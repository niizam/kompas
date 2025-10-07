import json
from datetime import datetime, timedelta, timezone
from enum import Enum
from typing import Dict, Any, List, Union, Optional
from urllib.parse import quote_plus
import requests
from fastapi import FastAPI, Query, HTTPException
from fastapi.responses import HTMLResponse, JSONResponse


class Format(Enum):
    JSON = "json"
    HTML = "html"


JAKARTA_TZ = timezone(timedelta(hours=7))
UTC = timezone.utc


class Kompas:
    BASE = "https://cds.kompas.id/api/v2/"
    ARTICLE_DETAIL_BASE = "https://api.kompas.id/icm/api/v1/article/"
    LIST_URL = BASE + "article/list"
    POPULAR_URL = BASE + "article/popular-article"
    HOT_TOPIC_URL = BASE + "meta/hot_topic"

    def __init__(self, timeout: float = 15.0):
        self.session = requests.Session()
        self.session.headers.update({
            "User-Agent": "okhttp/4.12.0",
            "Accept-Encoding": "gzip",
        })
        self.timeout = timeout

    # -------------------------- HTTP -------------------------- #

    def _get(self, url: str, params: Optional[Dict[str, Any]] = None) -> Optional[Dict[str, Any]]:
        try:
            r = self.session.get(url, params=params, timeout=self.timeout)
            r.raise_for_status()
            return r.json()
        except requests.RequestException:
            return None
        except ValueError:
            # not JSON
            return None

    # -------------------------- Utils -------------------------- #

    @staticmethod
    def _jakarta_str_to_epoch_utc(date_str: str) -> Optional[int]:
        """Parse 'YYYY-mm-dd HH:MM:SS' assumed in Asia/Jakarta, return epoch seconds UTC."""
        if not date_str:
            return None
        try:
            dt_local = datetime.strptime(date_str, "%Y-%m-%d %H:%M:%S").replace(tzinfo=JAKARTA_TZ)
            return int(dt_local.astimezone(UTC).timestamp())
        except Exception:
            return None

    @staticmethod
    def _epoch_utc_to_jakarta_str(epoch: Optional[int]) -> str:
        if epoch is None:
            return "Unknown"
        return datetime.fromtimestamp(epoch, tz=UTC).astimezone(JAKARTA_TZ).strftime("%Y-%m-%d %H:%M:%S")

    @staticmethod
    def _pick_thumbnail(thumbnails: Dict[str, Any]) -> Optional[str]:
        """Prefer larger sizes; fall back gracefully."""
        sizes = (thumbnails or {}).get("sizes", {})
        for key in ("full", "large", "medium", "postThumbnail"):
            url = (sizes.get(key) or {}).get("permalink")
            if url:
                return url
        return None

    @staticmethod
    def _extract_keywords(container: Dict[str, Any]) -> List[str]:
        """Merge keyword, postTag names, and category names; drop x-hide-*."""
        words: List[str] = []

        def add(name: Optional[str]):
            if not name:
                return
            n = name.strip()
            if not n or n.lower().startswith("x-hide-"):
                return
            if n not in words:
                words.append(n)

        add(container.get("keyword"))

        for tag in container.get("postTag", []) or []:
            add(tag.get("name"))

        for cat in container.get("category", []) or []:
            add(cat.get("name"))

        return words

    @staticmethod
    def _extract_authors_from_detail(data: Dict[str, Any]) -> List[Dict[str, str]]:
        """Prefer credits (role->name), fallback to author/articleByLine."""
        authors: List[Dict[str, str]] = []

        for credit in data.get("credits", []) or []:
            role = credit.get("role") or "Contributor"
            for name_with_email in credit.get("names", []) or []:
                name = (name_with_email or "").split(" - ")[0].strip()
                if name:
                    authors.append({role: name})

        if authors:
            return authors

        for name in data.get("author", []) or []:
            if name:
                authors.append({"Author": name})

        if not authors and data.get("articleByLine"):
            authors.append({"Contributor": data["articleByLine"]})

        return authors

    @staticmethod
    def _extract_authors_from_list_item(item: Dict[str, Any]) -> Dict[str, Any]:
        """
        Return a dict with possible keys like "Writer" and "Editor".
        If there is one editor, use a string; if multiple, use a list.
        """
        out: List[Dict[str, Any]] = []
        writer = item.get("articleByLine", "")
        if writer:
            out.append({"writer": writer})

        editors = [e.get("name") for e in (item.get("editors") or []) if e.get("name")]
        if editors:
            out.append({"editor": editors[0] if len(editors) == 1 else editors})

        return out

    @staticmethod
    def _normalize_content_blocks(raw_blocks: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
        """Map Kompas content blocks to a compact, consistent schema."""
        normalized: List[Dict[str, Any]] = []
        for block in raw_blocks or []:
            btype = block.get("type")
            body = (block.get("body") or "").strip()
            meta = block.get("metaBody") or {}

            item: Dict[str, Any] = {"type": btype}

            if btype in {"text", "heading-2", "heading-3", "heading-4", "blockquote", "caption"}:
                text = (meta.get("text") or meta.get("src") or body or "").strip()
                if text:
                    item["text"] = text

            elif btype == "image":
                url = meta.get("src") or meta.get("permalink")
                if url:
                    item["url"] = url
                    if meta.get("caption"):
                        item["caption"] = meta.get("caption").strip()

            elif btype == "ordered":
                items = [i.get("src", "").strip() for i in (meta.get("listText") or []) if i.get("src")]
                if items:
                    item["list"] = items

            elif btype == "recommender":
                rec_url = meta.get("src")
                rec_title = (meta.get("title") or "").strip()
                if rec_url and rec_title:
                    item["recommendation"] = {"title": rec_title, "url": rec_url}

            elif btype == "separator":
                # carry through to render as <hr/>
                pass

            # Add only if it has meaningful data besides 'type'
            if len(item) > 1 or btype == "separator":
                normalized.append(item)

        return normalized

    # -------------------------- Rendering -------------------------- #

    @staticmethod
    def _render_html(structured: Dict[str, Any]) -> str:
        title = structured.get("title", "")
        url = structured.get("url", "")
        published = Kompas._epoch_utc_to_jakarta_str(structured.get("published_date"))
        authors: List[Dict[str, str]] = structured.get("authors", [])
        keywords_list: List[str] = structured.get("keywords", [])
        thumb = structured.get("thumbnail")
        blocks: List[Dict[str, Any]] = structured.get("content", [])

        parts: List[str] = []
        parts.append("<!DOCTYPE html>")
        parts.append("<html><head>")
        parts.append(f"<title>{title}</title>")
        parts.append('<meta charset="UTF-8">')
        parts.append('<meta name="viewport" content="width=device-width, initial-scale=1.0">')
        parts.append("<style>")
        parts.append("body{font-family:sans-serif;line-height:1.6;max-width:800px;margin:auto;padding:20px}")
        parts.append("h1{border-bottom:2px solid #ccc;padding-bottom:10px}")
        parts.append(".metadata p{margin:5px 0;font-size:.9em;color:#555}")
        parts.append(".content-block{margin-bottom:20px}")
        parts.append(".content-block img{max-width:100%;height:auto;display:block;margin:10px 0}")
        parts.append(".recommendation{border-left:4px solid #007bff;padding-left:10px;margin-top:20px}")
        parts.append("</style></head><body>")
        parts.append(f"<h1>{title}</h1>")

        parts.append('<div class="metadata">')
        parts.append(f'<p><strong>URL:</strong> <a href="{url}">{url}</a></p>')
        parts.append(f"<p><strong>Published:</strong> {published}</p>")
        parts.append("<p><strong>Authors:</strong></p><ul>")
        for a in authors:
            for role, name in a.items():
                parts.append(f"<li>{role}: {name}</li>")
        parts.append("</ul>")
        if keywords_list:
            parts.append(f"<p><strong>Keywords:</strong> {', '.join(keywords_list)}</p>")
        if thumb:
            parts.append(f'<a href="{thumb}" target="_blank"><img src="{thumb}" alt="Thumbnail" style="max-width:100%;"></a>')
        parts.append("</div><hr/><h2>Content:</h2>")

        for b in blocks:
            btype = b.get("type") or "unknown"
            parts.append(f'<div class="content-block type-{btype}">')

            if "text" in b:
                if btype.startswith("heading-"):
                    lvl = btype.split("-")[-1]
                    parts.append(f"<h{lvl}>{b['text']}</h{lvl}>")
                else:
                    parts.append(f"<p>{b['text']}</p>")

            elif btype == "ordered" and "list" in b:
                parts.append("<ol>")
                for it in b["list"]:
                    parts.append(f"<li>{it}</li>")
                parts.append("</ol>")

            elif btype == "recommender" and "recommendation" in b:
                rec = b["recommendation"]
                parts.append('<div class="recommendation">')
                parts.append(f'<p><strong>See also:</strong> <a href="{rec["url"]}">{rec["title"]}</a></p>')
                parts.append("</div>")

            elif btype == "separator":
                parts.append("<hr/>")

            parts.append("</div>")

        parts.append("</body></html>")
        return "\n".join(parts)

    # -------------------------- Public API -------------------------- #

    def article_detail(self, permalink: str, format: Format = Format.JSON) -> Union[str, List[Dict[str, Any]]]:
        """
        Fetch a single article by kompas permalink and return JSON string or HTML string.
        """
        slug = permalink.split("/artikel/", 1)[-1]
        if slug == permalink:  # '/artikel/' not found
            slug = permalink.rstrip("/").split("/")[-1]

        slug = slug.split("?", 1)[0].split("#", 1)[0]
        if slug.endswith("/"):
            slug = slug[:-5]


        data = self._get(self.ARTICLE_DETAIL_BASE + slug)
        if not data:
            return "[]" if format == Format.JSON else "<!-- no data -->"

        structured = {
            "title": data.get("title", ""),
            "content": self._normalize_content_blocks(data.get("content") or []),
            "url": data.get("permalink", permalink),
            "authors": self._extract_authors_from_detail(data),
            "published_date": self._jakarta_str_to_epoch_utc(data.get("publishedDate", "")),
            "keywords": self._extract_keywords(data),
            "thumbnail": self._pick_thumbnail(data.get("thumbnails") or {}),
        }

        if format == Format.HTML:
            return self._render_html(structured)
        return json.dumps(structured, ensure_ascii=False)

    def process_article(self, article: Dict[str, Any]) -> Dict[str, Any]:
        """
        Normalize an article item from list/search/popular feeds.
        """
        return {
            "title": article.get("title", ""),
            "content": self._extract_excerpt_as_paragraphs(article.get("content") or [], article.get("excerpt") or ""),
            "url": article.get("permalink", ""),
            "authors": self._extract_authors_from_list_item(article),
            "published_date": self._jakarta_str_to_epoch_utc(article.get("publishedDate", "")),
            "keywords": self._extract_keywords(article),
            "thumbnail": self._pick_thumbnail(article.get("thumbnails") or {}),
        }

    @staticmethod
    def _extract_excerpt_as_paragraphs(raw_blocks: List[Dict[str, Any]], fallback_excerpt: str) -> List[str]:
        """
        Convert a subset of blocks to simple text paragraphs.
        If no blocks are suitable, return [fallback_excerpt] (when available).
        """
        paras: List[str] = []
        for block in raw_blocks or []:
            btype = block.get("type")
            if btype in {"text", "heading-2", "heading-3", "blockquote", "caption"}:
                meta = block.get("metaBody") or {}
                text = (meta.get("text") or block.get("body") or "").strip()
                if text:
                    paras.append(text)
            elif btype == "image":
                meta = block.get("metaBody") or {}
                cap = (meta.get("caption") or "").strip()
                if cap:
                    paras.append(cap)

        if not paras and fallback_excerpt:
            return [fallback_excerpt.strip()]
        return paras

    def articles(self, type: Optional[str] = None, search: Optional[str] = None) -> List[Dict[str, Any]]:
        """
        Retrieve articles feed.

        Args:
          type: None | "popular" | "hot"
          search: keyword to search; ignored if type is set

        Returns:
          List of normalized article dicts.
        """
        if type == "hot":
            payload = self._get(self.HOT_TOPIC_URL) or {}
            topics = ((payload.get("result") or {}).get("hot")) or []
            out: List[Dict[str, Any]] = []
            for topic in topics:
                for art in (topic.get("articles") or []):
                    out.append(self.process_article(art))
            return out

        if type == "popular":
            payload = self._get(self.POPULAR_URL) or {}
            results = payload.get("result")
            if not isinstance(results, list):
                return []
            return [self.process_article(a) for a in results]

        if search and type is None:
            today = datetime.now(JAKARTA_TZ).strftime("%Y-%m-%d")
            search_url = f"{self.BASE}article/search"
            params = {
                "from": "2017-01-01",
                "to": today,
                "keyword": quote_plus(search),
                "priority": "score",
            }
            payload = self._get(search_url, params=params) or {}
            results = payload.get("result") or []
            return [self.process_article(a) for a in results]

        # default list feed
        payload = self._get(self.LIST_URL) or {}
        results = payload.get("result") or []
        return [self.process_article(a) for a in results]


app = FastAPI(title="Kompas API")
kompas_api = Kompas()

@app.get("/api/article")
def get_articles(type: Optional[str] = Query(default=None, pattern="^(popular|hot)$"), search: Optional[str] = None):
    try:
        return kompas_api.articles(type=type, search=search)
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@app.get("/read")
def get_article_detail(permalink: str, format: Format = Format.JSON):
    try:
        result = kompas_api.article_detail(permalink, format)
        if format == Format.HTML:
            return HTMLResponse(content=result)
        return JSONResponse(content=json.loads(result))
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@app.get("/healthz")
def healthz():
    return {"status": "ok"}

from fastapi.responses import HTMLResponse

@app.get("/", response_class=HTMLResponse)
def root():
    year = datetime.now(JAKARTA_TZ).year
    html = r"""
<!DOCTYPE html>
<html>
<head>
<meta charset="utf-8"/>
<title>Kompas.id</title>
<meta name="viewport" content="width=device-width, initial-scale=1.0"/>
<link rel="icon" type="image/x-icon" href="https://www.kompas.id/artikel/favicon.png">
<style>
  body {
    background: #e0e0e0 url('data:image/gif;base64,R0lGODlhEAAQAPQAAP///5mZmXPz8/Dw8O7u7tnZ2d3d3bu7u7GxsbS0tLe3t7q6ur+/v+Li4tjY2NPT09/f39jY2Nvb2+jo6N7e3uTk5OTk5P///wAAAAAAAAAAAAAAAAAAAAAAAAAAACH5BAEAABwALAAAAAAQABAAAAWg4CeOZGmeaKqubOu+cCzPdFQKBQKh8Si8Uqv2CwGAhA4HCAJgKBbDabD0Wi0Wi4XFYj8fj8HgkEolAqFQKJQKpWq/X6fYLBYLBaLRaLRcLpcJBAAAOw==') repeat;
    color: #000;
    font-family: "Verdana", "Tahoma", "Arial", sans-serif;
  }
  a { color: #0000EE; }
  a:visited { color: #551A8B; }
  .container {
    max-width: 920px; margin: 10px auto; padding: 6px;
    border: 3px double #000; background: #fffdf5;
  }
  .header {
    border: 4px ridge #ccc; padding: 6px; background: #ffffcc;
    text-align: center;
  }
  .header h1 { margin: 4px 0; font-size: 28px; letter-spacing: 1px; }
  .nav {
    margin: 8px 0; padding: 6px; border: 3px groove #999; background: #f0f0ff;
    text-align: center;
  }
  .btn {
    display: inline-block; padding: 6px 10px; margin: 2px;
    border: 3px outset #bbb; background: #e6e6e6; cursor: pointer; font-weight: bold;
  }
  .btn:active { border: 3px inset #bbb; }
  .searchbar { margin-top: 6px; }
  input[type="text"] {
    padding: 4px; border: 2px inset #ccc; width: 260px; background: #fff;
  }
  .ticker {
    margin: 8px 0; border: 3px groove #aaa; background: #ccffcc; padding: 4px;
  }
  .panel {
    border: 4px ridge #ccc; background: #fff; padding: 6px; margin-top: 8px;
  }
  table.results {
    width: 100%; border-collapse: separate; border-spacing: 0; margin-top: 6px;
  }
  table.results th, table.results td {
    border: 2px solid #000; padding: 6px; vertical-align: top;
  }
  table.results th { background: #c0c0ff; }
  .thumb {
    width: 96px; height: 72px; object-fit: cover; border: 2px inset #999; background: #eee;
  }
  .foot {
    margin-top: 12px; text-align: center; font-size: 12px; color: #333;
  }
  .blink {
    animation: blink 1s steps(2, start) infinite;
  }
  @keyframes blink { to { visibility: hidden; } }
  .content-snippet {
    margin-top: 6px; background: #fffff0; border: 2px dashed #999; padding: 6px;
    font-size: 13px;
  }
</style>
</head>
<body>
  <div class="container">
    <div class="header">
      <h1><a href="https://www.kompas.id" class="flex w-64" title="Kompas.id"><img class="w-auto h-10 lg:h-14 mx-auto" src="https://cdn-www.kompas.id/assets/kompas-logo-masthead.svg" alt="Kompas.id" width="249" height="40"></a></h1>
    </div>

    <div class="nav">
      <span class="btn" onclick="loadLatest()">Latest</span>
      <span class="btn" onclick="loadPopular()">Popular</span>
      <span class="btn" onclick="loadHot()">Hot Topics</span>
      <span style="margin-left:10px"></span>
      <a class="btn" href="/healthz" target="_blank">Health Check</a>
      <div class="searchbar">
        <form onsubmit="doSearch(event)">
          <input id="q" type="text" placeholder="Search Kompas..." />
          <button class="btn" type="submit">Search!</button>
        </form>
      </div>
    </div>

    <div class="ticker">
      <marquee id="headline-marquee" behavior="scroll" direction="left" scrollamount="4">
        Loading headlines… <span class="blink">Please wait</span>
      </marquee>
    </div>

    <div class="panel">
      <b>Results</b>
      <table class="results">
        <thead>
          <tr>
            <th width="110">Thumbnail</th>
            <th>News</th>
          </tr>
        </thead>
        <tbody id="results">
          <tr><td colspan="2">Loading... please wait</td></tr>
        </tbody>
      </table>
    </div>

    <div class="foot">
      <hr/>
      <div>
        <font size="2">Copyright © %%YEAR%% PT Kompas Media Nusantara</font>
      </div>
    </div>
  </div>

  <script>
    function el(tag, attrs={}, kids=[]) {
      const n = document.createElement(tag);
      for (const [k,v] of Object.entries(attrs)) {
        if (k === 'class') n.className = v;
        else if (k === 'html') n.innerHTML = v;
        else n.setAttribute(k, v);
      }
      kids.forEach(k => n.appendChild(k));
      return n;
    }

    function readLink(permalink) {
      const href = "/read?permalink=" + encodeURIComponent(permalink) + "&format=html";
      return href;
    }

    function renderRows(items) {
      const body = document.getElementById('results');
      body.innerHTML = "";
      if (!items || items.length === 0) {
        body.appendChild(el('tr', {}, [el('td', {colspan:'2', html:'No results.'})]));
        return;
      }
      items.forEach(item => {
        const thumb = item.thumbnail ? el('img', {src:item.thumbnail, class:'thumb', alt:'thumb'}) : el('div', {class:'thumb'});
        const title = item.title || 'Untitled';
        const url = item.url || '#';
        const published = (item.published_date ? new Date(item.published_date * 1000) : null);
        const dateStr = published ? published.toLocaleString('en-GB', { hour12:false }) : 'Unknown';

        const aTitle = el('a', { href: readLink(url), target: '_blank', html: title });
        const by = (item.authors && item.authors.length)
          ? (' — ' + item.authors.map(o => {
                const k = Object.keys(o)[0];
                const v = o[k];
                if (Array.isArray(v)) return k + ': ' + v.join(', ');
                return k + ': ' + v;
            }).join(' | '))
          : '';

        const kws = (item.keywords && item.keywords.length) ? ('<small><b>Keywords:</b> ' + item.keywords.join(', ') + '</small>') : '';

        // Build the right cell
        const cellRight = el('td', {}, [
          el('div', {html: '<b>' + aTitle.outerHTML + '</b>'}),
          el('div', {html: '<small><b>Published:</b> ' + dateStr + by + '</small>'}),
        ]);

        const contentParas = Array.isArray(item.content) ? item.content.slice(0, 4) : []; // show a few
        if (contentParas.length) {
          const snippetWrap = el('div', {class: 'content-snippet'});
          contentParas.forEach(p => snippetWrap.appendChild(el('p', {html: p})));
          cellRight.appendChild(snippetWrap);
        }

        // Source line (kept after content)
        if (url) cellRight.appendChild(el('div', {html: '<small><b>Source:</b> <a href="' + url + '" target="_blank">' + url + '</a></small>'}));

        // Keywords line (kept after content)
        if (kws) cellRight.appendChild(el('div', {html: kws}));

        const row = el('tr', {}, [el('td', {}, [thumb]), cellRight]);
        body.appendChild(row);
      });
    }

    async function fetchJSON(endpoint) {
      try {
        const r = await fetch(endpoint, { headers: { 'Accept': 'application/json' } });
        if (!r.ok) throw new Error('HTTP ' + r.status);
        return await r.json();
      } catch (e) {
        console.error(e);
        const body = document.getElementById('results');
        body.innerHTML = "";
        body.appendChild(el('tr', {}, [el('td', {colspan:'2', html:'<span style="color:red">Error: ' + e.message + '</span>'})]));
        return null;
      }
    }

    function doSearch(ev) {
      ev.preventDefault();
      const q = document.getElementById('q').value.trim();
      if (!q) { loadLatest(); return; }
      fetchJSON('/api/article?search=' + encodeURIComponent(q)).then(renderRows);
    }

    function loadLatest() { fetchJSON('/api/article').then(renderRows); }
    function loadPopular() { fetchJSON('/api/article?type=popular').then(renderRows); }
    function loadHot() { fetchJSON('/api/article?type=hot').then(renderRows); }

    // ----- Ticker / Marquee -----
    function setMarqueeText(text) {
      const mq = document.getElementById('headline-marquee');
      mq.textContent = text;
    }

    async function loadTicker() {
      const items = await fetchJSON('/api/article?type=hot');
      if (!items || !items.length) {
        setMarqueeText('No hot topics available at the moment.');
        return;
      }
      const titles = items.map(it => it && it.title).filter(Boolean);
      const line = titles.slice(0, 30).join('  •  ');
      setMarqueeText(line);
    }

    // Initial load
    loadLatest();
    loadTicker();
  </script>

  <noscript>
    <div style="max-width:920px;margin:10px auto;border:3px solid #000;background:#fff;padding:8px;">
      This site needs JavaScript to load articles. Try <a href="/api/article" target="_blank">/api/article</a>.
    </div>
  </noscript>
</body>
</html>
""".replace("%%YEAR%%", str(year))
    return HTMLResponse(content=html)

# Example Usage:

#     list_articles = kompas.articles()
#     print(list_articles)

#     popular_articles = kompas.articles(type="popular")
#     print(f"Headlines in popular articles: {', '.join([a['title'] for a in popular_articles])}")

#     hot_topics = kompas.articles(type="hot")
#     print(f"Keywords in hot topics: {', '.join([t['title'] for t in hot_topics])}")

#     search_articles = kompas.articles(search="prabowo")
#     print(f"Number of articles found for 'prabowo': {len(search_articles)}")

#     article_detail_html = kompas.article_detail(
#         input("Enter Kompas article URL: ").strip(),
#         Format.HTML
#     )
#     with open("article.html", "w", encoding="utf-8") as f:
#         f.write(article_detail_html)

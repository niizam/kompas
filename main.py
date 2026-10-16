import json
import random
import re
from datetime import datetime, timedelta, timezone
from enum import Enum
from html import escape, unescape
from pathlib import Path
from typing import Dict, Any, List, Union, Optional
from urllib.parse import quote, quote_plus
import requests
from fastapi import FastAPI, Query, HTTPException
from fastapi.responses import HTMLResponse, JSONResponse, RedirectResponse
from fastapi.staticfiles import StaticFiles

class Format(Enum):
    JSON = "json"
    HTML = "html"


JAKARTA_TZ = timezone(timedelta(hours=7))
UTC = timezone.utc

BASE_DIR = Path(__file__).resolve().parent
STATIC_DIR = BASE_DIR / "static"
LAYOUT_TEMPLATE = (BASE_DIR / "templates" / "layout.html").read_text(encoding="utf-8")

DAYS_ID = ["Senin", "Selasa", "Rabu", "Kamis", "Jumat", "Sabtu", "Minggu"]
MONTHS_ID = ["Januari", "Februari", "Maret", "April", "Mei", "Juni", "Juli",
             "Agustus", "September", "Oktober", "November", "Desember"]

# -------------------------- 1990s page chrome -------------------------- #

def render_page(title: str, toolbar: str, main: str, before_page: str = "",
                scripts: str = "", query: str = "") -> str:
    """Fill the shared retro layout. Single pass, so content can't inject placeholders."""
    values = {
        "TITLE": escape(title, quote=False),
        "TOOLBAR": toolbar,
        "MAIN": main,
        "BEFORE_PAGE": before_page,
        "SCRIPTS": scripts,
        "QUERY": escape(query),
        "YEAR": str(datetime.now(JAKARTA_TZ).year),
    }
    return re.sub(r"%%([A-Z_]+)%%", lambda m: values.get(m.group(1), m.group(0)), LAYOUT_TEMPLATE)


def read_link(permalink: str) -> str:
    return "/read?permalink=" + quote(permalink, safe="") + "&format=html"


def strip_tags(text: str) -> str:
    return unescape(re.sub(r"<[^>]+>", "", text or "")).strip()


def format_jakarta_long(epoch: Optional[int]) -> str:
    if epoch is None:
        return "Unknown date"
    d = datetime.fromtimestamp(epoch, tz=UTC).astimezone(JAKARTA_TZ)
    return f"{DAYS_ID[d.weekday()]}, {d.day} {MONTHS_ID[d.month - 1]} {d.year} &mdash; {d:%H:%M} WIB"


def article_toolbar(url: str, title: str) -> str:
    buttons = ['<a class="btn95" href="/">&laquo; Front Page</a>',
               '<button class="btn95" type="button" onclick="window.print()">&#128424; Print</button>']
    if url:
        plain = strip_tags(title) or "A story from KOMPAS Online"
        mailto = "mailto:?subject=" + quote(plain) + "&body=" + quote("Check out this story:\n\n" + plain + "\n" + url)
        buttons.append(f'<a class="btn95" href="{escape(mailto)}">&#9993; E-mail to a Friend</a>')
        buttons.append(f'<a class="btn95" href="{escape(url)}" target="_blank" rel="noopener">Original &#8599;</a>')
    return "\n".join("    " + b for b in buttons)


FRONT_TOOLBAR = """\
    <a class="btn95" href="/?feed=latest" data-feed="latest">&#128240; Latest</a>
    <a class="btn95" href="/?feed=popular" data-feed="popular">&#11088; Popular</a>
    <a class="btn95" href="/?feed=hot" data-feed="hot">&#128293; Hot Topics</a>"""

FRONT_MAIN = """\
        <div class="section-bar">
          <h2 id="section-title">Latest News</h2>
          <small id="section-meta">Contacting host...</small>
        </div>
        <div id="results" aria-live="polite">
          <div class="loading-msg"><span class="hourglass" aria-hidden="true">&#8987;</span> Loading&hellip; <span class="blink">please wait</span></div>
        </div>"""

FRONT_OVERLAYS = """\
<div id="dialup" hidden>
  <div class="win95" role="dialog" aria-modal="true" aria-labelledby="dial-title">
    <div class="titlebar"><span id="dial-title">Connect To: KOMPAS Online</span><button class="x" type="button" data-skip aria-label="Close">&times;</button></div>
    <div class="win-body">
      <div class="dial-row">
        <div class="dial-icon" aria-hidden="true">&#9742;</div>
        <div>Dial-Up Networking<br><span id="dial-status"><b>Initializing modem...</b></span></div>
      </div>
      <div class="dial-log bevel-in" id="dial-log"></div>
      <div class="progress95 bevel-in" id="dial-progress"></div>
      <div class="win-actions"><button class="btn95" type="button" data-skip>Skip &raquo;</button></div>
    </div>
  </div>
</div>
<div id="popup" class="win95" role="dialog" aria-labelledby="pop-title" hidden>
  <div class="titlebar"><span id="pop-title">&#128226; You've got news!</span><button class="x" type="button" data-close aria-label="Close">&times;</button></div>
  <div class="win-body">
    <b>KOMPAS Online Breaking News Alert</b>
    <p class="pop-headline" id="pop-headline"></p>
    <div class="win-actions">
      <a class="btn95" id="pop-read" href="/">Read Story</a>
      <button class="btn95" type="button" data-close>Close</button>
    </div>
  </div>
</div>"""

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
    def _render_block(b: Dict[str, Any], first_para: bool) -> str:
        btype = b.get("type") or "unknown"

        if "text" in b:
            if btype.startswith("heading-"):
                lvl = btype.split("-")[-1]
                return f"<h{lvl}>{b['text']}</h{lvl}>"
            if btype == "blockquote":
                return f"<blockquote>{b['text']}</blockquote>"
            if btype == "caption":
                return f"<p class=\"caption\">{b['text']}</p>"
            cls = ' class="first"' if first_para else ""
            return f"<p{cls}>{b['text']}</p>"

        if btype == "image" and "url" in b:
            src = escape(b["url"])
            cap = f"<figcaption>{b['caption']}</figcaption>" if b.get("caption") else ""
            return (f'<figure><a class="thumb-frame" href="{src}" target="_blank">'
                    f'<img src="{src}" alt="" loading="lazy" data-modem></a>{cap}</figure>')

        if btype == "ordered" and "list" in b:
            return "<ol>" + "".join(f"<li>{it}</li>" for it in b["list"]) + "</ol>"

        if btype == "recommender" and "recommendation" in b:
            rec = b["recommendation"]
            return (f'<div class="see-also"><b>&#9758; SEE ALSO:</b> '
                    f'<a href="{escape(read_link(rec["url"]))}">{rec["title"]}</a></div>')

        if btype == "separator":
            return "<hr>"

        return ""

    @staticmethod
    def _render_html(structured: Optional[Dict[str, Any]], permalink: str = "") -> str:
        if not structured:
            main = ('<div class="article"><div class="nodata">'
                    '<h1>404 - Story Not Found</h1>'
                    '<p>The story you requested could not be retrieved from the news wire.<br>'
                    'It may have moved, or the line may be busy.</p>'
                    '<p><a class="btn95" href="/">&laquo; Back to the Front Page</a></p>'
                    '</div></div>')
            return render_page("KOMPAS Online -- Story Not Found", article_toolbar(permalink, ""), main)

        title = structured.get("title", "")
        url = structured.get("url", "")
        published = format_jakarta_long(structured.get("published_date"))
        authors: List[Dict[str, str]] = structured.get("authors", [])
        keywords_list: List[str] = structured.get("keywords", [])
        thumb = structured.get("thumbnail")
        blocks: List[Dict[str, Any]] = structured.get("content", [])

        parts: List[str] = ['<div class="article">']
        section = escape(keywords_list[-1]) if keywords_list else "Berita"
        parts.append(f'<div class="crumbs"><a href="/">KOMPAS Online</a> &raquo; {section}</div>')
        parts.append(f"<h1>{title}</h1>")

        byline = [f"&#128197; {published}"]
        for a in authors:
            for role, name in a.items():
                byline.append(f"<b>{escape(role)}:</b> {escape(name)}")
        parts.append('<div class="byline">' + " &middot; ".join(byline) + "</div>")

        if thumb:
            t = escape(thumb)
            parts.append(f'<figure class="lead"><a class="thumb-frame" href="{t}" target="_blank">'
                         f'<img src="{t}" alt="" data-modem></a>'
                         f'<figcaption>Click picture to enlarge (may take a while on 14.4k modems)</figcaption></figure>')

        parts.append('<div class="body">')
        first_para = True
        for b in blocks:
            is_para = b.get("type") == "text" and "text" in b
            parts.append(Kompas._render_block(b, first_para and is_para))
            if is_para:
                first_para = False
        parts.append("</div>")

        parts.append('<div class="end-mark">* * * &#9632; * * *</div>')
        if keywords_list:
            links = ", ".join(f'<a href="/?q={quote_plus(k)}">{escape(k)}</a>' for k in keywords_list)
            parts.append(f'<div class="tags"><b>Related topics:</b> {links}</div>')
        parts.append(f'<p class="tags no-print"><a href="/">&laquo; Back to the Front Page</a></p>')
        parts.append("</div>")

        page_title = "KOMPAS Online -- " + strip_tags(title)
        return render_page(page_title, article_toolbar(url, title), "\n".join(parts))

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
            return "[]" if format == Format.JSON else self._render_html(None, permalink)

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

@app.get("/random")
def random_story():
    """Webring "Random Story" button: jump to a random article from the latest feed."""
    items = [a for a in kompas_api.articles() if a.get("url")]
    if not items:
        return RedirectResponse("/")
    return RedirectResponse(read_link(random.choice(items)["url"]))

app.mount("/static", StaticFiles(directory=STATIC_DIR), name="static")

@app.get("/", response_class=HTMLResponse)
def root(q: Optional[str] = None):
    page = render_page(
        "KOMPAS Online -- Edisi Internet",
        FRONT_TOOLBAR,
        FRONT_MAIN,
        before_page=FRONT_OVERLAYS,
        scripts='<script src="/static/front.js"></script>',
        query=q or "",
    )
    return HTMLResponse(content=page)

# Example usage:
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

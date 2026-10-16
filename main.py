import json
import random
import re
from datetime import date, datetime, timedelta, timezone
from enum import Enum
from html import escape, unescape
from pathlib import Path
from threading import Lock
from typing import Dict, Any, List, Union, Optional
from urllib.parse import quote, quote_plus, urlencode
import requests
from cachetools import TTLCache
from feedgen.feed import FeedGenerator
from fastapi import FastAPI, Query, HTTPException, Request
from fastapi.responses import HTMLResponse, JSONResponse, PlainTextResponse, RedirectResponse, Response
from fastapi.staticfiles import StaticFiles

from regions import PROVINCES, DEFAULT_PROVINCE_CODE

class Format(Enum):
    JSON = "json"
    HTML = "html"


JAKARTA_TZ = timezone(timedelta(hours=7))
UTC = timezone.utc

BASE_DIR = Path(__file__).resolve().parent
STATIC_DIR = BASE_DIR / "static"
LAYOUT_TEMPLATE = (BASE_DIR / "templates" / "layout.html").read_text(encoding="utf-8")
LLMS_TEMPLATE = (BASE_DIR / "templates" / "llms.txt").read_text(encoding="utf-8")

DAYS_ID = ["Senin", "Selasa", "Rabu", "Kamis", "Jumat", "Sabtu", "Minggu"]
MONTHS_ID = ["Januari", "Februari", "Maret", "April", "Mei", "Juni", "Juli",
             "Agustus", "September", "Oktober", "November", "Desember"]

# -------------------------- 1990s page chrome -------------------------- #

def render_page(title: str, toolbar: str, main: str, before_page: str = "",
                scripts: str = "", query: str = "") -> str:
    """Fill the shared retro layout. Single pass, so content can't inject placeholders."""
    values = {
        "TITLE": escape(title, quote=False),
        "TOOLBAR": f'  <div class="toolbar" role="toolbar">\n{toolbar}\n  </div>' if toolbar else "",
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


FRONT_TOOLBAR = ""

FRONT_MAIN = """\
        <div id="front-modules">
          <div class="topics bx">
            <ul class="topic-tabs" role="tablist">
              <li><button type="button" role="tab" data-topic="latest" aria-selected="true">Top Stories</button></li>
              <li><button type="button" role="tab" data-topic="popular" aria-selected="false">Popular</button></li>
              <li><button type="button" role="tab" data-topic="hot" aria-selected="false">Hot</button></li>
              <li><button type="button" role="tab" data-topic="region" aria-selected="false" id="topic-tab-region">My Area</button></li>
            </ul>
            <div class="topics-body">
              <ul class="topic-list" id="topic-list" role="tabpanel"><li>Loading&hellip;</li></ul>
              <div class="topic-pic" id="topic-pic"></div>
            </div>
            <div class="topics-foot"><a href="/?feed=latest" id="topic-more">More news &raquo;</a> &middot; <a href="/rss.xml" id="topic-rss" class="rss-mini">RSS</a></div>
          </div>

          <div class="bx region-box" id="region-box">
            <div class="bx-h c-dae">News from your area: <span id="region-name">&hellip;</span>
              <label class="region-pick">Change: <select id="region-select" aria-label="Choose your province"><option>Loading&hellip;</option></select></label>
            </div>
            <div class="bx-b">
              <div class="region-note" id="region-note">Finding where you are&hellip;</div>
              <ul class="region-list" id="region-list"></ul>
              <div class="region-more"><a href="/" id="region-more">More news from this area &raquo;</a> &middot; <a href="/rss.xml" id="region-rss" class="rss-mini">RSS</a></div>
            </div>
          </div>

          <div class="section-grid" id="section-grid"></div>
        </div>

        <div class="section-bar">
          <h2 id="section-title">Latest News</h2>
          <small id="section-meta">Contacting host...</small>
          <a class="rss-mini" id="section-rss" href="/rss.xml">RSS</a>
        </div>
        <div id="results" aria-live="polite">
          <div class="loading-msg"><span class="hourglass" aria-hidden="true">&#8987;</span> Loading&hellip; <span class="blink">please wait</span></div>
        </div>
        <div class="pager" id="pager"></div>"""

FRONT_OVERLAYS = """\
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

    def __init__(self, timeout: float = 15.0, cache_ttl: float = 120.0):
        self.session = requests.Session()
        self.session.headers.update({
            "User-Agent": "okhttp/4.12.0",
            "Accept-Encoding": "gzip",
        })
        self.timeout = timeout
        # The front page fans out into a dozen feeds; keep upstream traffic polite.
        self._cache: TTLCache = TTLCache(maxsize=512, ttl=cache_ttl)
        self._cache_lock = Lock()

    # -------------------------- HTTP -------------------------- #

    def _get(self, url: str, params: Optional[Dict[str, Any]] = None) -> Optional[Dict[str, Any]]:
        key = (url, tuple(sorted((params or {}).items())))
        with self._cache_lock:
            if key in self._cache:
                return self._cache[key]
        try:
            r = self.session.get(url, params=params, timeout=self.timeout)
            r.raise_for_status()
            data = r.json()
        except requests.RequestException:
            return None
        except ValueError:
            # not JSON
            return None
        with self._cache_lock:
            self._cache[key] = data
        return data

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

        epoch = structured.get("published_date")
        if epoch is not None:
            day = datetime.fromtimestamp(epoch, tz=UTC).astimezone(JAKARTA_TZ).date().isoformat()
            published = f'<a href="/?date={day}" title="More news from this day">{published}</a>'
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

    def articles(self, type: Optional[str] = None, search: Optional[str] = None,
                 date_from: Optional[date] = None, date_to: Optional[date] = None,
                 page: Optional[int] = None) -> List[Dict[str, Any]]:
        """
        Retrieve articles feed.

        Args:
          type: None | "popular" | "hot"
          search: keyword to search; ignored if type is set
          date_from, date_to: limit a search to this date range (Jakarta dates).
            Either one on its own, without a keyword, gives a dated archive.
          page: result page for searches (10 per page, starting at 1)

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

        if type is None and (search or date_from or date_to):
            today = datetime.now(JAKARTA_TZ).date()
            search_url = f"{self.BASE}article/search"
            params = {
                "from": (date_from or date(2017, 1, 1)).isoformat(),
                "to": (date_to or today).isoformat(),
                "keyword": search or "",
                "priority": "score",
            }
            if page and page > 1:
                params["page"] = page
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
def get_articles(
    type: Optional[str] = Query(default=None, pattern="^(popular|hot)$"),
    search: Optional[str] = None,
    date_: Optional[date] = Query(default=None, alias="date", description="Archive for one day (YYYY-MM-DD)"),
    date_from: Optional[date] = Query(default=None, alias="from", description="Search from this date (YYYY-MM-DD)"),
    date_to: Optional[date] = Query(default=None, alias="to", description="Search up to this date (YYYY-MM-DD)"),
    page: int = Query(default=1, ge=1, le=50),
):
    if date_:
        date_from = date_to = date_
    try:
        return kompas_api.articles(type=type, search=search, date_from=date_from, date_to=date_to, page=page)
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@app.get("/api/regions")
def get_regions():
    """Indonesian provinces for the "news from your area" box and the weather widget."""
    return {"default": DEFAULT_PROVINCE_CODE, "provinces": PROVINCES}

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

FEED_LABELS = {"latest": "Latest News", "popular": "Most Popular", "hot": "Hot Topics"}

def _image_type(url: str) -> str:
    # Kompas' image CDN converts on the fly, e.g. ".../filters:format(webp)/.../photo.jpg"
    if "format(webp)" in url:
        return "image/webp"
    ext = url.split("?", 1)[0].rsplit(".", 1)[-1].lower()
    return {"png": "image/png", "gif": "image/gif", "webp": "image/webp"}.get(ext, "image/jpeg")

@app.get("/rss.xml")
@app.get("/rss", include_in_schema=False)
def rss(
    request: Request,
    feed: str = Query(default="latest", pattern="^(latest|popular|hot)$"),
    q: Optional[str] = None,
    date_: Optional[date] = Query(default=None, alias="date"),
):
    """RSS 2.0 feed of any front page view: a feed, a search (?q=) or a day's archive (?date=)."""
    if q or date_:
        items = kompas_api.articles(search=q, date_from=date_, date_to=date_)
        bits = ([f"Search: {q}"] if q else []) + ([f"Archive {date_.isoformat()}"] if date_ else [])
        label = " / ".join(bits)
        page_qs = urlencode({k: v for k, v in (("q", q), ("date", date_ and date_.isoformat())) if v})
    else:
        items = kompas_api.articles(type=None if feed == "latest" else feed)
        label = FEED_LABELS[feed]
        page_qs = "" if feed == "latest" else f"feed={feed}"

    base = str(request.base_url).rstrip("/")
    fg = FeedGenerator()
    fg.title(f"KOMPAS Online -- {label}")
    # feedgen uses the last link set as the RSS <link>, so "self" goes first
    fg.link(href=str(request.url), rel="self")
    fg.link(href=f"{base}/" + (f"?{page_qs}" if page_qs else ""), rel="alternate")
    fg.description(f"{label} from kompas.id, via the KOMPAS Online alternative frontend.")
    fg.language("id")
    fg.ttl(10)
    fg.generator("KOMPAS Online (feedgen)")

    for item in items:
        if not item.get("url"):
            continue
        fe = fg.add_entry(order="append")
        fe.guid(item["url"], permalink=True)
        fe.title(strip_tags(item.get("title", "")) or "Untitled")
        fe.link(href=base + read_link(item["url"]))
        desc: List[str] = []
        if item.get("thumbnail"):
            desc.append(f'<p><img src="{escape(item["thumbnail"])}" alt=""></p>')
        for a in item.get("authors") or []:
            for role, name in a.items():
                names = ", ".join(name) if isinstance(name, list) else name
                desc.append(f"<p><b>{escape(role.capitalize())}:</b> {escape(names)}</p>")
        desc.extend(f"<p>{p}</p>" for p in (item.get("content") or [])[:3])
        fe.description("\n".join(desc) or " ")
        if item.get("published_date"):
            fe.pubDate(datetime.fromtimestamp(item["published_date"], tz=UTC))
        for kw in item.get("keywords") or []:
            fe.category(term=kw)
        if item.get("thumbnail"):
            fe.enclosure(item["thumbnail"], "0", _image_type(item["thumbnail"]))

    return Response(content=fg.rss_str(pretty=True), media_type="application/rss+xml; charset=utf-8")

@app.get("/llms.txt", response_class=PlainTextResponse)
def llms_txt(request: Request):
    """How to navigate this site and use its API, for language models (https://llmstxt.org)."""
    base = str(request.base_url).rstrip("/")
    provinces = ", ".join(f"{p['code']} = {p['name']}" for p in PROVINCES)
    body = LLMS_TEMPLATE.replace("{BASE}", base).replace("{PROVINCES}", provinces)
    return PlainTextResponse(body, media_type="text/plain; charset=utf-8")

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

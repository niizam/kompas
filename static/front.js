/* ==========================================================
   KOMPAS Online -- front page
   ========================================================== */

(function () {
  "use strict";

  var R = window.Retro;
  var FEEDS = {
    latest:  { title: "Latest News",  api: "/api/article" },
    popular: { title: "Most Popular", api: "/api/article?type=popular" },
    hot:     { title: "Hot Topics",   api: "/api/article?type=hot" }
  };
  var SECTIONS = [
    { label: "Politik & Hukum", q: "politik", c: "c-pol" },
    { label: "Ekonomi", q: "ekonomi", c: "c-eko" },
    { label: "Olahraga", q: "olahraga", c: "c-ola" },
    { label: "Internasional", q: "internasional", c: "c-int" },
    { label: "Iptek", q: "teknologi", c: "c-tek" },
    { label: "Budaya", q: "budaya", c: "c-bud" }
  ];
  var MONTHS = ["Jan", "Feb", "Mar", "Apr", "Mei", "Jun", "Jul", "Agu", "Sep", "Okt", "Nov", "Des"];
  var MONTHS_LONG = ["Januari", "Februari", "Maret", "April", "Mei", "Juni", "Juli",
                     "Agustus", "September", "Oktober", "November", "Desember"];
  var DAYS = ["Minggu", "Senin", "Selasa", "Rabu", "Kamis", "Jumat", "Sabtu"];
  var NEW_WINDOW_SECS = 3 * 3600;
  var RECENT_DAYS = 14;

  var results = document.getElementById("results");
  var modules = document.getElementById("front-modules");
  var sectionTitle = document.getElementById("section-title");
  var sectionMeta = document.getElementById("section-meta");
  var sectionRss = document.getElementById("section-rss");
  var pager = document.getElementById("pager");
  var searchInput = document.getElementById("q");
  var requestSeq = 0;
  var lastItems = [];
  var current = null;

  function el(tag, attrs, kids) {
    var n = document.createElement(tag);
    Object.keys(attrs || {}).forEach(function (k) {
      var v = attrs[k];
      if (k === "class") n.className = v;
      else if (k === "html") n.innerHTML = v;
      else if (k === "text") n.textContent = v;
      else n.setAttribute(k, v);
    });
    (kids || []).forEach(function (c) { if (c) n.appendChild(c); });
    return n;
  }

  function qs(params) {
    var parts = [];
    Object.keys(params).forEach(function (k) {
      if (params[k]) parts.push(k + "=" + encodeURIComponent(params[k]));
    });
    return parts.join("&");
  }

  // Jakarta-local date string from epoch seconds
  function jktDate(epoch) {
    if (!epoch) return "Unknown";
    var d = new Date((epoch + 7 * 3600) * 1000);
    return d.getUTCDate() + " " + MONTHS[d.getUTCMonth()] + " " + d.getUTCFullYear() + ", " +
      R.pad(d.getUTCHours()) + ":" + R.pad(d.getUTCMinutes()) + " WIB";
  }

  function longDay(iso) {
    var d = new Date(iso + "T00:00:00");
    if (isNaN(d)) return iso;
    return DAYS[d.getDay()] + ", " + d.getDate() + " " + MONTHS_LONG[d.getMonth()] + " " + d.getFullYear();
  }

  function isNew(epoch) {
    return epoch && (Date.now() / 1000 - epoch) < NEW_WINDOW_SECS;
  }

  function newest(items) {
    return items.slice().sort(function (a, b) { return (b.published_date || 0) - (a.published_date || 0); });
  }

  // Recent stories for a keyword; widens to all time when the last two weeks are quiet
  function recentSearch(q) {
    return R.api("/api/article?" + qs({ search: q, from: R.jakartaIso(-RECENT_DAYS) }))
      .then(function (items) {
        return items && items.length ? items : R.api("/api/article?" + qs({ search: q }));
      })
      .then(newest);
  }

  function byline(authors) {
    return (authors || []).map(function (o) {
      var k = Object.keys(o)[0];
      var v = o[k];
      return "<b>" + k.charAt(0).toUpperCase() + k.slice(1) + ":</b> " + (Array.isArray(v) ? v.join(", ") : v);
    }).join(" &middot; ");
  }

  function thumb(item, eager) {
    var a = el("a", { href: R.readLink(item.url), class: "thumb-frame", "aria-hidden": "true", tabindex: "-1" });
    if (item.thumbnail) {
      var img = el("img", { src: item.thumbnail, alt: "", loading: eager ? "eager" : "lazy", decoding: "async" });
      a.appendChild(R.modemify(img));
    } else {
      a.appendChild(el("span", { class: "thumb-empty", html: "[IMAGE]<br>not available" }));
    }
    return a;
  }

  function icons(item) {
    var out = [];
    if (isNew(item.published_date)) out.push(el("span", { class: "ico ico-new", text: "NEW" }));
    if (item.thumbnail) out.push(el("span", { class: "ico ico-photo", text: "FOTO", title: "With photo" }));
    return out;
  }

  function titleLink(item) {
    return el("a", { href: R.readLink(item.url), html: item.title || "Untitled" });
  }

  // ---------- Main list (feed / search / archive) ----------

  function storyText(item, paras) {
    var wrap = el("div", { class: "story-text" });
    var h = el("h3");
    if (isNew(item.published_date)) h.appendChild(el("span", { class: "new", text: "NEW!" }));
    h.appendChild(titleLink(item));
    wrap.appendChild(h);

    var who = byline(item.authors);
    wrap.appendChild(el("div", { class: "meta", html: jktDate(item.published_date) + (who ? " &middot; " + who : "") }));

    var content = Array.isArray(item.content) ? item.content.slice(0, paras) : [];
    if (content.length) {
      var snip = el("div", { class: "snippet" });
      content.forEach(function (p) { snip.appendChild(el("p", { html: p })); });
      wrap.appendChild(snip);
    }

    wrap.appendChild(el("div", { class: "more" }, [
      el("a", { href: R.readLink(item.url), html: "Baca selengkapnya &raquo;" })
    ]));

    var kws = (item.keywords || []).slice(0, 5);
    if (kws.length) {
      var kw = el("div", { class: "kw", html: "Topics: " });
      kws.forEach(function (k, i) {
        if (i) kw.appendChild(document.createTextNode(", "));
        kw.appendChild(el("a", { href: "/?q=" + encodeURIComponent(k), "data-q": k, text: k }));
      });
      wrap.appendChild(kw);
    }
    return wrap;
  }

  function render(items, kicker) {
    results.innerHTML = "";
    lastItems = items || [];
    if (!lastItems.length) {
      results.appendChild(el("div", { class: "error-msg", html:
        "<b>404 - No stories found.</b><br>Try another search or another day, or press <i>Reload</i> on your browser." }));
      sectionMeta.textContent = "0 stories";
      return;
    }

    var newestEpoch = lastItems.reduce(function (m, it) { return Math.max(m, it.published_date || 0); }, 0);
    sectionMeta.textContent = lastItems.length + " stories" + (newestEpoch ? " · Last updated " + jktDate(newestEpoch) : "");

    var top = lastItems[0];
    results.appendChild(el("div", { class: "headline" }, [
      el("span", { class: "kicker", text: kicker }),
      top.thumbnail ? thumb(top, true) : null,
      storyText(top, 3)
    ]));

    var tbody = el("tbody");
    lastItems.slice(1).forEach(function (item) {
      tbody.appendChild(el("tr", {}, [
        el("td", { class: "story-thumb" }, [thumb(item, false)]),
        el("td", { class: "story-body" }, [storyText(item, 2)])
      ]));
    });
    results.appendChild(el("table", { class: "stories", role: "presentation" }, [tbody]));
  }

  function renderPager(state, count) {
    pager.innerHTML = "";
    if (!(state.q || state.date)) return;
    var page = state.page || 1;
    if (page > 1) {
      pager.appendChild(el("a", { class: "btn95", href: pageUrl(Object.assign({}, state, { page: page - 1 })), "data-page": page - 1, html: "&laquo; Prev 10" }));
    }
    pager.appendChild(el("span", { class: "btn95 is-active", text: "Page " + page }));
    if (count >= 10) {
      pager.appendChild(el("a", { class: "btn95", href: pageUrl(Object.assign({}, state, { page: page + 1 })), "data-page": page + 1, html: "Next 10 &raquo;" }));
    }
  }

  function showLoading(what) {
    results.innerHTML = "";
    pager.innerHTML = "";
    results.appendChild(el("div", { class: "loading-msg", html:
      '<span class="hourglass" aria-hidden="true">&#8987;</span> Downloading ' + what +
      '&hellip; <span class="blink">please wait</span>' }));
    sectionMeta.textContent = "Contacting host...";
  }

  function markTabs(state) {
    document.querySelectorAll("#cat-tabs a").forEach(function (a) {
      var on = state.home ? a.getAttribute("href") === "/"
        : state.q ? (a.getAttribute("data-q") || "").toLowerCase() === state.q.toLowerCase()
        : state.date ? a.getAttribute("href") === "#calendar-box"
        : a.getAttribute("data-feed") === state.feed;
      a.classList.toggle("is-active", !!on);
    });
  }

  function load(state) {
    var seq = ++requestSeq;
    current = state;
    var api, kicker, title, rss, what;
    var page = state.page || 1;

    if (state.q || state.date) {
      api = "/api/article?" + qs({ search: state.q, date: state.date, page: page > 1 ? page : "" });
      rss = "/rss.xml?" + qs({ q: state.q, date: state.date });
      kicker = state.q ? "TOP RESULT" : "ARCHIVE";
      title = state.q && state.date ? "“" + state.q + "” on " + state.date
        : state.q ? "Search: “" + state.q + "”"
        : "Archive: " + longDay(state.date);
      what = state.q ? "search results" : "the archive";
    } else {
      var feed = FEEDS[state.feed] ? state.feed : "latest";
      api = FEEDS[feed].api;
      rss = "/rss.xml" + (feed === "latest" ? "" : "?feed=" + feed);
      kicker = "HEADLINE";
      title = state.home ? "Latest News — Full Coverage" : FEEDS[feed].title;
      what = "today's edition";
    }

    sectionTitle.textContent = title;
    sectionRss.href = rss;
    document.title = "KOMPAS Online -- " + (state.home ? "Edisi Internet" : title);
    if (searchInput) searchInput.value = state.q || "";
    if (modules) modules.hidden = !state.home;
    markTabs(state);
    if (R.calendar) {
      if (state.date) R.calendar.setDate(state.date, false);
      else R.calendar.clear(false);
    }
    showLoading(what);

    return R.api(api)
      .then(function (items) {
        if (seq !== requestSeq) return null;
        render(items, kicker);
        renderPager(state, (items || []).length);
        return items;
      })
      .catch(function (e) {
        if (seq !== requestSeq) return null;
        results.innerHTML = "";
        results.appendChild(el("div", { class: "error-msg", html:
          "<b>Netscape is unable to locate the server.</b><br>" +
          "The server does not have a DNS entry or the line is busy. (" + R.escapeHtml(e.message) + ")<br><br>" +
          '<button class="btn95" type="button" id="retry">Try Again</button>' }));
        document.getElementById("retry").addEventListener("click", function () { load(state); });
        sectionMeta.textContent = "Transfer interrupted!";
        return null;
      });
  }

  function stateFromUrl() {
    var p = new URLSearchParams(location.search);
    var date = p.get("date");
    var state = {
      feed: p.get("feed") || "latest",
      q: (p.get("q") || "").trim(),
      date: /^\d{4}-\d{2}-\d{2}$/.test(date || "") ? date : "",
      page: Math.max(1, parseInt(p.get("page") || "1", 10) || 1)
    };
    state.home = !p.get("feed") && !state.q && !state.date;
    return state;
  }

  function pageUrl(state) {
    if (state.home) return "/";
    var s = (state.q || state.date)
      ? qs({ q: state.q, date: state.date, page: state.page > 1 ? state.page : "" })
      : (state.feed && state.feed !== "latest" ? "feed=" + state.feed : "feed=latest");
    return "/" + (s ? "?" + s : "");
  }

  function navigate(state) {
    state = Object.assign({ feed: "latest", q: "", date: "", page: 1 }, state);
    state.home = !!state.home;
    history.pushState(state, "", pageUrl(state));
    window.scrollTo(0, 0);
    return load(state);
  }

  // ---------- Topics box (tabbed headline list) ----------

  var topicTab = "latest";

  function topicItems(tab) {
    if (tab === "region") {
      return R.getLocation().then(function (loc) { return recentSearch(loc.province.name); });
    }
    return R.api(FEEDS[tab].api);
  }

  function showTopics(tab) {
    topicTab = tab;
    var list = document.getElementById("topic-list");
    var pic = document.getElementById("topic-pic");
    var more = document.getElementById("topic-more");
    var rss = document.getElementById("topic-rss");
    document.querySelectorAll("[data-topic]").forEach(function (b) {
      b.setAttribute("aria-selected", String(b.getAttribute("data-topic") === tab));
    });
    list.innerHTML = "<li>Loading&hellip;</li>";
    pic.innerHTML = "";

    topicItems(tab).then(function (items) {
      if (topicTab !== tab) return;
      items = (items || []).slice(0, 10);
      list.innerHTML = "";
      items.forEach(function (it) {
        var li = el("li", {}, [titleLink(it)].concat(icons(it)));
        li.appendChild(el("time", { text: R.shortDate(it.published_date) }));
        list.appendChild(li);
      });
      if (!items.length) list.innerHTML = "<li>No stories right now.</li>";
      var lead = items.filter(function (it) { return it.thumbnail; })[0];
      if (lead) {
        pic.appendChild(thumb(lead, true));
        pic.appendChild(titleLink(lead));
      }
      return tab === "region" ? R.getLocation() : null;
    }).then(function (loc) {
      if (topicTab !== tab) return;
      if (loc) {
        more.href = "/?q=" + encodeURIComponent(loc.province.name);
        more.setAttribute("data-q", loc.province.name);
        more.removeAttribute("data-feed");
        rss.href = "/rss.xml?q=" + encodeURIComponent(loc.province.name);
      } else {
        more.href = "/?feed=" + tab;
        more.setAttribute("data-feed", tab);
        more.removeAttribute("data-q");
        rss.href = "/rss.xml" + (tab === "latest" ? "" : "?feed=" + tab);
      }
    }).catch(function () {
      list.innerHTML = "<li>Could not load stories.</li>";
    });
  }

  // ---------- News from your area ----------

  function renderRegion(loc) {
    var name = loc.province.name;
    document.getElementById("region-name").textContent = name;
    var tabLabel = document.getElementById("topic-tab-region");
    if (tabLabel) tabLabel.textContent = name;

    var note = document.getElementById("region-note");
    if (loc.source === "ip") {
      note.textContent = "Detected from your IP address (" + loc.place + "). Not right? Pick your province.";
    } else if (loc.source === "saved") {
      note.textContent = "Showing the province you picked.";
    } else if (loc.source === "abroad" && loc.ip) {
      note.textContent = "You seem to be outside Indonesia (" + [loc.ip.city, loc.ip.country].filter(Boolean).join(", ") + "), so here is " + name + ". Pick a province to change it.";
    } else {
      note.textContent = "Couldn't detect your location, so here is " + name + ".";
    }

    var select = document.getElementById("region-select");
    if (select.options.length < 2) {
      select.innerHTML = "";
      select.appendChild(el("option", { value: "", text: "Auto (IP)" }));
      loc.provinces.forEach(function (p) { select.appendChild(el("option", { value: p.code, text: p.name })); });
    }
    select.value = loc.source === "saved" ? loc.province.code : "";

    document.getElementById("region-more").href = "/?q=" + encodeURIComponent(name);
    document.getElementById("region-more").setAttribute("data-q", name);
    document.getElementById("region-rss").href = "/rss.xml?q=" + encodeURIComponent(name);

    var list = document.getElementById("region-list");
    list.innerHTML = "<li>Loading&hellip;</li>";
    recentSearch(name).then(function (items) {
      list.innerHTML = "";
      items.slice(0, 6).forEach(function (it) {
        list.appendChild(el("li", {}, [
          thumb(it, false),
          el("div", {}, [titleLink(it), el("time", { text: jktDate(it.published_date) })])
        ]));
      });
      if (!items.length) list.innerHTML = "<li>No recent news from " + R.escapeHtml(name) + ".</li>";
    }).catch(function () { list.innerHTML = "<li>Could not load regional news.</li>"; });
  }

  function startRegion() {
    var select = document.getElementById("region-select");
    if (!select) return;
    R.getLocation().then(renderRegion);
    select.addEventListener("change", function () { R.setRegion(select.value); });
    document.addEventListener("kompas:region", function (e) {
      renderRegion(e.detail);
      if (topicTab === "region") showTopics("region");
    });
  }

  // ---------- Topic sections grid ----------

  function startSections() {
    var grid = document.getElementById("section-grid");
    if (!grid) return;
    SECTIONS.forEach(function (sec) {
      var body = el("div", { class: "bx-b", html: "Loading&hellip;" });
      var head = el("div", { class: "bx-h " + sec.c }, [
        el("a", { href: "/?q=" + encodeURIComponent(sec.q), "data-q": sec.q, text: sec.label }),
        el("a", { class: "bx-more", href: "/?q=" + encodeURIComponent(sec.q), "data-q": sec.q, html: "more&raquo;" })
      ]);
      grid.appendChild(el("div", { class: "bx " + sec.c }, [head, body]));

      recentSearch(sec.q).then(function (items) {
        body.className = "";
        body.innerHTML = "";
        if (!items.length) { body.className = "bx-b"; body.textContent = "No stories."; return; }
        var lead = items[0];
        body.appendChild(el("div", { class: "sec-lead" }, [
          thumb(lead, false),
          el("div", {}, [el("b", {}, [titleLink(lead)]), el("div", { class: "meta", text: jktDate(lead.published_date) })])
        ]));
        var ul = el("ul", { class: "sec-list" });
        items.slice(1, 6).forEach(function (it) {
          ul.appendChild(el("li", {}, [titleLink(it)]));
        });
        body.appendChild(ul);
      }).catch(function () { body.textContent = "Could not load."; });
    });
  }

  // ---------- Links that stay on the page ----------

  document.addEventListener("click", function (e) {
    if (e.defaultPrevented || e.button !== 0 || e.metaKey || e.ctrlKey || e.shiftKey || e.altKey) return;
    var t = e.target.closest("[data-topic]");
    if (t) { showTopics(t.getAttribute("data-topic")); return; }
    var f = e.target.closest("[data-feed]");
    if (f) { e.preventDefault(); navigate({ feed: f.getAttribute("data-feed") }); return; }
    var k = e.target.closest("a[data-q]");
    if (k) { e.preventDefault(); navigate({ q: k.getAttribute("data-q") }); return; }
    var pg = e.target.closest("a[data-page]");
    if (pg) { e.preventDefault(); navigate(Object.assign({}, current, { page: parseInt(pg.getAttribute("data-page"), 10) })); return; }
    var a = e.target.closest("a[href]");
    if (!a) return;
    var href = a.getAttribute("href");
    if (href === "/") { e.preventDefault(); navigate({ home: true }); return; }
    if (href === "/#region-box") {
      e.preventDefault();
      var go = current && current.home ? Promise.resolve() : navigate({ home: true });
      go.then(function () { document.getElementById("region-box").scrollIntoView(); });
    }
  });

  var form = document.getElementById("search-form");
  if (form) {
    form.addEventListener("submit", function (e) {
      e.preventDefault();
      var q = searchInput.value.trim();
      navigate(q ? { q: q } : { home: true });
    });
  }

  R.onDatePicked = function (iso) { navigate({ date: iso }); };

  window.addEventListener("popstate", function () { load(stateFromUrl()); });

  // ---------- "You've got news!" pop-up ----------

  function popup() {
    var win = document.getElementById("popup");
    if (!win || !lastItems.length || R.store.get("kompas95.popped", sessionStorage)) return;
    R.store.set("kompas95.popped", "1", sessionStorage);
    var top = lastItems[0];
    document.getElementById("pop-headline").innerHTML = top.title;
    document.getElementById("pop-read").href = R.readLink(top.url);
    win.hidden = false;
    R.makeDraggable(win);
    win.querySelectorAll("[data-close]").forEach(function (b) {
      b.addEventListener("click", function () { win.hidden = true; });
    });
  }

  // ---------- Boot ----------

  var initial = stateFromUrl();
  history.replaceState(initial, "", location.href);
  if (location.hash === "#region-box") setTimeout(function () { document.getElementById("region-box").scrollIntoView(); }, 300);
  showTopics("latest");
  startRegion();
  startSections();
  load(initial).then(function (items) {
    if (items && initial.home) setTimeout(popup, 5000);
  });
})();

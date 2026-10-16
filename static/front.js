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
  var MONTHS = ["Jan", "Feb", "Mar", "Apr", "Mei", "Jun", "Jul", "Agu", "Sep", "Okt", "Nov", "Des"];
  var NEW_WINDOW_SECS = 3 * 3600;

  var results = document.getElementById("results");
  var sectionTitle = document.getElementById("section-title");
  var sectionMeta = document.getElementById("section-meta");
  var searchInput = document.getElementById("q");
  var requestSeq = 0;
  var lastItems = [];

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

  // Jakarta-local date string from epoch seconds
  function jktDate(epoch) {
    if (!epoch) return "Unknown";
    var d = new Date((epoch + 7 * 3600) * 1000);
    return d.getUTCDate() + " " + MONTHS[d.getUTCMonth()] + " " + d.getUTCFullYear() + ", " +
      R.pad(d.getUTCHours()) + ":" + R.pad(d.getUTCMinutes()) + " WIB";
  }

  function isNew(epoch) {
    return epoch && (Date.now() / 1000 - epoch) < NEW_WINDOW_SECS;
  }

  function byline(authors) {
    return (authors || []).map(function (o) {
      var k = Object.keys(o)[0];
      var v = o[k];
      return "<b>" + k.charAt(0).toUpperCase() + k.slice(1) + ":</b> " + (Array.isArray(v) ? v.join(", ") : v);
    }).join(" &middot; ");
  }

  function thumb(item, eager) {
    var link = el("a", { href: R.readLink(item.url), class: "thumb-frame", "aria-hidden": "true", tabindex: "-1" });
    if (item.thumbnail) {
      var img = el("img", { src: item.thumbnail, alt: "", loading: eager ? "eager" : "lazy", decoding: "async" });
      link.appendChild(R.modemify(img));
    } else {
      link.appendChild(el("span", { class: "thumb-empty", html: "[IMAGE]<br>not available" }));
    }
    return link;
  }

  function storyText(item, paras, headingTag) {
    var wrap = el("div", { class: "story-text" });
    var h = el(headingTag);
    if (isNew(item.published_date)) h.appendChild(el("span", { class: "new", text: "NEW!" }));
    h.appendChild(el("a", { href: R.readLink(item.url), html: item.title || "Untitled" }));
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

  function render(items, label) {
    results.innerHTML = "";
    lastItems = items || [];
    if (!lastItems.length) {
      results.appendChild(el("div", { class: "error-msg", html:
        "<b>404 - No stories found.</b><br>Try another search, or press <i>Reload</i> on your browser." }));
      sectionMeta.textContent = "0 stories";
      return;
    }

    var newest = lastItems.reduce(function (m, it) { return Math.max(m, it.published_date || 0); }, 0);
    sectionMeta.textContent = lastItems.length + " stories" + (newest ? " · Last updated " + jktDate(newest) : "");

    var top = lastItems[0];
    var headline = el("div", { class: "headline" }, [
      el("span", { class: "kicker", text: label === "search" ? "TOP RESULT" : "HEADLINE" }),
      top.thumbnail ? thumb(top, true) : null,
      storyText(top, 3, "h3")
    ]);
    results.appendChild(headline);

    var table = el("table", { class: "stories", role: "presentation" });
    var tbody = el("tbody");
    lastItems.slice(1).forEach(function (item) {
      tbody.appendChild(el("tr", {}, [
        el("td", { class: "story-thumb" }, [thumb(item, false)]),
        el("td", { class: "story-body" }, [storyText(item, 2, "h3")])
      ]));
    });
    table.appendChild(tbody);
    results.appendChild(table);
  }

  function showLoading(what) {
    results.innerHTML = "";
    results.appendChild(el("div", { class: "loading-msg", html:
      '<span class="hourglass" aria-hidden="true">&#8987;</span> Downloading ' + what +
      '&hellip; <span class="blink">please wait</span>' }));
    sectionMeta.textContent = "Contacting host...";
    R.setStatus("Connecting to cds.kompas.id...");
  }

  function setActive(feed) {
    document.querySelectorAll("[data-feed]").forEach(function (b) {
      b.classList.toggle("is-active", b.getAttribute("data-feed") === feed);
    });
  }

  function load(state) {
    var seq = ++requestSeq;
    var api, label;
    if (state.q) {
      api = "/api/article?search=" + encodeURIComponent(state.q);
      label = "search";
      sectionTitle.textContent = "Search: “" + state.q + "”";
      document.title = "KOMPAS Online -- Search: " + state.q;
      setActive(null);
    } else {
      var feed = FEEDS[state.feed] ? state.feed : "latest";
      api = FEEDS[feed].api;
      label = feed;
      sectionTitle.textContent = FEEDS[feed].title;
      document.title = "KOMPAS Online -- " + FEEDS[feed].title;
      setActive(feed);
    }
    if (searchInput) searchInput.value = state.q || "";
    showLoading(state.q ? "search results" : "today's edition");

    return fetch(api, { headers: { "Accept": "application/json" } })
      .then(function (r) { if (!r.ok) throw new Error("HTTP " + r.status); return r.json(); })
      .then(function (items) {
        if (seq !== requestSeq) return null;
        render(items, label);
        R.setStatus();
        return items;
      })
      .catch(function (e) {
        if (seq !== requestSeq) return null;
        results.innerHTML = "";
        results.appendChild(el("div", { class: "error-msg", html:
          "<b>Netscape is unable to locate the server.</b><br>" +
          "The server does not have a DNS entry or the line is busy. (" + e.message + ")<br><br>" +
          '<button class="btn95" type="button" id="retry">Try Again</button>' }));
        document.getElementById("retry").addEventListener("click", function () { load(state); });
        sectionMeta.textContent = "Transfer interrupted!";
        R.setStatus("Transfer interrupted!");
        return null;
      });
  }

  function stateFromUrl() {
    var p = new URLSearchParams(location.search);
    return { feed: p.get("feed") || "latest", q: (p.get("q") || "").trim() };
  }

  function navigate(state) {
    var url = state.q ? "/?q=" + encodeURIComponent(state.q)
      : (state.feed && state.feed !== "latest" ? "/?feed=" + state.feed : "/");
    history.pushState(state, "", url);
    window.scrollTo(0, 0);
    return load(state);
  }

  // Feed buttons + sidebar links + keyword links: no page reload needed
  document.addEventListener("click", function (e) {
    if (e.defaultPrevented || e.button !== 0 || e.metaKey || e.ctrlKey || e.shiftKey || e.altKey) return;
    var f = e.target.closest("[data-feed]");
    if (f) { e.preventDefault(); navigate({ feed: f.getAttribute("data-feed"), q: "" }); return; }
    var k = e.target.closest("a[data-q]");
    if (k) { e.preventDefault(); navigate({ feed: "latest", q: k.getAttribute("data-q") }); }
  });

  var form = document.getElementById("search-form");
  if (form) {
    form.addEventListener("submit", function (e) {
      e.preventDefault();
      var q = searchInput.value.trim();
      navigate({ feed: "latest", q: q });
    });
  }

  window.addEventListener("popstate", function () { load(stateFromUrl()); });

  // ---------- Dial-up splash (once per browser session) ----------
  var DIAL_SCRIPT = [
    [0,    "ATZ",                                     "Initializing modem..."],
    [350,  "OK",                                      null],
    [600,  "ATDT 0-21-KOMPAS",                        "Dialing..."],
    [1300, "CONNECT 28800/V.34/LAPM",                 "Verifying user name and password..."],
    [1900, "PPP: negotiating link...",                "Logging on to network..."],
    [2500, "Downloading today's edition...",          "Connected at 28,800 bps"]
  ];
  var DIAL_TOTAL = 3100;

  function dialUp() {
    var box = document.getElementById("dialup");
    if (!box) return Promise.resolve();
    if (R.REDUCED || R.store.get("kompas95.dialed", sessionStorage)) return Promise.resolve();
    R.store.set("kompas95.dialed", "1", sessionStorage);

    var log = document.getElementById("dial-log");
    var status = document.getElementById("dial-status");
    var bar = document.getElementById("dial-progress");
    var timers = [];
    box.hidden = false;

    return new Promise(function (resolve) {
      function finish() {
        timers.forEach(clearTimeout);
        box.hidden = true;
        resolve();
      }
      DIAL_SCRIPT.forEach(function (step) {
        timers.push(setTimeout(function () {
          log.appendChild(el("div", { text: step[1] }));
          if (step[2]) status.innerHTML = "<b>" + step[2] + "</b>";
        }, step[0]));
      });
      var blocks = 0;
      var maxBlocks = Math.floor((bar.clientWidth - 4) / 12) || 20;
      var iv = setInterval(function () {
        if (blocks >= maxBlocks) return clearInterval(iv);
        bar.appendChild(el("i"));
        blocks++;
      }, DIAL_TOTAL / maxBlocks);
      timers.push(iv);
      timers.push(setTimeout(finish, DIAL_TOTAL + 300));
      box.querySelectorAll("[data-skip]").forEach(function (b) { b.addEventListener("click", finish); });
    });
  }

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
  var dial = dialUp();
  var feed = load(initial);
  Promise.all([dial, feed]).then(function (res) {
    if (res[1] && !initial.q) setTimeout(popup, 4000);
  });
})();

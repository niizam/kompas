/* ==========================================================
   KOMPAS Online -- shared DHTML goodies
   Clock, hit counter, sparkles, ticker, rankings, trending
   keywords, "your area" detection, weather and the calendar.
   ========================================================== */

(function () {
  "use strict";

  var REDUCED = window.matchMedia && window.matchMedia("(prefers-reduced-motion: reduce)").matches;

  // Storage can throw (private mode, blocked cookies...). Never let that break the page.
  var store = {
    get: function (k, s) { try { return (s || localStorage).getItem(k); } catch (e) { return null; } },
    set: function (k, v, s) { try { (s || localStorage).setItem(k, v); } catch (e) { /* ignore */ } },
    del: function (k, s) { try { (s || localStorage).removeItem(k); } catch (e) { /* ignore */ } }
  };

  var DAYS = ["Minggu", "Senin", "Selasa", "Rabu", "Kamis", "Jumat", "Sabtu"];
  var DAYS_SHORT = ["Sun", "Mon", "Tue", "Wed", "Thu", "Fri", "Sat"];
  var MONTHS = ["Januari", "Februari", "Maret", "April", "Mei", "Juni", "Juli",
                "Agustus", "September", "Oktober", "November", "Desember"];

  function pad(n, w) { n = String(n); while (n.length < (w || 2)) n = "0" + n; return n; }

  function jakartaNow() {
    // Wall-clock time in Jakarta (UTC+7), independent of the visitor's own zone
    var now = new Date();
    return new Date(now.getTime() + (now.getTimezoneOffset() + 420) * 60000);
  }

  // YYYY-MM-DD in Jakarta, optionally shifted by a number of days
  function jakartaIso(offsetDays) {
    var d = jakartaNow();
    if (offsetDays) d.setDate(d.getDate() + offsetDays);
    return d.getFullYear() + "-" + pad(d.getMonth() + 1) + "-" + pad(d.getDate());
  }

  // "16/10 16:21" in Jakarta time, from epoch seconds
  function shortDate(epoch) {
    if (!epoch) return "";
    var d = new Date((epoch + 7 * 3600) * 1000);
    return pad(d.getUTCDate()) + "/" + pad(d.getUTCMonth() + 1) + " " + pad(d.getUTCHours()) + ":" + pad(d.getUTCMinutes());
  }

  function readLink(permalink) {
    return "/read?permalink=" + encodeURIComponent(permalink) + "&format=html";
  }

  // Third-party widgets give up after a while instead of spinning forever
  function fetchJson(url, ms) {
    var ctrl = window.AbortController ? new AbortController() : null;
    var timer = ctrl && setTimeout(function () { ctrl.abort(); }, ms || 8000);
    return fetch(url, ctrl ? { signal: ctrl.signal } : {})
      .then(function (r) { if (!r.ok) throw new Error("HTTP " + r.status); return r.json(); })
      .finally(function () { clearTimeout(timer); });
  }

  // One request per URL per page view, shared by every widget that wants it
  var apiCache = {};
  function api(url) {
    if (!apiCache[url]) {
      apiCache[url] = fetch(url, { headers: { "Accept": "application/json" } })
        .then(function (r) { if (!r.ok) throw new Error("HTTP " + r.status); return r.json(); })
        .catch(function (e) { delete apiCache[url]; throw e; });
    }
    return apiCache[url];
  }

  function link(item, cls) {
    var a = document.createElement("a");
    a.href = readLink(item.url);
    a.innerHTML = item.title || "Untitled";
    if (cls) a.className = cls;
    return a;
  }

  // ---------- Clock + hit counter ----------

  function startClock() {
    var dateEl = document.getElementById("today");
    var clockEl = document.getElementById("clock");
    function tick() {
      var d = jakartaNow();
      if (dateEl) dateEl.textContent = DAYS[d.getDay()] + ", " + d.getDate() + " " + MONTHS[d.getMonth()] + " " + d.getFullYear();
      if (clockEl) clockEl.textContent = pad(d.getHours()) + ":" + pad(d.getMinutes()) + ":" + pad(d.getSeconds()) + " WIB";
    }
    tick();
    setInterval(tick, 1000);
  }

  // Counts *your* visits to this site. Webmasters of 1997 would be proud.
  function startCounter() {
    var el = document.getElementById("hit-counter");
    if (!el) return;
    var n = parseInt(store.get("kompas95.hits") || "0", 10) || 0;
    if (!store.get("kompas95.counted", sessionStorage)) {
      n += 1;
      store.set("kompas95.hits", String(n));
      store.set("kompas95.counted", "1", sessionStorage);
    }
    var digits = pad(Math.max(n, 1), 6);
    el.innerHTML = "";
    for (var i = 0; i < digits.length; i++) {
      var s = document.createElement("span");
      s.textContent = digits.charAt(i);
      el.appendChild(s);
    }
    el.setAttribute("aria-label", "Visit number " + n);
  }

  // ---------- Cursor sparkles ----------

  var SPARKS = ["✦", "✧", "★", "·", "*"];
  var SPARK_COLORS = ["#ff0000", "#ffcc00", "#00cc00", "#00ccff", "#ff00ff", "#ff66cc"];
  var sparklesOn = !REDUCED && store.get("kompas95.sparkles") !== "off";
  var lastSpark = 0;

  function onMove(e) {
    if (!sparklesOn) return;
    var t = Date.now();
    if (t - lastSpark < 40) return;
    lastSpark = t;
    var s = document.createElement("span");
    s.className = "sparkle";
    s.textContent = SPARKS[Math.floor(Math.random() * SPARKS.length)];
    s.style.left = (e.clientX + 6) + "px";
    s.style.top = (e.clientY + 6) + "px";
    s.style.color = SPARK_COLORS[Math.floor(Math.random() * SPARK_COLORS.length)];
    s.style.setProperty("--dx", (Math.random() * 30 - 15).toFixed(0) + "px");
    s.setAttribute("aria-hidden", "true");
    document.body.appendChild(s);
    setTimeout(function () { s.remove(); }, 950);
  }

  function startSparkles() {
    document.addEventListener("mousemove", onMove, { passive: true });
    var btn = document.getElementById("toggle-sparkles");
    if (!btn) return;
    function label() { btn.textContent = "Sparkles: " + (sparklesOn ? "ON" : "OFF"); }
    label();
    btn.addEventListener("click", function () {
      sparklesOn = !sparklesOn;
      store.set("kompas95.sparkles", sparklesOn ? "on" : "off");
      label();
    });
  }

  // ---------- Slow-modem image reveal ----------

  function modemify(img) {
    if (REDUCED) return img;
    img.classList.add("modem");
    function done() { img.classList.add("loaded"); }
    if (img.complete && img.naturalWidth) done();
    else {
      img.addEventListener("load", done, { once: true });
      img.addEventListener("error", done, { once: true });
    }
    return img;
  }

  // ---------- Draggable Win95 windows ----------

  function makeDraggable(win) {
    var bar = win.querySelector(".titlebar");
    if (!bar) return;
    var sx, sy, ox, oy;
    bar.addEventListener("pointerdown", function (e) {
      if (e.target.closest("button")) return;
      var r = win.getBoundingClientRect();
      sx = e.clientX; sy = e.clientY; ox = r.left; oy = r.top;
      win.style.left = ox + "px"; win.style.top = oy + "px";
      win.style.right = "auto"; win.style.bottom = "auto";
      bar.setPointerCapture(e.pointerId);
    });
    bar.addEventListener("pointermove", function (e) {
      if (!bar.hasPointerCapture(e.pointerId)) return;
      var x = Math.min(Math.max(0, ox + e.clientX - sx), window.innerWidth - 60);
      var y = Math.min(Math.max(0, oy + e.clientY - sy), window.innerHeight - 30);
      win.style.left = x + "px"; win.style.top = y + "px";
    });
  }

  // ---------- Ticker, rankings ----------

  function fillRanking(id, items, n) {
    var box = document.getElementById(id);
    if (!box) return;
    box.innerHTML = "";
    items.slice(0, n).forEach(function (it) {
      var li = document.createElement("li");
      li.appendChild(link(it));
      box.appendChild(li);
    });
    if (!items.length) box.innerHTML = "<li>Nothing here right now.</li>";
  }

  function startFeeds() {
    var mq = document.getElementById("headline-marquee");

    api("/api/article?type=hot").then(function (items) {
      items = (items || []).filter(function (it) { return it && it.title; });
      if (mq) {
        mq.textContent = items.length
          ? items.slice(0, 30).map(function (it) { return it.title; }).join("  ★  ")
          : "No hot topics available at the moment.";
      }
      fillRanking("hot-box", items, 8);
    }).catch(function () {
      if (mq) mq.textContent = "*** Lost connection to the news wire. Please check your modem. ***";
      fillRanking("hot-box", [], 0);
    });

    api("/api/article?type=popular").then(function (items) {
      fillRanking("ranking", (items || []).filter(function (it) { return it && it.title; }), 10);
    }).catch(function () { fillRanking("ranking", [], 0); });

    startTrending();
  }

  // ---------- Trending keywords (counted across the live feeds) ----------

  // Section/desk names that Kompas mixes into keywords; they'd always win the count
  var KEYWORD_NOISE = /^(desk |x-)|^(foto|tutur visual|nasional|regional|utama|metro|berita|opini|internasional|ekonomi|ekonomi (dan|&) bisnis|olahraga|politik (dan|&) hukum|humaniora|budaya|iptek|lingkungan|nusantara|video|kompas|artikel|kompas\.id|lembar|jeda|kompas urbana)$/i;

  function startTrending() {
    var bar = document.getElementById("trend-bar");
    var inline = document.getElementById("trend-inline");
    if (!bar && !inline) return;
    var feeds = ["/api/article", "/api/article?type=popular", "/api/article?type=hot"];
    Promise.all(feeds.map(function (u) { return api(u).catch(function () { return []; }); }))
      .then(function (lists) {
        var counts = {}, labels = {}, hot = {};
        lists.forEach(function (items, i) {
          (items || []).forEach(function (it) {
            (it.keywords || []).forEach(function (k) {
              var key = k.trim().toLowerCase();
              if (!key || key.length > 40 || KEYWORD_NOISE.test(key)) return;
              counts[key] = (counts[key] || 0) + 1;
              if (!labels[key]) labels[key] = k.trim();
              if (i === 2) hot[key] = true;
            });
          });
        });
        var top = Object.keys(counts).sort(function (a, b) { return counts[b] - counts[a] || (hot[b] ? 1 : 0) - (hot[a] ? 1 : 0); }).slice(0, 10);
        function kwLink(key) {
          var a = document.createElement("a");
          a.href = "/?q=" + encodeURIComponent(labels[key]);
          a.setAttribute("data-q", labels[key]);
          a.textContent = labels[key];
          return a;
        }
        if (bar) {
          bar.innerHTML = "";
          top.forEach(function (key) {
            var li = document.createElement("li");
            li.appendChild(kwLink(key));
            if (hot[key]) {
              var up = document.createElement("span");
              up.className = "up";
              up.textContent = " ▲";
              up.title = "In today's hot topics";
              li.appendChild(up);
            }
            bar.appendChild(li);
          });
          if (!top.length) bar.innerHTML = "<li>No keywords yet</li>";
        }
        if (inline) {
          inline.innerHTML = "";
          top.slice(0, 5).forEach(function (key) { inline.appendChild(kwLink(key)); });
        }
      });
  }

  // ---------- "Your area": province from saved choice, IP, or default ----------
  // IP lookup goes to ipwho.is from the visitor's browser; the result stays in this tab.

  var locationPromise = null;

  function normalize(s) { return String(s || "").toLowerCase().replace(/[^a-z]/g, ""); }

  function matchProvince(provinces, ip) {
    if (!ip || ip.country_code !== "ID") return null;
    var code = String(ip.region_code || "").toUpperCase().replace(/^ID-/, "");
    var region = normalize(ip.region);
    return provinces.filter(function (p) { return p.code === code; })[0] ||
      provinces.filter(function (p) {
        return [p.name].concat(p.aliases || []).some(function (n) { return normalize(n) === region; });
      })[0] || null;
  }

  function lookupIp() {
    var cached = store.get("kompas95.ip", sessionStorage);
    if (cached) { try { return Promise.resolve(JSON.parse(cached)); } catch (e) { /* refetch */ } }
    return fetchJson("https://ipwho.is/", 6000)
      .then(function (ip) {
        if (!ip || ip.success === false) throw new Error("lookup failed");
        var keep = { country: ip.country, country_code: ip.country_code, region: ip.region,
                     region_code: ip.region_code, city: ip.city, latitude: ip.latitude, longitude: ip.longitude };
        store.set("kompas95.ip", JSON.stringify(keep), sessionStorage);
        return keep;
      });
  }

  function getLocation() {
    if (locationPromise) return locationPromise;
    locationPromise = api("/api/regions").then(function (data) {
      var provinces = data.provinces || [];
      var byCode = {};
      provinces.forEach(function (p) { byCode[p.code] = p; });
      var fallback = byCode[data.default] || provinces[0];
      function fromProvince(p, source, extra) {
        return Object.assign({ province: p, provinces: provinces, place: p.capital, lat: p.lat, lon: p.lon, source: source }, extra || {});
      }

      var saved = byCode[store.get("kompas95.region")];
      if (saved) return fromProvince(saved, "saved");

      return lookupIp().then(function (ip) {
        var p = matchProvince(provinces, ip);
        if (p) {
          return fromProvince(p, "ip", {
            place: ip.city || p.capital,
            lat: typeof ip.latitude === "number" ? ip.latitude : p.lat,
            lon: typeof ip.longitude === "number" ? ip.longitude : p.lon,
            ip: ip
          });
        }
        return fromProvince(fallback, "abroad", { ip: ip });
      }).catch(function () { return fromProvince(fallback, "default"); });
    });
    return locationPromise;
  }

  function setRegion(code) {
    if (code) store.set("kompas95.region", code);
    else store.del("kompas95.region");
    locationPromise = null;
    return getLocation().then(function (loc) {
      document.dispatchEvent(new CustomEvent("kompas:region", { detail: loc }));
      return loc;
    });
  }

  // ---------- Weather (Open-Meteo, no key needed) ----------

  var WMO = [
    [[0], "☀️", "Clear"],
    [[1], "🌤️", "Mostly clear"],
    [[2], "⛅", "Partly cloudy"],
    [[3], "☁️", "Overcast"],
    [[45, 48], "🌫️", "Fog / haze"],
    [[51, 53, 55, 56, 57], "🌦️", "Drizzle"],
    [[61, 63, 65, 66, 67], "🌧️", "Rain"],
    [[71, 73, 75, 77, 85, 86], "🌨️", "Snow"],
    [[80, 81, 82], "🌦️", "Showers"],
    [[95, 96, 99], "⛈️", "Thunderstorm"]
  ];
  function wmo(code) {
    for (var i = 0; i < WMO.length; i++) if (WMO[i][0].indexOf(code) !== -1) return WMO[i];
    return [[], "❓", "Unknown"];
  }

  var weatherSeq = 0;

  function renderWeather(loc) {
    var box = document.getElementById("weather");
    if (!box) return;
    var seq = ++weatherSeq;
    box.textContent = "Checking the skies…";
    var url = "https://api.open-meteo.com/v1/forecast?latitude=" + loc.lat.toFixed(3) + "&longitude=" + loc.lon.toFixed(3) +
      "&current=temperature_2m,relative_humidity_2m,weather_code" +
      "&daily=weather_code,temperature_2m_max,temperature_2m_min,precipitation_probability_max" +
      "&timezone=auto&forecast_days=3";
    fetchJson(url, 10000)
      .then(function (w) {
        if (seq !== weatherSeq) return;
        var now = w.current || {};
        var cur = wmo(now.weather_code);
        var d = w.daily || {};
        var heads = (d.time || []).map(function (t, i) {
          if (i === 0) return "Today";
          if (i === 1) return "Tmrw";
          var dt = new Date(t + "T00:00:00");
          return DAYS_SHORT[dt.getDay()] + " " + dt.getDate();
        });
        var html = '<div class="wx-place">📍 ' + escapeHtml(loc.place) +
          ' <small>(' + escapeHtml(loc.province.name) + ')</small></div>' +
          '<div class="wx-now"><span class="wx-icon" aria-hidden="true">' + cur[1] + '</span><div>' +
          '<span class="wx-temp">' + Math.round(now.temperature_2m) + '&deg;C</span>' +
          '<div class="wx-desc">' + cur[2] + ' &middot; Humidity ' + Math.round(now.relative_humidity_2m) + '%</div></div></div>' +
          '<table class="wx-days"><tr>' + heads.map(function (h) { return "<th>" + h + "</th>"; }).join("") + "</tr><tr>" +
          heads.map(function (_, i) {
            var c = wmo(d.weather_code[i]);
            return '<td title="' + c[2] + '"><span class="wx-icon" aria-hidden="true">' + c[1] + "</span>" +
              '<span class="wx-hi">' + Math.round(d.temperature_2m_max[i]) + '</span>/<span class="wx-lo">' +
              Math.round(d.temperature_2m_min[i]) + "</span><br>" +
              '<span class="wx-rain">☂' + (d.precipitation_probability_max[i] == null ? "-" : d.precipitation_probability_max[i]) + "%</span></td>";
          }).join("") + "</tr></table>" +
          '<div class="wx-src">Open-Meteo &middot; ' + escapeHtml((now.time || "").slice(11)) + " local</div>";
        box.innerHTML = html;
      })
      .catch(function () {
        if (seq === weatherSeq) box.innerHTML = "Weather service is unreachable.<br><small>Try again later.</small>";
      });
  }

  function escapeHtml(s) {
    return String(s == null ? "" : s).replace(/[&<>"']/g, function (c) {
      return { "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;", "'": "&#39;" }[c];
    });
  }

  function startWeather() {
    if (!document.getElementById("weather")) return;
    getLocation().then(renderWeather);
    document.addEventListener("kompas:region", function (e) { renderWeather(e.detail); });
  }

  // ---------- News calendar (flatpickr + Nager.Date holidays) ----------

  var holidays = {};
  var holidayYears = {};

  function loadHolidays(year) {
    if (holidayYears[year]) return holidayYears[year];
    var key = "kompas95.hol." + year;
    var cached = store.get(key);
    var p = cached
      ? Promise.resolve(JSON.parse(cached))
      : fetchJson("https://date.nager.at/api/v3/PublicHolidays/" + year + "/ID")
          .then(function (list) {
            var slim = list.map(function (h) { return { date: h.date, name: h.localName || h.name }; });
            store.set(key, JSON.stringify(slim));
            return slim;
          });
    holidayYears[year] = p.then(function (list) {
      list.forEach(function (h) { holidays[h.date] = h.name; });
    }).catch(function () { delete holidayYears[year]; });
    return holidayYears[year];
  }

  function isoOf(d) { return d.getFullYear() + "-" + pad(d.getMonth() + 1) + "-" + pad(d.getDate()); }

  function listHolidays(fp) {
    var ul = document.getElementById("holiday-list");
    if (!ul) return;
    var prefix = fp.currentYear + "-" + pad(fp.currentMonth + 1) + "-";
    ul.innerHTML = "";
    Object.keys(holidays).sort().forEach(function (iso) {
      if (iso.indexOf(prefix) !== 0) return;
      var li = document.createElement("li");
      li.innerHTML = "<b>" + parseInt(iso.slice(8), 10) + "</b> " + escapeHtml(holidays[iso]);
      ul.appendChild(li);
    });
  }

  function startCalendar() {
    var el = document.getElementById("news-calendar");
    if (!el || typeof window.flatpickr !== "function") return;
    var locale = Object.assign({}, (window.flatpickr.l10ns && window.flatpickr.l10ns.id) || {}, { firstDayOfWeek: 0 });
    var picked = new URLSearchParams(location.search).get("date");

    var fp = window.flatpickr(el, {
      inline: true,
      locale: locale,
      dateFormat: "Y-m-d",
      minDate: "2017-01-01",
      maxDate: jakartaIso(),
      defaultDate: /^\d{4}-\d{2}-\d{2}$/.test(picked || "") ? picked : null,
      onDayCreate: function (_, __, ___, day) {
        var d = day.dateObj;
        var iso = isoOf(d);
        if (d.getDay() === 0) day.classList.add("is-sun");
        if (d.getDay() === 6) day.classList.add("is-sat");
        if (holidays[iso]) { day.classList.add("is-holiday"); day.title = holidays[iso]; }
      },
      onChange: function (_, iso) {
        if (!iso) return;
        if (typeof Retro.onDatePicked === "function") Retro.onDatePicked(iso);
        else location.href = "/?date=" + iso;
      },
      onMonthChange: function () { refresh(); },
      onYearChange: function () { refresh(); }
    });

    function refresh() {
      loadHolidays(fp.currentYear).then(function () { fp.redraw(); listHolidays(fp); });
    }
    refresh();
    Retro.calendar = fp;
  }

  // ---------- Reader poll ----------

  var POLL_ANSWERS = {
    yes: "Welcome to the future! Don't forget to check your inbox weekly.",
    soon: "Good idea. We hear it will be big.",
    what: "It's like a letter, but through your telephone line!"
  };

  function startPoll() {
    var poll = document.getElementById("poll");
    var form = document.getElementById("poll-form");
    if (!poll || !form) return;
    function thank(v) {
      form.remove();
      var p = document.createElement("p");
      p.innerHTML = '<span class="poll-thanks">Thank you for voting!</span><br>' +
        (POLL_ANSWERS[v] || "") + "<br><small>Results will be published in next week's edition.</small>";
      poll.appendChild(p);
    }
    var prior = store.get("kompas95.vote");
    if (prior) { thank(prior); return; }
    form.addEventListener("submit", function (e) {
      e.preventDefault();
      var choice = form.querySelector("input[name=vote]:checked");
      if (!choice) { alert("Please pick an answer before voting!"); return; }
      store.set("kompas95.vote", choice.value);
      thank(choice.value);
    });
  }

  // Exposed for page scripts
  var Retro = window.Retro = {
    REDUCED: REDUCED,
    store: store,
    api: api,
    modemify: modemify,
    makeDraggable: makeDraggable,
    readLink: readLink,
    escapeHtml: escapeHtml,
    jakartaNow: jakartaNow,
    jakartaIso: jakartaIso,
    shortDate: shortDate,
    getLocation: getLocation,
    setRegion: setRegion,
    pad: pad,
    onDatePicked: null,
    calendar: null
  };

  function init() {
    startClock();
    startCounter();
    startSparkles();
    startFeeds();
    startWeather();
    startCalendar();
    startPoll();
    document.querySelectorAll("img[data-modem]").forEach(modemify);
  }

  if (document.readyState === "loading") document.addEventListener("DOMContentLoaded", init);
  else init();
})();

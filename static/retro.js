/* ==========================================================
   KOMPAS Online -- shared DHTML goodies
   Clock, hit counter, cursor sparkles, MIDI jukebox,
   and a Netscape-style status bar.
   ========================================================== */

(function () {
  "use strict";

  var REDUCED = window.matchMedia && window.matchMedia("(prefers-reduced-motion: reduce)").matches;

  // Storage can throw (private mode, blocked cookies...). Never let that break the page.
  var store = {
    get: function (k, s) { try { return (s || localStorage).getItem(k); } catch (e) { return null; } },
    set: function (k, v, s) { try { (s || localStorage).setItem(k, v); } catch (e) { /* ignore */ } }
  };

  var DAYS = ["Minggu", "Senin", "Selasa", "Rabu", "Kamis", "Jumat", "Sabtu"];
  var MONTHS = ["Januari", "Februari", "Maret", "April", "Mei", "Juni", "Juli",
                "Agustus", "September", "Oktober", "November", "Desember"];

  function jakartaNow() {
    // Wall-clock time in Jakarta (UTC+7), independent of the visitor's own zone
    var now = new Date();
    return new Date(now.getTime() + (now.getTimezoneOffset() + 420) * 60000);
  }
  function pad(n, w) { n = String(n); while (n.length < (w || 2)) n = "0" + n; return n; }

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

  // Hit counter: counts *your* visits to this page. Webmasters of 1997 would be proud.
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

  // ---------- Status bar ----------
  var statusEl, statusIdle = "Document: Done";
  function setStatus(msg) { if (statusEl) statusEl.textContent = msg || statusIdle; }

  function startStatusBar() {
    statusEl = document.getElementById("status-msg");
    if (!statusEl) return;
    setStatus("Contacting host: kompas.id...");
    window.addEventListener("load", function () { setStatus(); });
    document.addEventListener("mouseover", function (e) {
      var a = e.target.closest && e.target.closest("a[href]");
      if (a) setStatus(a.href);
    });
    document.addEventListener("mouseout", function (e) {
      if (e.target.closest && e.target.closest("a[href]")) setStatus();
    });
  }

  // ---------- Cursor sparkles ----------
  var SPARKS = ["✦", "✧", "★", "·", "*"];
  var SPARK_COLORS = ["#ff0000", "#ffcc00", "#00cc00", "#00ccff", "#ff00ff", "#ffffff"];
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
    function label() { btn.textContent = "Cursor sparkles: " + (sparklesOn ? "ON" : "OFF"); }
    label();
    btn.addEventListener("click", function () {
      sparklesOn = !sparklesOn;
      store.set("kompas95.sparkles", sparklesOn ? "on" : "off");
      label();
    });
  }

  // ---------- MIDI jukebox (square waves via Web Audio) ----------
  // An original little loop, "kompas_theme.mid". No real MIDI files were harmed.
  var MELODY = [
    // [midi note or 0 for rest, length in eighths]
    [72, 1], [76, 1], [79, 2], [76, 1], [74, 1], [72, 2],
    [74, 1], [77, 1], [81, 2], [79, 2], [77, 2],
    [76, 1], [79, 1], [84, 2], [83, 1], [81, 1], [79, 2],
    [77, 1], [76, 1], [74, 1], [71, 1], [72, 4],
    [0, 2],
    [79, 1], [79, 1], [81, 1], [79, 1], [77, 2], [76, 2],
    [74, 1], [76, 1], [77, 2], [74, 2], [71, 2],
    [72, 1], [76, 1], [79, 1], [84, 1], [83, 2], [79, 2],
    [81, 1], [79, 1], [77, 1], [74, 1], [72, 4], [0, 2]
  ];
  var BASS = [48, 48, 53, 53, 55, 55, 48, 48, 45, 45, 50, 50, 55, 55, 48, 48];
  var EIGHTH = 0.18;

  var audio = null, playing = false, loopTimer = null;

  function midiToHz(m) { return 440 * Math.pow(2, (m - 69) / 12); }

  function blip(ctx, type, note, start, dur, vol) {
    var osc = ctx.createOscillator();
    var gain = ctx.createGain();
    osc.type = type;
    osc.frequency.value = midiToHz(note);
    gain.gain.setValueAtTime(vol, start);
    gain.gain.exponentialRampToValueAtTime(0.0001, start + dur * 0.95);
    osc.connect(gain).connect(ctx.destination);
    osc.start(start);
    osc.stop(start + dur);
  }

  function scheduleLoop() {
    if (!playing) return;
    var t = audio.currentTime + 0.05;
    var total = 0;
    MELODY.forEach(function (n) {
      if (n[0]) blip(audio, "square", n[0], t + total * EIGHTH, n[1] * EIGHTH, 0.05);
      total += n[1];
    });
    var bassStep = total / BASS.length;
    BASS.forEach(function (b, i) { blip(audio, "triangle", b, t + i * bassStep * EIGHTH, bassStep * EIGHTH, 0.12); });
    loopTimer = setTimeout(scheduleLoop, total * EIGHTH * 1000);
  }

  function startJukebox() {
    var box = document.getElementById("midi");
    if (!box) return;
    var playBtn = document.getElementById("midi-play");
    var stopBtn = document.getElementById("midi-stop");
    var AC = window.AudioContext || window.webkitAudioContext;
    if (!AC) { box.querySelector(".now").textContent = "Your browser does not support MIDI :("; return; }

    playBtn.addEventListener("click", function () {
      if (playing) return;
      audio = audio || new AC();
      if (audio.state === "suspended") audio.resume();
      playing = true;
      box.classList.add("playing");
      setStatus("Playing kompas_theme.mid...");
      scheduleLoop();
    });
    stopBtn.addEventListener("click", function () {
      playing = false;
      clearTimeout(loopTimer);
      box.classList.remove("playing");
      if (audio) { audio.close(); audio = null; }
      setStatus();
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

  function readLink(permalink) {
    return "/read?permalink=" + encodeURIComponent(permalink) + "&format=html";
  }

  // ---------- Breaking-news ticker + "Topik Hangat" box ----------
  function startHotTopics() {
    var mq = document.getElementById("headline-marquee");
    var box = document.getElementById("hot-box");
    if (!mq && !box) return;

    fetch("/api/article?type=hot", { headers: { "Accept": "application/json" } })
      .then(function (r) { if (!r.ok) throw new Error("HTTP " + r.status); return r.json(); })
      .then(function (items) {
        items = (items || []).filter(function (it) { return it && it.title; });
        if (mq) {
          mq.textContent = items.length
            ? items.slice(0, 30).map(function (it) { return it.title; }).join("  ★  ")
            : "No hot topics available at the moment.";
        }
        if (box) {
          box.innerHTML = "";
          items.slice(0, 8).forEach(function (it) {
            var li = document.createElement("li");
            var a = document.createElement("a");
            a.href = readLink(it.url);
            a.innerHTML = it.title;
            li.appendChild(a);
            box.appendChild(li);
          });
          if (!items.length) box.innerHTML = "<li>Nothing hot right now.</li>";
        }
      })
      .catch(function () {
        if (mq) mq.textContent = "*** Lost connection to the news wire. Please check your modem. ***";
        if (box) box.innerHTML = "<li>Could not load topics.</li>";
      });
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
  window.Retro = {
    REDUCED: REDUCED,
    store: store,
    setStatus: setStatus,
    modemify: modemify,
    makeDraggable: makeDraggable,
    readLink: readLink,
    jakartaNow: jakartaNow,
    pad: pad
  };

  function init() {
    startClock();
    startCounter();
    startStatusBar();
    startSparkles();
    startJukebox();
    startHotTopics();
    startPoll();
    document.querySelectorAll("img[data-modem]").forEach(modemify);
  }

  if (document.readyState === "loading") document.addEventListener("DOMContentLoaded", init);
  else init();
})();

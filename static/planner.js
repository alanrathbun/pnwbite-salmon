(function () {
  "use strict";

  function loadPayload() {
    var el = document.getElementById("report-payload");
    if (!el) return null;
    try {
      return JSON.parse(el.textContent);
    } catch (e) {
      console.error("payload parse failed", e);
      return null;
    }
  }

  function getHash() {
    var h = location.hash.replace(/^#/, "");
    var out = {};
    h.split("&").forEach(function (p) {
      var kv = p.split("=");
      if (kv[0]) out[kv[0]] = decodeURIComponent(kv[1] || "");
    });
    return out;
  }

  function setHashKey(key, value) {
    var h = getHash();
    h[key] = value;
    location.hash = Object.keys(h)
      .filter(function (k) { return h[k]; })
      .map(function (k) { return k + "=" + encodeURIComponent(h[k]); })
      .join("&");
  }

  function findEntry(days, dateIso) {
    for (var i = 0; i < days.length; i++) {
      if (days[i].date === dateIso) return days[i];
    }
    return null;
  }

  function pivotLaunchCard(launchEl, payload, dateIso) {
    var launchKey = launchEl.dataset.launch;
    launchEl.querySelectorAll("[data-species-block]").forEach(function (block) {
      var sp = block.dataset.speciesBlock;
      var fkey = sp + "::" + launchKey;
      var days = (payload.forecasts || {})[fkey] || [];
      var entry = findEntry(days, dateIso);
      var heroEl = block.querySelector("[data-hero]");
      if (!heroEl) {
        // Inject one above the day-strip the first time we pivot.
        var strip = block.querySelector(".day-strip");
        if (strip) {
          heroEl = document.createElement("div");
          heroEl.dataset.hero = "1";
          heroEl.className = "hero-stat";
          strip.parentNode.insertBefore(heroEl, strip);
        }
      }
      if (heroEl) {
        if (!entry) {
          heroEl.textContent = "no data";
          heroEl.className = "hero-stat muted";
        } else {
          var open = entry.open !== false;
          heroEl.className = "hero-stat " + entry.verdict;
          heroEl.innerHTML = (open ? "OPEN" : "CLOSED") +
            " &middot; <strong>" + entry.verdict + "</strong>" +
            " (score " + (entry.score || 0).toFixed(2) + ")" +
            (entry.long_range && entry.climatology
              ? ' <span class="muted">typical ' +
                Math.round(entry.climatology.high_f) + "&deg;/" +
                Math.round(entry.climatology.low_f) + "&deg;F</span>"
              : "");
        }
      }
    });
  }

  function applyDate(payload, dateIso) {
    var caption = document.getElementById("picker-caption");
    if (caption) caption.textContent = dateIso;
    var note = document.getElementById("picker-note");
    if (note) {
      var todayIso = payload.today;
      var diff = (Date.parse(dateIso) - Date.parse(todayIso)) / 86400000;
      var msgs = [];
      if (diff > 6) msgs.push("Weather shown is climate-normal, not a forecast.");
      if (payload.pamphlet_expires && dateIso > payload.pamphlet_expires) {
        msgs.push("Regulations beyond " + payload.pamphlet_expires +
          " may not match the next pamphlet edition.");
      }
      note.textContent = msgs.join(" ");
    }
    document.querySelectorAll("[data-launch]").forEach(function (l) {
      pivotLaunchCard(l, payload, dateIso);
    });
  }

  function init() {
    var payload = loadPayload();
    if (!payload) return;
    var picker = document.getElementById("date-picker");
    if (!picker) return;

    var hash = getHash();
    if (hash.date) picker.value = hash.date;
    applyDate(payload, picker.value);

    picker.addEventListener("change", function () {
      setHashKey("date", picker.value);
      applyDate(payload, picker.value);
    });
    window.addEventListener("hashchange", function () {
      var h = getHash();
      if (h.date && h.date !== picker.value) {
        picker.value = h.date;
        applyDate(payload, h.date);
      }
    });

    // Expose for later tasks
    window.__plannerPayload = payload;
  }

  if (document.readyState === "loading") {
    document.addEventListener("DOMContentLoaded", init);
  } else {
    init();
  }
})();

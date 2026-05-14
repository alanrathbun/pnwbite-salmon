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
    var firstEntry = null;
    launchEl.querySelectorAll("[data-species-block]").forEach(function (block) {
      var sp = block.dataset.speciesBlock;
      var fkey = sp + "::" + launchKey;
      var days = (payload.forecasts || {})[fkey] || [];
      var entry = findEntry(days, dateIso);
      if (entry && !firstEntry) firstEntry = entry;
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

    // Update the launch card's top-level banner so it reflects the picked date,
    // not just today. All species at a launch share the same regs section, so
    // the first species' entry is authoritative for open/closed + reason.
    var banner = launchEl.querySelector(".banner-open, .banner-closed");
    if (banner && firstEntry) {
      var open = firstEntry.open !== false;
      var reason = firstEntry.closure_reason || (open ? "default-open" : "closed");
      banner.className = open ? "banner-open" : "banner-closed";
      banner.textContent = (open ? "OPEN · " : "CLOSED — ") + reason;
    }
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

  function fmtPick(pick, options) {
    var opts = options || {};
    var pieces = [];
    if (opts.date) pieces.push(pick.date);
    if (opts.launch) pieces.push(pick.launch);
    if (opts.species) pieces.push(pick.species);
    pieces.push("score " + (pick.score || 0).toFixed(2));
    if (pick.technique) pieces.push(pick.technique);
    return pieces.join(" &middot; ");
  }

  function renderPlannerResults(items, opts) {
    var resultsEl = document.getElementById("planner-results");
    if (!resultsEl) return;
    if (!items || items.length === 0) {
      resultsEl.innerHTML = '<p class="muted">No results.</p>';
      return;
    }
    var ol = ["<ol>"];
    for (var i = 0; i < items.length; i++) {
      ol.push("<li>" + fmtPick(items[i], opts) + "</li>");
    }
    ol.push("</ol>");
    resultsEl.innerHTML = ol.join("");
  }

  function runBestPlaces(payload) {
    var sp = document.querySelector('[data-planner-input="bp-species"]').value;
    var dateIso = document.querySelector('[data-planner-input="bp-date"]').value;
    var byDate = (payload.top_picks_by_date || {})[dateIso] || {};
    var picks = byDate[sp] || [];
    renderPlannerResults(picks, { launch: true });
    return picks.length > 0 ? { picks: picks, mode: "best-places", species: sp, date: dateIso } : null;
  }

  function runBestDates(payload) {
    var launch = document.querySelector('[data-planner-input="bd-launch"]').value;
    var sp = document.querySelector('[data-planner-input="bd-species"]').value;
    var fkey = sp + "::" + launch;
    var days = (payload.forecasts || {})[fkey] || [];
    var openDays = days.filter(function (d) { return d.open !== false; });
    openDays.sort(function (a, b) { return (b.score || 0) - (a.score || 0); });
    var top = openDays.slice(0, 5).map(function (d) {
      var item = { date: d.date, score: d.score };
      if (d.techniques && d.techniques[0]) item.technique = d.techniques[0].label;
      return item;
    });
    renderPlannerResults(top, { date: true });
    return top.length > 0 ? { picks: top, mode: "best-dates", launch: launch, species: sp } : null;
  }

  function runBestMix(payload) {
    var dateIso = document.querySelector('[data-planner-input="bm-date"]').value;
    var byDate = (payload.top_picks_by_date || {})[dateIso] || {};
    var all = [];
    Object.keys(byDate).forEach(function (sp) {
      byDate[sp].forEach(function (p) { all.push(Object.assign({ species: sp }, p)); });
    });
    all.sort(function (a, b) { return (b.score || 0) - (a.score || 0); });
    var top = all.slice(0, 5);
    renderPlannerResults(top, { launch: true, species: true });
    return top.length > 0 ? { picks: top, mode: "best-mix", date: dateIso } : null;
  }

  function verdictFor(score) {
    if (score >= 0.9) return "GREAT";
    if (score >= 0.7) return "GOOD";
    if (score >= 0.5) return "FAIR";
    return "POOR";
  }

  function launchName(payload, key) {
    var l = (payload.launches || []).find ? (payload.launches || []).find(function (x) { return x.key === key; }) : null;
    if (l) return l.name;
    for (var i = 0; i < (payload.launches || []).length; i++) {
      if (payload.launches[i].key === key) return payload.launches[i].name;
    }
    return key;
  }

  function recomputeHeatmap(payload, launchKey) {
    var heatmapEl = document.getElementById("season-heatmap");
    if (!heatmapEl || !launchKey) return;
    var subtitle = heatmapEl.querySelector("p.muted");
    var name = launchName(payload, launchKey);
    if (subtitle) {
      subtitle.innerHTML =
        'Showing scores for <strong>' + name + '</strong>. ' +
        'Red days are closed or out of season for this launch. ' +
        'For best-launch-anywhere by date, use the Trip Planner below.';
    }
    var rows = heatmapEl.querySelectorAll("[data-heat-species]");
    rows.forEach(function (row) {
      var sp = row.dataset.heatSpecies;
      var fkey = sp + "::" + launchKey;
      var days = (payload.forecasts || {})[fkey];
      row.hidden = false;
      var cells = row.querySelectorAll(".heat-cell");
      // No forecast for this (species, launch) means the launch doesn't
      // target that species. Keep the row visible but gray every cell so
      // the heatmap height is consistent across launches.
      if (!days || days.length === 0) {
        cells.forEach(function (cell) {
          var dateIso = cell.dataset.heatDate;
          cell.className = "heat-cell NA";
          cell.title = dateIso + " · " + name + " · not targeted for " + sp + " at this launch";
        });
        return;
      }
      var byDate = {};
      for (var i = 0; i < days.length; i++) byDate[days[i].date] = days[i];
      cells.forEach(function (cell) {
        var dateIso = cell.dataset.heatDate;
        var entry = byDate[dateIso];
        if (!entry) {
          cell.className = "heat-cell POOR";
          cell.title = dateIso + ": no data";
          return;
        }
        var score = entry.open === false ? 0.0 : (entry.score || 0);
        cell.className = "heat-cell " + verdictFor(score);
        var note = entry.open === false
          ? " · closed (" + (entry.closure_reason || "") + ")"
          : "";
        cell.title = dateIso + " · " + name + " · score " + score.toFixed(2) + note;
      });
    });
  }

  function activeMode() {
    var btn = document.querySelector("#planner .tab.active");
    return btn ? btn.dataset.plannerMode : "best-places";
  }

  function showForm(mode) {
    document.querySelectorAll("[data-planner-form]").forEach(function (f) {
      f.hidden = (f.dataset.plannerForm !== mode);
    });
    document.querySelectorAll("#planner .tab").forEach(function (t) {
      t.classList.toggle("active", t.dataset.plannerMode === mode);
    });
  }

  function runActive(payload) {
    var mode = activeMode();
    if (mode === "best-places") return runBestPlaces(payload);
    if (mode === "best-dates") return runBestDates(payload);
    if (mode === "best-mix") return runBestMix(payload);
    return null;
  }

  function pad(n) { return n < 10 ? "0" + n : "" + n; }

  function icsDate(dateIso) {
    // YYYYMMDD for all-day events
    return dateIso.replace(/-/g, "");
  }

  function buildIcs(state) {
    var lines = [
      "BEGIN:VCALENDAR",
      "VERSION:2.0",
      "PRODID:-//pnwbite//salmon planner//EN",
      "CALSCALE:GREGORIAN",
    ];
    var stamp = new Date();
    var dtstamp =
      stamp.getUTCFullYear() +
      pad(stamp.getUTCMonth() + 1) +
      pad(stamp.getUTCDate()) + "T" +
      pad(stamp.getUTCHours()) +
      pad(stamp.getUTCMinutes()) +
      pad(stamp.getUTCSeconds()) + "Z";
    state.picks.forEach(function (p, idx) {
      var date = state.mode === "best-dates" ? p.date : (state.date || p.date);
      if (!date) return;
      var summaryParts = ["pnwbite salmon"];
      if (p.species) summaryParts.push(p.species);
      else if (state.species) summaryParts.push(state.species);
      if (p.launch) summaryParts.push(p.launch);
      else if (state.launch) summaryParts.push(state.launch);
      if (p.score !== undefined) summaryParts.push("score " + p.score.toFixed(2));
      var summary = summaryParts.join(" · ");
      var uid = "pnwbite-" + state.mode + "-" + date + "-" + idx + "@pnwbite.com";
      lines.push("BEGIN:VEVENT");
      lines.push("UID:" + uid);
      lines.push("DTSTAMP:" + dtstamp);
      lines.push("DTSTART;VALUE=DATE:" + icsDate(date));
      lines.push("DTEND;VALUE=DATE:" + icsDate(date));
      lines.push("SUMMARY:" + summary.replace(/[,;\\]/g, "\\$&"));
      if (p.technique) {
        lines.push("DESCRIPTION:Technique\\: " + p.technique.replace(/[,;\\]/g, "\\$&"));
      }
      lines.push("END:VEVENT");
    });
    lines.push("END:VCALENDAR");
    return lines.join("\r\n");
  }

  function downloadIcs(state) {
    var ics = buildIcs(state);
    var blob = new Blob([ics], { type: "text/calendar;charset=utf-8" });
    var url = URL.createObjectURL(blob);
    var a = document.createElement("a");
    a.href = url;
    a.download = "pnwbite-" + state.mode + ".ics";
    document.body.appendChild(a);
    a.click();
    document.body.removeChild(a);
    URL.revokeObjectURL(url);
  }

  function wirePlanner(payload) {
    var btn = document.getElementById("planner-ics");
    var lastState = null;
    function refresh() {
      lastState = runActive(payload);
      if (btn) btn.hidden = !lastState;
    }
    document.querySelectorAll("#planner .tab").forEach(function (t) {
      t.addEventListener("click", function () {
        showForm(t.dataset.plannerMode);
        refresh();
      });
    });
    document.querySelectorAll("[data-planner-input]").forEach(function (inp) {
      inp.addEventListener("change", refresh);
    });
    if (btn) {
      btn.addEventListener("click", function () { if (lastState) downloadIcs(lastState); });
    }
    refresh();
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

    wirePlanner(payload);
    window.__planner = { runActive: runActive, payload: payload };

    // Heatmap reflects whichever launch is selected in the launch dropdown.
    // The legacy IIFE inside _js() restores the launch from localStorage/hash
    // before defer-loaded planner.js runs, so launchSel.value is already set.
    var launchSel = document.getElementById("launch-select");
    if (launchSel) {
      recomputeHeatmap(payload, launchSel.value);
      launchSel.addEventListener("change", function () {
        recomputeHeatmap(payload, launchSel.value);
      });
      // The legacy hashchange handler updates launchSel.value when the URL
      // hash changes; piggyback on that to keep the heatmap in sync.
      window.addEventListener("hashchange", function () {
        recomputeHeatmap(payload, launchSel.value);
      });
    }
  }

  if (document.readyState === "loading") {
    document.addEventListener("DOMContentLoaded", init);
  } else {
    init();
  }
})();

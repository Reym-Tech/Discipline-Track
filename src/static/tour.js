/* Discipline-Track guided tour. Vanilla spotlight engine, no dependencies.
   Non-blocking: the spotlight layer never intercepts clicks, so users can
   keep exploring mid-tour. Seen-state persists per browser (dt-tour-seen).
   The tour only reads and drives the UI; it never creates or edits records. */
(function () {
  "use strict";

  var SEEN_KEY = "dt-tour-seen";
  var PAD = 8;
  var GAP = 14;
  var reduceMotion = window.matchMedia("(prefers-reduced-motion: reduce)").matches;

  var STEPS = {
    "/": [
      { sel: "#audit-table", title: "Severity, sorted",
        body: "Everyone ordered by demerits, then ID \u2014 the highest totals sit at the bottom." },
      { sel: ".view-btn", title: "Open a full record", demo: "firstView",
        body: "The tour opened the first record: history plus the applied sanction." },
      { sel: "#filter-form", title: "Catch the urgent cases", goto: "/log",
        body: "Set a minimum \u2014 3 means suspension-level and up \u2014 then Apply. Continue for the logging screen." }
    ],
    "/log": [
      { sel: "#q", title: "Find the student",
        body: "Type a name or ID; matches appear as you type. The tour runs one next." },
      { sel: "#results", title: "Pick the person", demo: "search",
        body: "The tour picked the first match. In real use, check the demerits beside each name." },
      { sel: "#violation-form", title: "Record it",
        body: "Pick the violation \u2014 points and the consequence apply instantly and save." }
    ]
  };

  function store(key, value) {
    try {
      if (value === null) localStorage.removeItem(key);
      else localStorage.setItem(key, value);
    } catch (e) {}
  }
  function read(key) {
    try { return localStorage.getItem(key); } catch (e) { return null; }
  }
  function visible(el) {
    if (!el || el.hidden) return false;
    var r = el.getBoundingClientRect();
    if (r.width < 2 || r.height < 2) return false;
    var cs = window.getComputedStyle(el);
    return cs.visibility !== "hidden" && cs.display !== "none";
  }
  function firstVisible(sel) {
    var nodes = document.querySelectorAll(sel);
    for (var i = 0; i < nodes.length; i++) {
      if (visible(nodes[i])) return nodes[i];
    }
    return null;
  }
  function waitFor(fn, timeout) {
    return new Promise(function (resolve, reject) {
      var start = Date.now();
      (function poll() {
        var val = null;
        try { val = fn(); } catch (e) { val = null; }
        if (val) { resolve(val); return; }
        if (Date.now() - start > (timeout || 3000)) { reject(new Error("timeout")); return; }
        setTimeout(poll, 120);
      })();
    });
  }

  /* Demo actions: drive the real UI, never write data. */
  var DEMOS = {
    search: function () {
      var q = document.getElementById("q");
      if (!q) return Promise.reject(new Error("no search box"));
      q.value = "a";
      q.dispatchEvent(new Event("input", { bubbles: true }));
      return waitFor(function () {
        return document.querySelector("#results button[data-i]");
      }, 4000).then(function (btn) {
        btn.click();
        return waitFor(function () {
          var box = document.getElementById("selected");
          return box && visible(box) ? box : null;
        }, 3000);
      });
    },
    firstView: function () {
      var btn = firstVisible(".view-btn");
      if (!btn) return Promise.reject(new Error("no rows to open"));
      btn.click();
      return waitFor(function () {
        var body = document.getElementById("detail-body");
        return body && !body.hidden ? body : null;
      }, 3000);
    }
  };

  var spot = null;
  var tip = null;
  var tipTitle = null;
  var tipBody = null;
  var tipCount = null;
  var backBtn = null;
  var nextBtn = null;
  var skipBtn = null;
  var running = false;
  var steps = [];
  var idx = 0;
  var returnFocus = null;
  var settleToken = 0;
  var rafQueued = false;

  function build() {
    spot = document.createElement("div");
    spot.className = "tour-spot";
    spot.hidden = true;
    tip = document.createElement("div");
    tip.className = "tour-tip";
    tip.setAttribute("role", "dialog");
    tip.setAttribute("aria-modal", "false");
    tip.hidden = true;
    tip.innerHTML =
      '<p class="tour-progress" id="tour-count"></p>' +
      '<h2 id="tour-title" tabindex="-1"></h2>' +
      '<p id="tour-body"></p>' +
      '<div class="tour-actions">' +
      '<button type="button" class="btn btn-small" id="tour-back">Back</button>' +
      '<button type="button" class="btn btn-small" id="tour-skip">Skip tour</button>' +
      '<button type="button" class="btn btn-small btn-primary" id="tour-next">Next</button>' +
      "</div>";
    document.body.appendChild(spot);
    document.body.appendChild(tip);
    tipTitle = document.getElementById("tour-title");
    tipBody = document.getElementById("tour-body");
    tipCount = document.getElementById("tour-count");
    backBtn = document.getElementById("tour-back");
    nextBtn = document.getElementById("tour-next");
    skipBtn = document.getElementById("tour-skip");
    tip.setAttribute("aria-labelledby", "tour-title");
    tip.setAttribute("aria-describedby", "tour-body");
    backBtn.addEventListener("click", function () { go(idx - 1); });
    nextBtn.addEventListener("click", function () {
      var step = steps[idx];
      if (step && step.goto) {
        try { sessionStorage.setItem("dt-tour-next", "1"); } catch (e) {}
        store(SEEN_KEY, "1");
        window.location.href = step.goto;
        return;
      }
      go(idx + 1);
    });
    skipBtn.addEventListener("click", end);
    document.addEventListener("keydown", function (ev) {
      if (!running) return;
      if (ev.key === "Escape") { end(); return; }
      if (tip.contains(document.activeElement)) {
        if (ev.key === "ArrowRight") { ev.preventDefault(); go(idx + 1); }
        if (ev.key === "ArrowLeft") { ev.preventDefault(); go(idx - 1); }
      }
    });
    window.addEventListener("resize", requestRedraw);
    window.addEventListener("scroll", requestRedraw, { passive: true, capture: true });
  }

  function requestRedraw() {
    if (!running || rafQueued) return;
    rafQueued = true;
    window.requestAnimationFrame(function () {
      rafQueued = false;
      if (running) draw(steps[idx]);
    });
  }

  function targetOf(step) {
    if (!step.sel) return null;
    return firstVisible(step.sel);
  }

  function draw(step) {
    var el = targetOf(step);
    if (el) {
      var r = el.getBoundingClientRect();
      /* Fixed positioning: viewport-relative rect applies directly. */
      spot.hidden = false;
      spot.style.left = Math.max(4, r.left - PAD) + "px";
      spot.style.top = Math.max(4, r.top - PAD) + "px";
      spot.style.width = r.width + PAD * 2 + "px";
      spot.style.height = r.height + PAD * 2 + "px";
      positionTip(r);
    } else {
      spot.hidden = true;
      centerTip();
    }
  }

  function positionTip(r) {
    tip.style.left = "";
    tip.style.right = "";
    tip.style.top = "";
    tip.style.bottom = "";
    tip.style.transform = "";
    var margin = 12;
    var maxW = Math.min(360, window.innerWidth - margin * 2);
    tip.style.maxWidth = maxW + "px";
    /* Measure with the tip visible off-flow. */
    tip.style.visibility = "hidden";
    tip.hidden = false;
    var tipH = tip.offsetHeight;
    var tipW = tip.offsetWidth;
    tip.style.visibility = "";
    var left = Math.min(Math.max(margin, r.left), window.innerWidth - tipW - margin);
    var below = r.bottom + GAP + tipH + margin;
    if (below <= window.innerHeight) {
      tip.style.left = left + "px";
      tip.style.top = r.bottom + GAP + "px";
    } else {
      tip.style.left = left + "px";
      tip.style.top = Math.max(margin, r.top - GAP - tipH) + "px";
    }
  }

  function centerTip() {
    tip.hidden = false;
    tip.style.left = "50%";
    tip.style.top = "50%";
    tip.style.transform = "translate(-50%, -50%)";
    tip.style.maxWidth = Math.min(380, window.innerWidth - 24) + "px";
  }

  function render(step, total) {
    tipTitle.textContent = step.title;
    tipBody.textContent = step.body;
    tipCount.textContent = "Step " + (idx + 1) + " of " + total;
    backBtn.disabled = idx === 0;
    if (step.goto) nextBtn.textContent = "Next: Log violation";
    else nextBtn.textContent = idx === total - 1 ? "Finish" : "Next";
    tip.hidden = false;
    tipTitle.focus({ preventScroll: true });
  }

  function go(n) {
    if (!running) return;
    if (n >= steps.length) { end(); return; }
    if (n < 0) n = 0;
    /* Walk forward/back to the next step whose target exists. */
    var dir = n >= idx ? 1 : -1;
    var token = ++settleToken;
    (function advance(i) {
      if (token !== settleToken) return;
      if (i < 0 || i >= steps.length) {
        if (dir > 0) end();
        else { idx = 0; present(steps[0], token); }
        return;
      }
      var step = steps[i];
      var proceed = function () {
        if (token !== settleToken) return;
        idx = i;
        present(step, token);
      };
      if (!step.sel) { proceed(); return; }
      if (targetOf(step)) { proceed(); return; }
      if (step.demo && DEMOS[step.demo]) {
        DEMOS[step.demo]().then(proceed, function () { advance(i + dir); });
        return;
      }
      advance(i + dir);
    })(n);
  }

  function present(step, token) {
    render(step, steps.length);
    var el = targetOf(step);
    if (el) {
      try {
        el.scrollIntoView({ block: "center", behavior: reduceMotion ? "auto" : "smooth" });
      } catch (e) {}
      setTimeout(function () {
        if (token === settleToken && running) draw(step);
      }, reduceMotion ? 60 : 420);
      draw(step);
    } else {
      draw(step, false);
    }
  }

  function stepsFor(path) {
    return STEPS[path] || STEPS[path.replace(/\/$/, "")] || [];
  }

  function start() {
    var list = stepsFor(window.location.pathname);
    if (!list.length) return;
    if (!spot) build();
    steps = list;
    idx = 0;
    running = true;
    returnFocus = document.activeElement;
    document.body.classList.add("tour-open");
    go(0);
  }

  function end() {
    settleToken++;
    running = false;
    store(SEEN_KEY, "1");
    document.body.classList.remove("tour-open");
    if (spot) spot.hidden = true;
    if (tip) tip.hidden = true;
    if (returnFocus && document.contains(returnFocus)) {
      try { returnFocus.focus({ preventScroll: true }); } catch (e) {}
    }
  }

  function boot() {
    var trigger = document.getElementById("tour-start");
    if (trigger) trigger.addEventListener("click", start);
    if (!trigger) return;
    var continued = false;
    try {
      continued = sessionStorage.getItem("dt-tour-next") === "1";
      sessionStorage.removeItem("dt-tour-next");
    } catch (e) {}
    if (!continued && read(SEEN_KEY)) return;
    var list = stepsFor(window.location.pathname);
    if (!list.length) return;
    setTimeout(function () {
      if (!continued && read(SEEN_KEY)) return;
      start();
    }, 800);
  }

  if (document.readyState === "loading") {
    document.addEventListener("DOMContentLoaded", boot);
  } else {
    boot();
  }

  window.DisciplineTour = { start: start };
})();

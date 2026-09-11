/* Discipline-Track progressive enhancement. No framework; fetch + inline states. */
(function () {
  "use strict";

  function show(el, msg) {
    if (!el) return;
    el.textContent = msg;
    el.hidden = !msg;
  }

  function pillClass(status) {
    return "pill " + status.toLowerCase().replace(/ /g, "-");
  }

  function esc(s) {
    return String(s).replace(/[&<>"']/g, function (c) {
      return { "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;", "'": "&#39;" }[c];
    });
  }

  /* ---- Display preferences: text size + high contrast, persisted ---- */
  (function prefs() {
    var root = document.documentElement;
    var group = document.getElementById("text-size");
    var toggle = document.getElementById("contrast-toggle");
    if (!group && !toggle) return;

    function store(key, value) {
      try {
        if (value === null) localStorage.removeItem(key);
        else localStorage.setItem(key, value);
      } catch (e) {}
    }

    function applyText(size) {
      if (size === "large" || size === "xl") root.setAttribute("data-text", size);
      else root.removeAttribute("data-text");
      store("dt-text", size === "default" ? null : size);
      if (group) {
        group.querySelectorAll("button[data-size]").forEach(function (btn) {
          btn.setAttribute("aria-pressed", btn.getAttribute("data-size") === size ? "true" : "false");
        });
      }
    }

    function applyContrast(high) {
      if (high) root.setAttribute("data-contrast", "high");
      else root.removeAttribute("data-contrast");
      store("dt-contrast", high ? "1" : null);
      if (toggle) toggle.setAttribute("aria-pressed", high ? "true" : "false");
    }

    if (group) {
      group.addEventListener("click", function (ev) {
        var btn = ev.target.closest("button[data-size]");
        if (btn) applyText(btn.getAttribute("data-size"));
      });
      var current = root.getAttribute("data-text") || "default";
      applyText(current);
    }
    if (toggle) {
      if (root.getAttribute("data-contrast") === "high") toggle.setAttribute("aria-pressed", "true");
      toggle.addEventListener("click", function () {
        applyContrast(root.getAttribute("data-contrast") !== "high");
      });
    }
  })();

  /* ---- Audit screen ---- */
  var filterForm = document.getElementById("filter-form");
  if (filterForm) {
    var auditBody = document.getElementById("audit-body");
    var shownCount = document.getElementById("shown-count");
    var matchCount = document.getElementById("match-count");
    var tableNote = document.getElementById("table-note");

    auditBody.addEventListener("click", function (ev) {
      var btn = ev.target.closest(".view-btn");
      if (btn) loadDetail(btn.getAttribute("data-sid"), null);
    });

    filterForm.addEventListener("submit", function (ev) {
      ev.preventDefault();
      var min = document.getElementById("min").value || "0";
      var limit = document.getElementById("limit").value || "500";
      show(document.getElementById("filter-error"), "");
      auditBody.innerHTML = '<tr><td colspan="6" class="empty">Loading filtered records…</td></tr>';
      fetch("/api/audit?min_demerits=" + encodeURIComponent(min) + "&limit=" + encodeURIComponent(limit))
        .then(function (res) {
          if (!res.ok) throw new Error("Filter request failed (" + res.status + "). Check the numbers and retry.");
          return res.json();
        })
        .then(function (body) {
          if (!body.students.length) {
            auditBody.innerHTML = '<tr><td colspan="6" class="empty">No students meet this threshold. Lower the minimum and retry.</td></tr>';
          } else {
            auditBody.innerHTML = body.students.map(function (r) {
              return '<tr data-sid="' + r.student_id + '"><td class="num">' + r.student_id + "</td><td>" +
                esc(r.name) + "</td><td>" + esc(r.course) + '</td><td class="num">' + r.total_demerits +
                '</td><td><span class="' + pillClass(r.status) + '">' + esc(r.status) + '</span></td>' +
                '<td><button type="button" class="btn btn-small view-btn" data-sid="' + r.student_id + '">View</button></td></tr>';
            }).join("");
          }
          shownCount.textContent = body.returned;
          matchCount.textContent = body.total;
          var capped = body.returned < body.total;
          tableNote.hidden = !capped;
          if (capped) tableNote.textContent = "Showing " + body.returned + " of " + body.total + " matches; raise the row limit to see more.";
        })
        .catch(function (err) { show(document.getElementById("filter-error"), err.message); });
    });
  }

  function loadDetail(sid, selectBtn) {
    var empty = document.getElementById("detail-empty");
    var body = document.getElementById("detail-body");
    if (!empty || !body) return;
    show(document.getElementById("detail-error"), "");
    empty.textContent = "Loading student " + sid + "…";
    body.hidden = true;
    fetch("/api/students/" + encodeURIComponent(sid))
      .then(function (res) {
        if (!res.ok) throw new Error("Student " + sid + " could not be loaded.");
        return res.json();
      })
      .then(function (r) {
        empty.hidden = true;
        body.hidden = false;
        document.getElementById("d-name").textContent = r.name;
        document.getElementById("d-id").textContent = "· ID " + r.student_id;
        document.getElementById("d-meta").textContent = (r.course || "No course") + " · " + r.total_demerits + " demerits";
        document.getElementById("d-status").innerHTML = '<span class="' + pillClass(r.status) + '">' + esc(r.status) + "</span> " + esc(r.sanction);
        document.getElementById("d-history").innerHTML = r.history.length
          ? r.history.map(function (h) {
              return "<li><code>" + esc(h.code) + "</code> (+" + h.points + ") — " + esc(h.description) + "</li>";
            }).join("")
          : "<li>No violations recorded.</li>";
        if (selectBtn) {
          document.querySelectorAll(".view-btn").forEach(function (b) { b.removeAttribute("aria-current"); });
          selectBtn.setAttribute("aria-current", "true");
        }
      })
      .catch(function (err) {
        empty.textContent = "Nothing selected. Use View on any row.";
        show(document.getElementById("detail-error"), err.message);
      });
  }

  /* ---- Log screen ---- */
  var q = document.getElementById("q");
  if (q) {
    var results = document.getElementById("results");
    var selectedBox = document.getElementById("selected");
    var outcome = document.getElementById("outcome");
    var chosen = null;
    var timer = null;
    var inflight = null;

    q.addEventListener("input", function () {
      clearTimeout(timer);
      var query = q.value.trim();
      results.innerHTML = "";
      show(document.getElementById("search-error"), "");
      if (!query) return;
      timer = setTimeout(function () {
        if (inflight) inflight.abort();
        inflight = new AbortController();
        fetch("/api/students?q=" + encodeURIComponent(query), { signal: inflight.signal })
          .then(function (res) {
            if (!res.ok) throw new Error("Search failed (" + res.status + "). Retry.");
            return res.json();
          })
          .then(function (body) {
            results.innerHTML = body.students.length
              ? body.students.map(function (r, i) {
                  return '<li><button type="button" data-i="' + i + '" aria-selected="false"><strong>' +
                    esc(r.name) + "</strong> · ID " + r.student_id +
                    ' <span class="r-meta">' + r.total_demerits + " demerits · " + esc(r.status) + "</span></button></li>";
                }).join("")
              : "<li class=\"note\">No matches. Check the spelling or register the student on this page.</li>";
            results.querySelectorAll("button[data-i]").forEach(function (btn) {
              btn.addEventListener("click", function () { choose(body.students[Number(btn.getAttribute("data-i"))], btn); });
            });
          })
          .catch(function (err) {
            if (err.name !== "AbortError") show(document.getElementById("search-error"), err.message);
          });
      }, 180);
    });

    function choose(r, btn) {
      chosen = r;
      results.querySelectorAll("button").forEach(function (b) { b.setAttribute("aria-selected", "false"); });
      btn.setAttribute("aria-selected", "true");
      selectedBox.hidden = false;
      outcome.hidden = true;
      show(document.getElementById("log-error"), "");
      document.getElementById("s-name").textContent = r.name;
      document.getElementById("s-id").textContent = "· ID " + r.student_id;
      document.getElementById("s-meta").textContent = (r.course || "No course") + " · currently " + r.total_demerits + " demerits (" + r.status + ")";
      document.getElementById("code").focus();
    }

    document.getElementById("violation-form").addEventListener("submit", function (ev) {
      ev.preventDefault();
      if (!chosen) return;
      var code = document.getElementById("code").value;
      var desc = document.getElementById("desc").value.trim();
      show(document.getElementById("log-error"), "");
      fetch("/api/violations", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ student_id: chosen.student_id, code: code, description: desc })
      })
        .then(function (res) {
          return res.json().then(function (body) {
            if (!res.ok) throw new Error(body.error || "Logging failed.");
            return body;
          });
        })
        .then(function (body) {
          chosen = body.record;
          outcome.hidden = false;
          outcome.innerHTML = "<strong>" + esc(body.consequence.status) + " — " + esc(body.consequence.sanction) + "</strong>" +
            esc(chosen.name) + " now carries " + chosen.total_demerits + " demerits.";
          document.getElementById("s-meta").textContent = (chosen.course || "No course") + " · currently " + chosen.total_demerits + " demerits (" + chosen.status + ")";
          document.getElementById("desc").value = "";
        })
        .catch(function (err) { show(document.getElementById("log-error"), err.message); });
    });

    document.getElementById("register-form").addEventListener("submit", function (ev) {
      ev.preventDefault();
      show(document.getElementById("register-error"), "");
      var msg = document.getElementById("register-msg");
      msg.textContent = "";
      fetch("/api/students", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({
          student_id: Number(document.getElementById("r-id").value),
          name: document.getElementById("r-name").value.trim(),
          course: document.getElementById("r-course").value.trim()
        })
      })
        .then(function (res) {
          return res.json().then(function (body) {
            if (!res.ok) throw new Error(body.error || "Registration failed.");
            return body;
          });
        })
        .then(function (body) {
          msg.textContent = "Registered " + body.name + " (ID " + body.student_id + "). Search above to log their first offense.";
          ev.target.reset();
          document.getElementById("r-course").value = "BSIT-1A";
        })
        .catch(function (err) { show(document.getElementById("register-error"), err.message); });
    });
  }
})();

/* Discipline-Track floating nav. Toggles .is-scrolled on .topbar with
   enter/exit hysteresis so micro-scrolls and overscroll bounce around a
   single threshold can't flicker the state. rAF-throttled, passive,
   progressive enhancement: no-JS keeps the static bar. */
(function () {
  "use strict";

  var ENTER_AT = 40;
  var EXIT_AT = 15;

  function init() {
    var bar = document.querySelector(".topbar");
    if (!bar) return;
    var ticking = false;

    function apply() {
      ticking = false;
      var y = window.scrollY || document.documentElement.scrollTop || 0;
      var isScrolled = bar.classList.contains("is-scrolled");
      var next = isScrolled ? y > EXIT_AT : y > ENTER_AT;
      if (next !== isScrolled) {
        bar.classList.toggle("is-scrolled", next);
      }
    }

    function request() {
      if (!ticking) {
        ticking = true;
        window.requestAnimationFrame(apply);
      }
    }

    apply();
    window.addEventListener("scroll", request, { passive: true });
    window.addEventListener("resize", request);
  }

  if (document.readyState === "loading") {
    document.addEventListener("DOMContentLoaded", init);
  } else {
    init();
  }
})();

/* شاي بو حمد — progressive enhancement only.
   Every piece of content is in the HTML already; this file adds polish.
   If it fails to load, the site still reads and still works. */
(function () {
  "use strict";

  // Flips the no-js class the document ships with, so [data-reveal] elements
  // stay visible for anyone without JavaScript instead of being stuck at
  // opacity:0 — a genuinely easy way to ship an invisible page.
  document.documentElement.classList.remove("no-js");

  var reduceMotion = window.matchMedia("(prefers-reduced-motion: reduce)").matches;

  /* ---------------------------------------------------- reveal on scroll */
  var revealables = document.querySelectorAll("[data-reveal]");
  if (!("IntersectionObserver" in window) || reduceMotion) {
    revealables.forEach(function (el) { el.classList.add("is-visible"); });
  } else {
    var revealObserver = new IntersectionObserver(function (entries) {
      entries.forEach(function (entry) {
        if (!entry.isIntersecting) return;
        entry.target.classList.add("is-visible");
        revealObserver.unobserve(entry.target);   // reveal once, then stop
      });
    }, { rootMargin: "0px 0px -12% 0px", threshold: 0.08 });

    revealables.forEach(function (el) { revealObserver.observe(el); });
  }

  /* ------------------------------------------- header condense + progress */
  var header = document.getElementById("header");
  var pour = document.querySelector(".pour");
  var ticking = false;

  function onScroll() {
    var y = window.scrollY || window.pageYOffset;

    if (header) header.classList.toggle("is-condensed", y > 40);

    if (pour) {
      var scrollable = document.documentElement.scrollHeight - window.innerHeight;
      // scaleX with a transform-origin of inline-start handles RTL for us —
      // no sign flipping needed, unlike a translateX-based indicator.
      pour.style.setProperty("--progress", scrollable > 0 ? y / scrollable : 0);
    }
    ticking = false;
  }

  window.addEventListener("scroll", function () {
    if (ticking) return;
    ticking = true;
    window.requestAnimationFrame(onScroll);
  }, { passive: true });
  onScroll();

  /* ------------------------------------------------ active nav highlight */
  var sections = Array.prototype.slice.call(
    document.querySelectorAll("main section[id]")
  );
  var navLinks = {};
  document.querySelectorAll(".nav a[href^='#']").forEach(function (a) {
    navLinks[a.getAttribute("href").slice(1)] = a;
  });

  if ("IntersectionObserver" in window && sections.length) {
    var navObserver = new IntersectionObserver(function (entries) {
      entries.forEach(function (entry) {
        var link = navLinks[entry.target.id];
        if (!link) return;
        if (entry.isIntersecting) {
          Object.keys(navLinks).forEach(function (k) {
            navLinks[k].removeAttribute("aria-current");
          });
          link.setAttribute("aria-current", "true");
        }
      });
    }, { rootMargin: "-45% 0px -50% 0px" });
    sections.forEach(function (s) { navObserver.observe(s); });
  }

  /* ----------------------------------------------------- menu filtering */
  var filters = document.querySelectorAll(".filter");
  var menuItems = document.querySelectorAll("[data-category]");

  filters.forEach(function (button) {
    button.addEventListener("click", function () {
      var wanted = button.dataset.filter;

      filters.forEach(function (b) {
        b.setAttribute("aria-pressed", String(b === button));
      });

      menuItems.forEach(function (item) {
        var show = wanted === "all" || item.dataset.category === wanted;
        item.hidden = !show;
      });
    });
  });

  /* ------------------------------------------------------------- footer */
  var year = document.getElementById("year");
  if (year) year.textContent = new Date().getFullYear();
})();

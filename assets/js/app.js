/* شاي بو حمد — progressive enhancement only.
   All content is in the HTML already; this file adds polish. If it fails to
   load, the page still reads and still works. */
(function () {
  "use strict";

  // The document ships with class="no-js" so [data-reveal] elements stay
  // visible for anyone without JavaScript, instead of being stuck at
  // opacity:0 — an easy way to ship an invisible page.
  document.documentElement.classList.remove("no-js");

  var reduce = window.matchMedia("(prefers-reduced-motion: reduce)").matches;
  var hasIO = "IntersectionObserver" in window;

  /* ---------------------------------------------------- reveal on scroll */
  var revealables = document.querySelectorAll("[data-reveal]");
  if (!hasIO || reduce) {
    revealables.forEach(function (el) { el.classList.add("is-visible"); });
  } else {
    var revealObserver = new IntersectionObserver(function (entries) {
      entries.forEach(function (entry) {
        if (!entry.isIntersecting) return;
        entry.target.classList.add("is-visible");
        revealObserver.unobserve(entry.target);      // reveal once
      });
    }, { rootMargin: "0px 0px -10% 0px", threshold: 0.06 });
    revealables.forEach(function (el) { revealObserver.observe(el); });
  }

  /* --------------------------------- header, progress bar, band parallax */
  var header = document.getElementById("header");
  var pour = document.querySelector(".pour");
  var parallaxLayers = Array.prototype.slice.call(
    document.querySelectorAll("[data-parallax]")
  );
  var ticking = false;

  function frame() {
    var y = window.scrollY || window.pageYOffset;

    if (header) header.classList.toggle("is-stuck", y > 60);

    if (pour) {
      var scrollable = document.documentElement.scrollHeight - window.innerHeight;
      pour.style.setProperty("--progress", scrollable > 0 ? y / scrollable : 0);
    }

    // Parallax via transform, never background-attachment: fixed — that forces
    // a full background repaint every frame and makes scrolling stutter.
    if (!reduce) {
      var vh = window.innerHeight;
      parallaxLayers.forEach(function (layer) {
        var band = layer.parentElement;
        var rect = band.getBoundingClientRect();
        if (rect.bottom < 0 || rect.top > vh) return;      // off-screen
        var progress = (rect.top + rect.height / 2 - vh / 2) / vh;
        layer.style.transform = "translate3d(0," + (progress * -40).toFixed(2) + "px,0)";
      });
    }

    ticking = false;
  }

  window.addEventListener("scroll", function () {
    if (ticking) return;
    ticking = true;
    window.requestAnimationFrame(frame);
  }, { passive: true });
  window.addEventListener("resize", frame, { passive: true });
  frame();

  /* ------------------------------------------------ active nav highlight */
  var navLinks = {};
  document.querySelectorAll(".nav a[href^='#']").forEach(function (a) {
    navLinks[a.getAttribute("href").slice(1)] = a;
  });
  var sections = document.querySelectorAll("main section[id]");

  if (hasIO && sections.length) {
    var navObserver = new IntersectionObserver(function (entries) {
      entries.forEach(function (entry) {
        if (!entry.isIntersecting) return;
        var link = navLinks[entry.target.id];
        Object.keys(navLinks).forEach(function (k) {
          navLinks[k].removeAttribute("aria-current");
        });
        if (link) link.setAttribute("aria-current", "true");
      });
    }, { rootMargin: "-45% 0px -50% 0px" });
    sections.forEach(function (s) { navObserver.observe(s); });
  }

  /* ------------------------------------------------------- mouse tilt */
  // Skipped on touch devices: there is no pointer to follow, and the listener
  // would only cost battery.
  if (!reduce && window.matchMedia("(hover: hover) and (pointer: fine)").matches) {
    document.querySelectorAll("[data-tilt]").forEach(function (el) {
      el.addEventListener("mousemove", function (e) {
        var r = el.getBoundingClientRect();
        var px = (e.clientX - r.left) / r.width - 0.5;
        var py = (e.clientY - r.top) / r.height - 0.5;
        el.style.setProperty("--ry", (px * 7).toFixed(2) + "deg");
        el.style.setProperty("--rx", (-py * 7).toFixed(2) + "deg");
      });
      el.addEventListener("mouseleave", function () {
        el.style.setProperty("--ry", "0deg");
        el.style.setProperty("--rx", "0deg");
      });
    });
  }

  /* ---------------------------------------------------- menu filtering */
  var filters = document.querySelectorAll(".filter");
  var items = document.querySelectorAll("[data-category]");

  filters.forEach(function (button) {
    button.addEventListener("click", function () {
      var wanted = button.dataset.filter;
      filters.forEach(function (b) {
        b.setAttribute("aria-pressed", String(b === button));
      });
      items.forEach(function (item) {
        item.hidden = !(wanted === "all" || item.dataset.category === wanted);
      });
    });
  });

  /* ------------------------------------------------------------ footer */
  var year = document.getElementById("year");
  if (year) year.textContent = new Date().getFullYear();
})();

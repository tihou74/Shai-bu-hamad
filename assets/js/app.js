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

  /* ------------------------------------------------------ intro curtain */
  // Plays once per browsing session. Nobody wants a title sequence every
  // time they tap back, and reduced-motion users should never see one.
  (function intro() {
    var el = document.getElementById("intro");
    if (!el) return;

    var seen = false;
    try { seen = sessionStorage.getItem("sbh-intro") === "1"; } catch (e) { seen = false; }
    if (seen || reduce) {
      el.remove();
      return;
    }

    el.classList.add("is-playing");
    document.documentElement.classList.add("is-intro-locked");

    function lift() {
      el.classList.add("is-leaving");
      document.documentElement.classList.remove("is-intro-locked");
      try { sessionStorage.setItem("sbh-intro", "1"); } catch (e) { /* private mode */ }
      // Removed rather than left stacked: a fixed full-screen element that
      // stays in the tree keeps its compositing layer alive for nothing.
      window.setTimeout(function () { el.remove(); }, 1300);
    }

    var timer = window.setTimeout(lift, 2400);
    // Any intent to move on skips the rest of it.
    ["wheel", "touchstart", "keydown", "click"].forEach(function (evt) {
      window.addEventListener(evt, function once() {
        window.clearTimeout(timer);
        lift();
        window.removeEventListener(evt, once);
      }, { passive: true, once: true });
    });
  })();

  /* ------------------------------------------------------------- reels */
  // The owner's clips, at 9:16, playing only while they are on screen.
  //
  // There was a full-bleed hero video here before. It was removed because
  // every clip in media/video/ is a vertical phone recording at 480-720px
  // wide, and stretching one across a desktop hero upscaled it about 3x.
  //
  // Two details earn their keep. Nothing is fetched until a card is close to
  // the viewport, so opening the page costs no video bytes at all. And three
  // of the clips open on black or on a burnt-in title card, so each carries a
  // data-start in-point and is looped from there rather than from zero — a
  // row of black rectangles is what a naive loop would give.
  (function reels() {
    var cards = document.querySelectorAll(".reel-card video");
    if (!cards.length) return;

    var net = navigator.connection || {};
    var thrifty = net.saveData ||
                  /(^|-)(2g|slow-2g)$/.test(net.effectiveType || "");

    // A still frame is the whole experience for reduced-motion and metered
    // connections: fetch metadata so the first frame can be shown, and never
    // call play().
    if (reduce || thrifty) {
      cards.forEach(function (v) {
        v.removeAttribute("loop");
        v.preload = "metadata";
      });
      return;
    }

    if (!hasIO) return;

    // Decode only what is visible. Six simultaneous video decodes is the
    // kind of thing that turns a phone into a hand warmer.
    var io = new IntersectionObserver(function (entries) {
      entries.forEach(function (entry) {
        var v = entry.target;
        if (entry.isIntersecting && !reduce && !thrifty) {
          v.play().catch(function () { /* autoplay refused: leave the frame */ });
        } else {
          v.pause();
        }
      });
    }, { rootMargin: "100px", threshold: 0.35 });

    cards.forEach(function (v) { io.observe(v); });
  })();

  /* ------------------------------------------------------ pearl strand */
  // Lights every pearl up to the section being read, and marks the current
  // one. Cumulative rather than one-at-a-time: a strand that fills says how
  // far through the page you are, which a single moving dot does not.
  (function strand() {
    var pearls = Array.prototype.slice.call(
      document.querySelectorAll(".strand a")
    );
    if (!pearls.length || !hasIO) return;

    var ids = pearls.map(function (a) { return a.getAttribute("href").slice(1); });

    function lightUpTo(index) {
      pearls.forEach(function (a, i) {
        a.classList.toggle("is-lit", i <= index);
        if (i === index) a.setAttribute("aria-current", "true");
        else a.removeAttribute("aria-current");
      });
    }

    var io = new IntersectionObserver(function (entries) {
      entries.forEach(function (entry) {
        if (!entry.isIntersecting) return;
        var i = ids.indexOf(entry.target.id);
        if (i > -1) lightUpTo(i);
      });
    }, { rootMargin: "-45% 0px -50% 0px" });

    ids.forEach(function (id) {
      var el = document.getElementById(id);
      if (el) io.observe(el);
    });

    lightUpTo(0);
  })();

  /* ---------------------------------------------------- reveal on scroll */
  // [data-settle] and [data-rise] are driven by CSS scroll-timelines where the
  // browser supports them; this observer is their fallback, and adding the
  // class is a no-op in browsers that took the CSS path.
  var revealables = document.querySelectorAll("[data-reveal], [data-settle], [data-rise]");
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

  /* The mouse-tilt effect that used to live here has been removed. It was
     gated behind `(hover: hover) and (pointer: fine)`, so it never ran on a
     phone — which is where most of this site is read. Its replacement is the
     scroll-driven motion in cinematic.css, which runs on every device because
     scroll is an input everybody has. */

  /* ---------------------------------------------------- sticky scene */
  // Each text block owns an index; as it takes the middle of the viewport the
  // matching figure in the sticky column fades in. CSS holds the column still,
  // so this only decides which photograph is showing.
  var sceneMedia = document.querySelector("[data-scene-media]");
  if (sceneMedia && hasIO) {
    var figures = sceneMedia.querySelectorAll("[data-scene]");
    var steps = document.querySelectorAll("[data-scene-step]");

    var sceneObserver = new IntersectionObserver(function (entries) {
      entries.forEach(function (entry) {
        if (!entry.isIntersecting) return;
        var wanted = entry.target.getAttribute("data-scene-step");
        figures.forEach(function (fig) {
          fig.classList.toggle("is-active",
            fig.getAttribute("data-scene") === wanted);
        });
      });
    }, { rootMargin: "-45% 0px -45% 0px" });

    steps.forEach(function (step) { sceneObserver.observe(step); });
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

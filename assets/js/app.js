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

  /* ------------------------------------------------------- hero footage */
  // The hero poster already shows the room, so the video is strictly an
  // upgrade. It is attached only when the visitor's connection and settings
  // say it is welcome — a 4MB autoplaying clip on a metered phone connection
  // is a cost the visitor did not agree to.
  (function heroVideo() {
    var video = document.querySelector("[data-hero-video]");
    if (!video) return;
    if (reduce) { video.remove(); return; }

    // Dropped rather than left at opacity 0: a transparent <video> stretched
    // over the hero still sits on top of it and still takes pointer events.
    function decline() { video.remove(); }

    var net = navigator.connection || {};
    if (net.saveData) return decline();                        // Data Saver on
    if (/(^|-)(2g|slow-2g)$/.test(net.effectiveType || "")) return decline();

    // Phones get the photograph, not the footage, for two reasons that point
    // the same way. The clip is a landscape pan, so a portrait viewport crops
    // it to its middle — a stretch of ceiling, with the room gone. And it is
    // 4.3MB on a connection the visitor may be paying for by the megabyte.
    // The <picture> element already hands a phone a portrait frame that is
    // composed for that shape, so skipping the video here is an upgrade.
    if (window.matchMedia("(max-width: 700px)").matches) return decline();

    video.src = video.getAttribute("data-hero-video");
    video.load();

    // Cross-fade in only once there are real frames to show, otherwise the
    // poster is replaced by a black box for as long as the first keyframe
    // takes to arrive.
    video.addEventListener("canplay", function () {
      video.classList.add("is-ready");
    }, { once: true });

    var playing = video.play();
    if (playing && playing.catch) {
      // Autoplay refused (some iOS low-power states): drop back to the poster
      // rather than leaving a frozen first frame on screen.
      playing.catch(function () { video.remove(); });
    }

    // Stop decoding while the hero is off-screen. Video decode is the most
    // expensive thing on this page and it is pure waste once scrolled past.
    if (hasIO) {
      new IntersectionObserver(function (entries) {
        entries.forEach(function (entry) {
          if (entry.isIntersecting) { video.play().catch(function () {}); }
          else { video.pause(); }
        });
      }, { threshold: 0.01 }).observe(video);
    }
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

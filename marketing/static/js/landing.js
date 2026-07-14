(function () {
  "use strict";

  const HERO_WORD_KEYS = [
    "landing_hero_word_1",
    "landing_hero_word_2",
    "landing_hero_word_3",
    "landing_hero_word_4",
  ];

  const navWrap = document.getElementById("landing-nav-wrap");
  const menuBtn = document.getElementById("landing-menu-btn");
  const mobileMenu = document.getElementById("landing-mobile-menu");
  const heroWordEl = document.getElementById("landing-hero-word");
  const ctaBox = document.getElementById("landing-cta-box");
  const ctaSpotlight = document.getElementById("landing-cta-spotlight");
  const steps = document.querySelectorAll(".landing-step");
  const particleCanvas = document.getElementById("landing-particles");

  function currentLang() {
    return localStorage.getItem("appLang") === "en" ? "en" : "zh";
  }

  function heroWords() {
    if (typeof window.t !== "function") {
      return currentLang() === "en"
        ? ["quote", "price", "style", "custom"]
        : ["試算", "報價", "選款", "訂製"];
    }
    return HERO_WORD_KEYS.map(function (key) {
      return window.t(key);
    });
  }

  /* ── Nav scroll ── */
  function onScroll() {
    if (navWrap) {
      navWrap.classList.toggle("is-scrolled", window.scrollY > 20);
    }
  }
  window.addEventListener("scroll", onScroll, { passive: true });
  onScroll();

  /* ── Mobile menu ── */
  function setMenuOpen(open) {
    if (!navWrap || !mobileMenu || !menuBtn) return;
    navWrap.classList.toggle("is-menu-open", open);
    mobileMenu.classList.toggle("is-open", open);
    mobileMenu.setAttribute("aria-hidden", open ? "false" : "true");
    menuBtn.setAttribute("aria-expanded", open ? "true" : "false");
    document.body.style.overflow = open ? "hidden" : "";
  }

  if (menuBtn) {
    menuBtn.addEventListener("click", function () {
      setMenuOpen(!mobileMenu.classList.contains("is-open"));
    });
  }

  document.querySelectorAll(".landing-mobile-link").forEach(function (link) {
    link.addEventListener("click", function () {
      setMenuOpen(false);
    });
  });

  /* ── Hero entrance ── */
  requestAnimationFrame(function () {
    ["landing-eyebrow", "landing-hero-desc", "landing-hero-actions", "landing-hero-stats"].forEach(function (id) {
      var el = document.getElementById(id);
      if (el) el.classList.add("is-visible");
    });
    var eyebrow = document.querySelector(".landing-eyebrow");
    if (eyebrow) eyebrow.classList.add("is-visible");
    var title = document.querySelector(".landing-hero-title");
    if (title) title.classList.add("is-visible");
  });

  /* ── Rotating hero word ── */
  var wordIndex = 0;
  var gradientColors = ["#8eedf0", "#a5f2f4", "#67e8f9", "#8eedf0", "#baf6f8"];

  function hex2rgb(hex) {
    return [
      parseInt(hex.slice(1, 3), 16),
      parseInt(hex.slice(3, 5), 16),
      parseInt(hex.slice(5, 7), 16),
    ];
  }

  function lerpColor(a, b, t) {
    return a.map(function (v, i) {
      return Math.round(v + (b[i] - v) * t);
    });
  }

  function renderWord(word) {
    if (!heroWordEl) return;
    heroWordEl.innerHTML = "";
    var letters = word.split("");
    letters.forEach(function (char, i) {
      var span = document.createElement("span");
      span.className = "landing-hero-word-char";
      span.textContent = char;
      span.style.opacity = "0";
      span.style.filter = "blur(12px)";

      var colorIndex = (i / Math.max(letters.length - 1, 1)) * (gradientColors.length - 1);
      var lower = Math.floor(colorIndex);
      var upper = Math.min(lower + 1, gradientColors.length - 1);
      var t = colorIndex - lower;
      var rgb = lerpColor(hex2rgb(gradientColors[lower]), hex2rgb(gradientColors[upper]), t);
      span.style.color = "rgb(" + rgb.join(",") + ")";

      heroWordEl.appendChild(span);

      var delay = i * 45;
      setTimeout(function () {
        var start = performance.now();
        var duration = 500;
        function tick(now) {
          var progress = Math.min((now - start) / duration, 1);
          var eased = 1 - Math.pow(1 - progress, 3);
          span.style.opacity = String(eased);
          span.style.filter = "blur(" + 12 * (1 - eased) + "px)";
          if (progress < 1) requestAnimationFrame(tick);
          else {
            setTimeout(function () {
              span.style.color = "#fff";
            }, 200);
          }
        }
        requestAnimationFrame(tick);
      }, delay);
    });
  }

  function cycleWord() {
    var words = heroWords();
    renderWord(words[wordIndex % words.length]);
    wordIndex += 1;
  }

  cycleWord();
  setInterval(cycleWord, 2500);

  document.addEventListener("langchange", function () {
    wordIndex = 0;
    cycleWord();
  });

  /* ── Footer banner: soft cursor glow on hover ── */
  var footerBanner = document.getElementById("landing-footer-banner");
  var footerGlow = document.getElementById("landing-footer-banner-glow");

  if (footerBanner && footerGlow) {
    var glowPos = { x: 50, y: 50 };
    var glowTarget = { x: 50, y: 50 };
    var glowHover = false;
    var glowRaf = 0;
    var glowReduced =
      window.matchMedia && window.matchMedia("(prefers-reduced-motion: reduce)").matches;

    function setGlowTarget(clientX, clientY) {
      var rect = footerBanner.getBoundingClientRect();
      if (!rect.width || !rect.height) return;
      glowTarget.x = ((clientX - rect.left) / rect.width) * 100;
      glowTarget.y = ((clientY - rect.top) / rect.height) * 100;
    }

    function tickGlow() {
      glowPos.x += (glowTarget.x - glowPos.x) * 0.14;
      glowPos.y += (glowTarget.y - glowPos.y) * 0.14;
      footerGlow.style.setProperty("--footer-glow-x", glowPos.x + "%");
      footerGlow.style.setProperty("--footer-glow-y", glowPos.y + "%");
      if (glowHover) {
        glowRaf = requestAnimationFrame(tickGlow);
      } else {
        glowRaf = 0;
      }
    }

    function startGlowLoop() {
      if (glowRaf || glowReduced) return;
      glowRaf = requestAnimationFrame(tickGlow);
    }

    footerBanner.addEventListener("mouseenter", function () {
      glowHover = true;
      footerBanner.classList.add("is-hover");
      startGlowLoop();
    });

    footerBanner.addEventListener("mousemove", function (e) {
      setGlowTarget(e.clientX, e.clientY);
      if (glowReduced) {
        footerGlow.style.setProperty("--footer-glow-x", glowTarget.x + "%");
        footerGlow.style.setProperty("--footer-glow-y", glowTarget.y + "%");
      }
    });

    footerBanner.addEventListener("mouseleave", function () {
      glowHover = false;
      footerBanner.classList.remove("is-hover");
    });

    footerBanner.addEventListener(
      "touchstart",
      function (e) {
        if (!e.touches.length) return;
        glowHover = true;
        footerBanner.classList.add("is-hover");
        setGlowTarget(e.touches[0].clientX, e.touches[0].clientY);
        startGlowLoop();
      },
      { passive: true }
    );

    footerBanner.addEventListener(
      "touchmove",
      function (e) {
        if (!e.touches.length) return;
        setGlowTarget(e.touches[0].clientX, e.touches[0].clientY);
      },
      { passive: true }
    );

    footerBanner.addEventListener("touchend", function () {
      glowHover = false;
      footerBanner.classList.remove("is-hover");
    });
  }

  /* ── Scroll reveal ── */
  if ("IntersectionObserver" in window) {
    var revealObs = new IntersectionObserver(
      function (entries) {
        entries.forEach(function (entry) {
          if (entry.isIntersecting) {
            entry.target.classList.add("is-visible");
          }
        });
      },
      { threshold: 0.12 }
    );
    document.querySelectorAll(".landing-reveal").forEach(function (el) {
      revealObs.observe(el);
    });
  } else {
    document.querySelectorAll(".landing-reveal").forEach(function (el) {
      el.classList.add("is-visible");
    });
  }

  /* ── Process steps auto-rotate ── */
  var activeStep = 0;
  if (steps.length) {
    setInterval(function () {
      activeStep = (activeStep + 1) % steps.length;
      steps.forEach(function (step, i) {
        step.classList.toggle("is-active", i === activeStep);
      });
    }, 6000);

    steps.forEach(function (step, i) {
      step.addEventListener("click", function () {
        activeStep = i;
        steps.forEach(function (s, j) {
          s.classList.toggle("is-active", j === activeStep);
        });
      });
    });
  }

  /* ── CTA spotlight ── */
  if (ctaBox && ctaSpotlight) {
    ctaBox.addEventListener("mousemove", function (e) {
      var rect = ctaBox.getBoundingClientRect();
      var x = ((e.clientX - rect.left) / rect.width) * 100;
      var y = ((e.clientY - rect.top) / rect.height) * 100;
      ctaSpotlight.style.background =
        "radial-gradient(600px circle at " + x + "% " + y + "%, rgba(142,237,240,0.12), transparent 45%)";
      ctaSpotlight.style.opacity = "1";
    });
    ctaBox.addEventListener("mouseleave", function () {
      ctaSpotlight.style.opacity = "0";
    });
  }

  /* ── Particle canvas (feature hero) ── */
  if (particleCanvas) {
    var ctx = particleCanvas.getContext("2d");
    var frameId = 0;
    var time = 0;
    var mouse = { x: 0.5, y: 0.5 };
    var particles = Array.from({ length: 55 }, function (_, i) {
      var seed = i * 1.618;
      return {
        bx: (seed * 127.1) % 1,
        by: (seed * 311.7) % 1,
        phase: seed * Math.PI * 2,
        speed: 0.4 + (seed % 0.4),
        radius: 1 + (seed % 1.5),
      };
    });

    function resizeCanvas() {
      var rect = particleCanvas.parentElement.getBoundingClientRect();
      var dpr = Math.min(window.devicePixelRatio || 1, 2);
      particleCanvas.width = rect.width * dpr;
      particleCanvas.height = rect.height * dpr;
      particleCanvas.style.width = rect.width + "px";
      particleCanvas.style.height = rect.height + "px";
      ctx.setTransform(dpr, 0, 0, dpr, 0, 0);
    }

    function renderParticles() {
      var w = particleCanvas.parentElement.clientWidth;
      var h = particleCanvas.parentElement.clientHeight;
      ctx.clearRect(0, 0, w, h);

      particles.forEach(function (p) {
        var flowX = Math.sin(time * p.speed * 0.4 + p.phase) * 30;
        var flowY = Math.cos(time * p.speed * 0.3 + p.phase * 0.7) * 20;
        var bx = p.bx * w;
        var by = p.by * h;
        var dx = p.bx - mouse.x;
        var dy = p.by - mouse.y;
        var dist = Math.sqrt(dx * dx + dy * dy);
        var influence = Math.max(0, 1 - dist * 2.5);
        var x = bx + flowX + influence * Math.cos(time + p.phase) * 28;
        var y = by + flowY + influence * Math.sin(time + p.phase) * 28;
        var pulse = Math.sin(time * p.speed + p.phase) * 0.5 + 0.5;
        var alpha = 0.06 + pulse * 0.14 + influence * 0.25;
        ctx.beginPath();
        ctx.arc(x, y, p.radius + pulse * 0.6, 0, Math.PI * 2);
        ctx.fillStyle = "rgba(142, 237, 240, " + alpha + ")";
        ctx.fill();
      });

      time += 0.016;
      frameId = requestAnimationFrame(renderParticles);
    }

    resizeCanvas();
    renderParticles();
    window.addEventListener("resize", resizeCanvas);

    particleCanvas.parentElement.addEventListener("mousemove", function (e) {
      var rect = particleCanvas.parentElement.getBoundingClientRect();
      mouse.x = (e.clientX - rect.left) / rect.width;
      mouse.y = (e.clientY - rect.top) / rect.height;
    });
  }
})();

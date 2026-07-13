(function () {
  "use strict";

  var card = document.getElementById("auth-split-card");
  var carousel = document.getElementById("auth-carousel");
  var dotsWrap = document.getElementById("auth-carousel-dots");
  var slideTimer = null;
  var currentSlide = 0;

  if (card) {
    requestAnimationFrame(function () {
      card.classList.add("is-mounted");
    });
  }

  function getSlides() {
    return carousel ? carousel.querySelectorAll(".auth-carousel-slide") : [];
  }

  function getDots() {
    return dotsWrap ? dotsWrap.querySelectorAll(".auth-dot") : [];
  }

  function goToSlide(index) {
    var slides = getSlides();
    var dots = getDots();
    if (!slides.length) return;

    currentSlide = ((index % slides.length) + slides.length) % slides.length;

    slides.forEach(function (slide, i) {
      slide.classList.toggle("is-active", i === currentSlide);
    });

    dots.forEach(function (dot, i) {
      var active = i === currentSlide;
      dot.classList.toggle("is-active", active);
      dot.setAttribute("aria-selected", active ? "true" : "false");
    });
  }

  function startCarousel() {
    if (!carousel || getSlides().length < 2) return;
    stopCarousel();
    slideTimer = setInterval(function () {
      goToSlide(currentSlide + 1);
    }, 5000);
  }

  function stopCarousel() {
    if (slideTimer) {
      clearInterval(slideTimer);
      slideTimer = null;
    }
  }

  if (dotsWrap) {
    dotsWrap.addEventListener("click", function (e) {
      var btn = e.target.closest(".auth-dot");
      if (!btn) return;
      var idx = parseInt(btn.getAttribute("data-index"), 10);
      if (!Number.isNaN(idx)) {
        goToSlide(idx);
        startCarousel();
      }
    });
  }

  startCarousel();

  document.querySelectorAll("[data-password-toggle]").forEach(function (btn) {
    btn.addEventListener("click", function () {
      var wrap = btn.closest(".auth-password-wrap");
      if (!wrap) return;
      var input = wrap.querySelector("input");
      if (!input) return;

      var show = input.type === "password";
      input.type = show ? "text" : "password";
      btn.classList.toggle("is-password-visible", show);
      btn.setAttribute("aria-label", show ? "隱藏密碼" : "顯示密碼");
      btn.setAttribute("aria-pressed", show ? "true" : "false");
    });
  });

  var STRENGTH_KEYS = [
    "",
    "auth_password_strength_weak",
    "auth_password_strength_fair",
    "auth_password_strength_good",
    "auth_password_strength_strong",
  ];

  function tr(key) {
    return window.t ? window.t(key) : key;
  }

  function scorePassword(password) {
    if (!password) return 0;
    var score = 0;
    if (password.length >= 6) score++;
    if (password.length >= 10) score++;
    if (/[a-z]/.test(password) && /[A-Z]/.test(password)) score++;
    if (/\d/.test(password)) score++;
    if (/[^A-Za-z0-9]/.test(password)) score++;
    if (score <= 1) return 1;
    if (score <= 2) return 2;
    if (score <= 3) return 3;
    return 4;
  }

  function updatePasswordStrength(input) {
    var field = input.closest(".auth-field");
    if (!field) return;
    var meter = field.querySelector(".auth-password-strength");
    var label = field.querySelector(".auth-password-strength-label");
    if (!meter || !label) return;

    var value = input.value.trim();
    var level = scorePassword(value);
    meter.classList.remove("is-level-1", "is-level-2", "is-level-3", "is-level-4", "is-visible");

    if (!value) {
      label.textContent = "";
      return;
    }

    meter.classList.add("is-visible", "is-level-" + level);
    var levelText = tr(STRENGTH_KEYS[level]);
    var template = tr("auth_password_strength_label");
    label.textContent = template.indexOf("{level}") >= 0
      ? template.replace("{level}", levelText)
      : levelText;
  }

  document.querySelectorAll("[data-password-strength]").forEach(function (input) {
    updatePasswordStrength(input);
    input.addEventListener("input", function () {
      updatePasswordStrength(input);
    });
  });

  document.addEventListener("langchange", function () {
    document.querySelectorAll("[data-password-strength]").forEach(updatePasswordStrength);
  });
})();

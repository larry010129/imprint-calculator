(function () {

  "use strict";



  var wrap = document.getElementById("app-nav-wrap");

  if (!wrap) return;



  var navbar = wrap.querySelector(".premium-navbar.app-navbar");

  var container = wrap.querySelector(".nav-container");

  var MOBILE_BP = 900;

  var H_PAD = 56;



  function onScroll() {

    wrap.classList.toggle("is-scrolled", window.scrollY > 16);

  }



  function syncNavWidth() {

    if (!navbar || !container) return;



    if (window.innerWidth <= MOBILE_BP) {

      navbar.style.width = "";

      return;

    }



    navbar.style.width = "max-content";

    var needed = Math.ceil(container.getBoundingClientRect().width) + H_PAD;

    var available = window.innerWidth - 32;

    navbar.style.width = Math.min(needed, available) + "px";

  }



  window.syncAppNavWidth = syncNavWidth;



  window.addEventListener("scroll", onScroll, { passive: true });

  window.addEventListener("resize", syncNavWidth, { passive: true });

  document.addEventListener("langchange", syncNavWidth);

  document.fonts && document.fonts.ready.then(syncNavWidth);



  if (window.ResizeObserver && container) {

    var observer = new ResizeObserver(syncNavWidth);

    observer.observe(container);

  }



  onScroll();



  if (document.readyState === "loading") {

    document.addEventListener("DOMContentLoaded", syncNavWidth);

  } else {

    syncNavWidth();

  }

})();


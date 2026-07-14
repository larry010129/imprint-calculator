(function () {
  const btn = document.querySelector('.quote-sheet footer button');
  if (btn) {
    btn.addEventListener('click', () => window.print());
  }
})();

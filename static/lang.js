(function () {
  const btn  = document.getElementById('langToggle');
  let lang   = localStorage.getItem('pf2e-lang') || 'fr';

  function apply() {
    document.querySelectorAll('[data-fr]').forEach(el => {
      el.textContent = lang === 'fr' ? el.dataset.fr : el.dataset.en;
    });
    btn.textContent = lang === 'fr' ? 'EN' : 'FR';
    document.documentElement.lang = lang;
    localStorage.setItem('pf2e-lang', lang);
  }

  btn.addEventListener('click', () => {
    lang = lang === 'fr' ? 'en' : 'fr';
    apply();
  });

  apply();
})();

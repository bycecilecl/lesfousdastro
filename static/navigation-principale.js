(() => {
  const nav = document.querySelector('.navbar--compact');
  if (!nav) return;
  const bouton = nav.querySelector('.navbar__toggle');
  const sousMenus = [...nav.querySelectorAll('.navbar__submenu')];
  const fermerSousMenus = sauf => sousMenus.forEach(menu => { if (menu !== sauf) menu.open = false; });
  const ouvrirMenu = ouvert => {
    document.body.classList.toggle('nav-open', ouvert);
    bouton.setAttribute('aria-expanded', String(ouvert));
    bouton.setAttribute('aria-label', ouvert ? 'Fermer le menu' : 'Ouvrir le menu');
    if (!ouvert) fermerSousMenus();
  };
  bouton.addEventListener('click', () => ouvrirMenu(!document.body.classList.contains('nav-open')));
  sousMenus.forEach(menu => menu.addEventListener('toggle', () => { if (menu.open) fermerSousMenus(menu); }));
  document.addEventListener('click', event => { if (!nav.contains(event.target)) ouvrirMenu(false); });
  nav.addEventListener('click', event => { if (event.target.closest('a')) ouvrirMenu(false); });
  nav.addEventListener('focusout', event => { if (event.relatedTarget && !nav.contains(event.relatedTarget)) fermerSousMenus(); });
  document.addEventListener('keydown', event => {
    if (event.key !== 'Escape') return;
    const ouvert = sousMenus.find(menu => menu.open);
    if (ouvert) {
      ouvert.open = false;
      ouvert.querySelector('summary').focus();
    } else if (document.body.classList.contains('nav-open')) {
      ouvrirMenu(false);
      bouton.focus();
    }
  });
  window.matchMedia('(min-width: 1101px)').addEventListener('change', () => ouvrirMenu(false));
})();

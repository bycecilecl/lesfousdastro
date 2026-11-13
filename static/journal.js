(() => {
    const journal = document.querySelector('[data-journal-mode]');
    if (!journal) return;
    const index = document.getElementById('mes-entrees');
    const mobile = window.matchMedia('(max-width: 800px)');
    const adapter = () => { index.open = !mobile.matches; };
    adapter();
    mobile.addEventListener('change', adapter);
    // Les liens vers une entrée sont de vrais liens : le retour navigateur reste utilisable.
    const ouvrirAncienLien = () => {
        if (journal.dataset.journalMode !== 'nouveau') return;
        const resultat = location.hash.match(/^#entree-(\d+)$/);
        if (!resultat) return;
        const lien = Array.from(index.querySelectorAll('[data-entree-id]')).find(a => a.dataset.entreeId === resultat[1]);
        if (lien) location.replace(lien.href);
    };
    ouvrirAncienLien();
    window.addEventListener('hashchange', ouvrirAncienLien);
    if (location.hash === '#aller-plus-loin') {
        const suite = document.getElementById('aller-plus-loin');
        if (suite) suite.open = true;
    }
    const formulaire = document.getElementById('journal-ecriture');
    if (!formulaire) return;
    let modifie = formulaire.dataset.saisieConservee === 'oui';
    formulaire.addEventListener('input', () => { modifie = true; });
    formulaire.addEventListener('change', () => { modifie = true; });
    formulaire.addEventListener('submit', () => { modifie = false; });
    window.addEventListener('beforeunload', evenement => {
        if (!modifie) return;
        evenement.preventDefault();
        evenement.returnValue = '';
    });
})();

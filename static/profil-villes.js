/* Recherche de ville du profil : sélection explicite, indépendante de datalist. */
(() => {
  function initialiser(ids) {
    const champ = document.getElementById(ids.champ);
    if (!champ) return;
    const liste = document.getElementById(ids.liste);
    const statut = document.getElementById(ids.statut);
    const latitude = document.getElementById(ids.latitude);
    const longitude = document.getElementById(ids.longitude);
    const fuseau = document.getElementById(ids.fuseau);
    let resultats = [], actif = -1, revision = 0, attente, requete;
    let selection = latitude.value && longitude.value && fuseau.value ? champ.value : null;

    function fermer() {
      liste.hidden = true;
      champ.setAttribute('aria-expanded', 'false');
      champ.removeAttribute('aria-activedescendant');
      actif = -1;
      liste.querySelectorAll('[role="option"]').forEach(option => option.setAttribute('aria-selected', 'false'));
    }
    function ouvrir() {
      if (!resultats.length) return;
      liste.hidden = false;
      champ.setAttribute('aria-expanded', 'true');
    }
    function choisir(lieu) {
      ++revision;
      clearTimeout(attente);
      requete?.abort();
      champ.value = lieu.label;
      latitude.value = lieu.lat;
      longitude.value = lieu.lon;
      fuseau.value = lieu.tzid;
      selection = lieu.label;
      champ.setCustomValidity('');
      champ.setAttribute('aria-busy', 'false');
      statut.textContent = `Ville sélectionnée : ${lieu.label} · ${lieu.tzid}`;
      resultats = [];
      fermer();
      liste.replaceChildren();
      champ.focus();
    }
    function lieuValide(lieu) {
      return lieu && typeof lieu.label === 'string' && lieu.label.trim()
        && lieu.lat !== null && lieu.lat !== '' && lieu.lon !== null && lieu.lon !== ''
        && Number.isFinite(Number(lieu.lat)) && Math.abs(Number(lieu.lat)) <= 90
        && Number.isFinite(Number(lieu.lon)) && Math.abs(Number(lieu.lon)) <= 180
        && typeof lieu.tzid === 'string' && lieu.tzid.trim();
    }
    async function rechercher(texte, version) {
      const controle = new AbortController();
      requete = controle;
      let expiration = false;
      const delai = window.setTimeout(() => { expiration = true; controle.abort(); }, 15000);
      champ.setAttribute('aria-busy', 'true');
      statut.textContent = 'Recherche des villes…';
      try {
        const reponse = await fetch(`/api/geocode?q=${encodeURIComponent(texte)}`, {signal: controle.signal});
        if (!reponse.ok) throw new Error('geocode');
        const donnees = await reponse.json();
        if (version !== revision || champ.value.trim() !== texte) return;
        resultats = Array.isArray(donnees.results) ? donnees.results.filter(lieuValide) : [];
        liste.replaceChildren(...resultats.map((lieu, index) => {
          const option = document.createElement('li');
          option.id = `${liste.id}-${version}-${index}`;
          option.setAttribute('role', 'option');
          option.setAttribute('aria-selected', 'false');
          option.textContent = lieu.label;
          // Garder le focus dans le champ jusqu'au clic, aussi sur Firefox.
          option.addEventListener('pointerdown', evenement => evenement.preventDefault());
          option.addEventListener('click', () => choisir(lieu));
          return option;
        }));
        statut.textContent = resultats.length
          ? `${resultats.length} ville${resultats.length > 1 ? 's' : ''} proposée${resultats.length > 1 ? 's' : ''}. Clique sur ta ville ou utilise les flèches puis Entrée.`
          : 'Aucune ville trouvée. Précise le pays ou essaie un code postal français.';
        ouvrir();
      } catch (erreur) {
        if (version !== revision || (erreur.name === 'AbortError' && !expiration)) return;
        statut.textContent = 'La recherche de ville est momentanément indisponible. Réessaie dans quelques instants.';
      } finally {
        clearTimeout(delai);
        if (version === revision) champ.setAttribute('aria-busy', 'false');
      }
    }
    champ.addEventListener('input', () => {
      const version = ++revision;
      clearTimeout(attente);
      requete?.abort();
      selection = null;
      resultats = [];
      fermer();
      liste.replaceChildren();
      latitude.value = longitude.value = fuseau.value = '';
      champ.setAttribute('aria-busy', 'false');
      champ.setCustomValidity('Choisis une ville dans les suggestions pour enregistrer ses coordonnées.');
      const texte = champ.value.trim();
      statut.textContent = texte.length < 2 ? 'Écris au moins deux lettres pour rechercher une ville.' : 'La liste des villes va apparaître sous le champ.';
      if (texte.length >= 2) attente = setTimeout(() => rechercher(texte, version), 400);
    });
    champ.addEventListener('keydown', evenement => {
      if ((evenement.key === 'ArrowDown' || evenement.key === 'ArrowUp') && resultats.length) {
        evenement.preventDefault();
        ouvrir();
        actif = (actif + (evenement.key === 'ArrowDown' ? 1 : actif < 0 ? 0 : -1) + resultats.length) % resultats.length;
        liste.querySelectorAll('[role="option"]').forEach((option, index) => {
          option.setAttribute('aria-selected', String(index === actif));
          if (index === actif) {
            champ.setAttribute('aria-activedescendant', option.id);
            option.scrollIntoView({block: 'nearest'});
          }
        });
      } else if (evenement.key === 'Enter' && !liste.hidden) {
        evenement.preventDefault();
        if (actif >= 0) choisir(resultats[actif]);
        else statut.textContent = 'Clique sur ta ville, ou sélectionne-la avec les flèches puis Entrée.';
      } else if (evenement.key === 'Escape' || evenement.key === 'Tab') {
        fermer();
      }
    });
    champ.addEventListener('focus', ouvrir);
    champ.addEventListener('blur', fermer);
    champ.form.addEventListener('submit', evenement => {
      if (selection !== champ.value || !latitude.value || !longitude.value || !fuseau.value) {
        evenement.preventDefault();
        champ.setCustomValidity('Choisis une ville dans la liste avant d’enregistrer ton profil.');
        champ.reportValidity();
      }
    });
  }
  initialiser({champ:'ville_naissance', liste:'suggestions-lieux-profil', statut:'lieu-statut', latitude:'latitude', longitude:'longitude', fuseau:'fuseau_horaire'});
  initialiser({champ:'ville_cycles', liste:'suggestions-lieux-cycles', statut:'cycles-statut', latitude:'latitude_cycles', longitude:'longitude_cycles', fuseau:'fuseau_cycles'});
})();

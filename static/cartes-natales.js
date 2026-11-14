(() => {
  const form = document.querySelector('[data-carte-form]');
  if (!form) return;
  const fichier = form.elements.carte, membre = form.elements.membre, page = form.elements.page_pdf;
  const status = form.querySelector('[data-carte-status]'), editeur = form.querySelector('[data-carte-editeur]');
  const canvas = form.querySelector('[data-carte-canvas]'), resultat = form.querySelector('[data-carte-resultat]');
  const sauver = form.querySelector('[data-carte-enregistrer]'), pageSection = form.querySelector('[data-page-section]');
  const champs = [...form.querySelectorAll('[data-coordonnee]')], noms = ['x', 'y', 'w', 'h'];
  let image = null, rectangle = [0, 0, 1, 1], depart = null, precedent = rectangle.slice();
  let numero = 0, controle = null;
  const limiter = (valeur, min, max) => Math.max(min, Math.min(max, valeur));
  const tailleValide = () => image && rectangle[2] * image.width >= 32 && rectangle[3] * image.height >= 32;

  function dessiner() {
    if (!image) return;
    const [x, y, w, h] = rectangle, ctx = canvas.getContext('2d');
    const gauche = x * canvas.width, haut = y * canvas.height, largeur = w * canvas.width, hauteur = h * canvas.height;
    ctx.clearRect(0, 0, canvas.width, canvas.height);
    ctx.drawImage(image, 0, 0);
    ctx.fillStyle = 'rgba(15, 38, 48, .42)';
    ctx.fillRect(0, 0, canvas.width, haut); ctx.fillRect(0, haut + hauteur, canvas.width, canvas.height - haut - hauteur);
    ctx.fillRect(0, haut, gauche, hauteur); ctx.fillRect(gauche + largeur, haut, canvas.width - gauche - largeur, hauteur);
    ctx.strokeStyle = '#00a8a8'; ctx.lineWidth = 3; ctx.strokeRect(gauche, haut, largeur, hauteur);
    const echelle = Math.min(1, 700 / Math.max(1, largeur));
    resultat.width = Math.max(1, Math.round(largeur * echelle)); resultat.height = Math.max(1, Math.round(hauteur * echelle));
    resultat.getContext('2d').drawImage(image, gauche, haut, largeur, hauteur, 0, 0, resultat.width, resultat.height);
    form.elements.recadrage.value = JSON.stringify(rectangle);
    champs.forEach(champ => { champ.value = (rectangle[noms.indexOf(champ.dataset.coordonnee)] * 100).toFixed(1); });
    sauver.disabled = !tailleValide();
  }

  function vider() {
    numero++; controle?.abort(); image = null; depart = null; editeur.hidden = true; pageSection.hidden = true;
    sauver.disabled = true; form.elements.empreinte_source.value = ''; form.elements.recadrage.value = '';
  }

  async function apercu() {
    const monNumero = ++numero;
    controle?.abort(); controle = new AbortController();
    image = null; depart = null; editeur.hidden = true; sauver.disabled = true; form.elements.empreinte_source.value = '';
    status.textContent = 'Préparation de l’aperçu… La carte enregistrée est conservée.';
    try {
      const reponse = await fetch(form.dataset.apercuUrl, {method:'POST', body:new FormData(form), signal:controle.signal});
      let donnees;
      try { donnees = await reponse.json(); } catch { throw new Error('L’aperçu est indisponible. Recharge la page et réessaie.'); }
      if (!reponse.ok) throw new Error(donnees.error || 'L’aperçu n’a pas pu être préparé.');
      const chargee = new Image();
      await new Promise((resolve, reject) => { chargee.onload = resolve; chargee.onerror = () => reject(new Error('L’image de l’aperçu est illisible.')); chargee.src = donnees.image; });
      if (monNumero !== numero) return;
      image = chargee; canvas.width = image.width; canvas.height = image.height; rectangle = [0, 0, 1, 1];
      form.elements.empreinte_source.value = donnees.empreinte;
      page.max = String(donnees.pages); pageSection.hidden = donnees.pages <= 1;
      form.querySelector('[data-page-total]').textContent = 'sur ' + donnees.pages + ' page(s)';
      editeur.hidden = false; dessiner();
      status.textContent = 'Sélectionne la zone à garder, puis enregistre. La conversion en WebP gardera les proportions de ta sélection.';
    } catch (erreur) {
      if (monNumero !== numero || erreur.name === 'AbortError') return;
      status.textContent = erreur.message || 'L’aperçu n’a pas pu être préparé. La carte enregistrée est conservée.';
      pageSection.hidden = true;
    }
  }

  fichier.addEventListener('change', () => {
    vider(); form.elements.utiliser_existante.value = 'non'; fichier.required = true; page.value = '1';
    if (fichier.files.length) apercu(); else status.textContent = 'Choisis un fichier pour préparer son cadrage.';
  });
  membre.addEventListener('change', () => {
    if (form.elements.utiliser_existante.value === 'oui') {
      vider(); form.elements.utiliser_existante.value = 'non'; fichier.required = true; page.value = '1';
      status.textContent = 'Le membre a changé. Choisis sa carte ou utilise son bouton « Recadrer » dans la liste.';
    }
  });
  page.addEventListener('change', () => { if (page.checkValidity()) apercu(); });
  document.querySelectorAll('[data-reprendre-carte]').forEach(bouton => bouton.addEventListener('click', () => {
    vider(); membre.value = bouton.dataset.reprendreCarte; fichier.value = ''; fichier.required = false;
    form.elements.utiliser_existante.value = 'oui'; page.value = '1'; apercu();
    document.getElementById('depot').scrollIntoView({block:'start'});
  }));
  form.querySelector('[data-carte-reset]').addEventListener('click', () => { rectangle = [0, 0, 1, 1]; dessiner(); });
  const position = event => {
    const cadre = canvas.getBoundingClientRect();
    return [limiter((event.clientX - cadre.left) / cadre.width, 0, 1), limiter((event.clientY - cadre.top) / cadre.height, 0, 1)];
  };
  canvas.addEventListener('pointerdown', event => {
    if (!image || (event.pointerType === 'mouse' && event.button !== 0)) return;
    event.preventDefault(); precedent = rectangle.slice(); depart = position(event); canvas.setPointerCapture(event.pointerId);
  });
  canvas.addEventListener('pointermove', event => {
    if (!depart) return;
    const [x, y] = position(event);
    rectangle = [Math.min(depart[0], x), Math.min(depart[1], y), Math.max(.00001, Math.abs(x - depart[0])), Math.max(.00001, Math.abs(y - depart[1]))];
    dessiner();
  });
  const terminer = event => {
    if (!depart) return;
    depart = null;
    if (!tailleValide()) { rectangle = precedent; status.textContent = 'Cette zone est trop petite. Trace un rectangle plus grand.'; }
    dessiner(); if (canvas.hasPointerCapture(event.pointerId)) canvas.releasePointerCapture(event.pointerId);
  };
  canvas.addEventListener('pointerup', terminer); canvas.addEventListener('pointercancel', terminer);
  champs.forEach(champ => champ.addEventListener('change', () => {
    if (!image) return;
    const valeurs = noms.map(nom => Number(form.querySelector('[data-coordonnee="' + nom + '"]').value) / 100);
    if (!valeurs.every(Number.isFinite)) return;
    const x = limiter(valeurs[0], 0, .999), y = limiter(valeurs[1], 0, .999);
    rectangle = [x, y, limiter(valeurs[2], .0001, 1 - x), limiter(valeurs[3], .0001, 1 - y)];
    dessiner(); if (!tailleValide()) status.textContent = 'Agrandis la sélection avant d’enregistrer.';
  }));
  form.addEventListener('submit', event => {
    if (!image || !tailleValide() || !form.elements.empreinte_source.value) {
      event.preventDefault(); status.textContent = 'Prépare d’abord un aperçu et choisis une zone assez grande.'; return;
    }
    sauver.disabled = true; sauver.textContent = 'Conversion et enregistrement…';
  });
})();

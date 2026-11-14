(() => {
  const racine = document.querySelector('[data-communaute]');
  if (!racine) return;
  racine.querySelectorAll('form[data-confirmer]').forEach(form => form.addEventListener('submit', event => {
    if (!window.confirm(form.dataset.confirmer)) event.preventDefault();
  }));
  const publication = racine.querySelector('[data-publication-form]');
  if (publication) {
    const titre = publication.querySelector('[name=titre]'), texte = publication.querySelector('[name=texte]');
    const apercu = () => {
      publication.querySelector('[data-preview-titre]').textContent = titre.value;
      publication.querySelector('[data-preview-texte]').textContent = texte.value;
    };
    titre.addEventListener('input', apercu); texte.addEventListener('input', apercu); apercu();
  }
  racine.querySelectorAll('form:not([data-salon-form])').forEach(form => form.addEventListener('submit', event => {
    if (event.defaultPrevented) return;
    const bouton = event.submitter;
    if (bouton) { bouton.disabled = true; bouton.textContent = 'Enregistrement…'; }
  }));
  const salon = racine.querySelector('[data-salon]');
  if (!salon) return;
  const conversation = salon.querySelector('[data-conversation]'), statut = salon.querySelector('[data-salon-status]');
  const formulaire = salon.querySelector('[data-salon-form]'), elements = new Map();
  let attente = false, arrete = false, minuteur, lectureEnCours = false, versionActions = 0;
  const csrf = salon.dataset.csrf;
  const appel = async (url, options = {}) => {
    const controle = new AbortController(), delai = setTimeout(() => controle.abort(), 15000);
    try {
      const reponse = await fetch(url, { ...options, signal: controle.signal, headers: { Accept: 'application/json', ...(options.headers || {}) } });
      let contenu;
      try { contenu = await reponse.json(); } catch { throw new Error('La conversation est momentanément indisponible.'); }
      if (!reponse.ok) {
        if (reponse.status === 401 || reponse.status === 403) arrete = true;
        throw new Error(contenu.error || 'Cette action n’a pas abouti.');
      }
      return contenu;
    } finally { clearTimeout(delai); }
  };
  const dessiner = messages => {
    const enBas = conversation.scrollHeight - conversation.scrollTop - conversation.clientHeight < 90;
    const presents = new Set(messages.map(m => m.id));
    for (const [id, element] of elements) if (!presents.has(id)) { element.remove(); elements.delete(id); }
    const vide = salon.querySelector('[data-salon-vide]');
    if (vide) vide.hidden = messages.length > 0;
    for (const message of messages) {
      const signature = JSON.stringify(message);
      if (elements.get(message.id)?.dataset.signature === signature) continue;
      const article = document.createElement('article'); article.className = 'comm-message' + (message.moi ? ' est-moi' : '');
      article.id = 'message-' + message.id;
      article.dataset.signature = signature;
      const entete = document.createElement('div'); entete.className = 'comm-message-head';
      const avatar = document.createElement('span'); avatar.className = 'comm-avatar'; avatar.setAttribute('aria-hidden', 'true');
      if (message.avatar) { const img = document.createElement('img'); img.src = message.avatar; img.alt = ''; avatar.append(img); } else avatar.textContent = '☾';
      const nom = document.createElement('strong'); nom.textContent = message.pseudo; nom.className = 'ton-' + Number(message.couleur);
      entete.append(avatar, nom);
      if (message.creatrice) { const badge = document.createElement('span'); badge.className = 'comm-badge'; badge.textContent = 'Créatrice'; entete.append(badge); }
      const heure = document.createElement('time'); heure.dateTime = message.date;
      const date = new Date(message.date); heure.textContent = date.toLocaleTimeString('fr-FR', {hour:'2-digit',minute:'2-digit'}); heure.title = date.toLocaleString('fr-FR');
      entete.append(heure);
      const texte = document.createElement('p'); texte.textContent = message.texte;
      article.append(entete, texte);
      if (message.retirer) {
        const retirer = document.createElement('button'); retirer.className = 'comm-text-button'; retirer.type = 'button'; retirer.textContent = 'Retirer';
        retirer.addEventListener('click', async () => {
          if (!window.confirm('Retirer ce message du salon ?')) return;
          versionActions += 1;
          retirer.disabled = true;
          try { await appel(message.retirer, {method:'POST',body:new URLSearchParams({csrf_token:csrf})}); elements.get(message.id)?.remove(); elements.delete(message.id); await actualiser(); }
          catch (erreur) { statut.textContent = erreur.message; } finally { retirer.disabled = false; }
        }); article.append(retirer);
      }
      if (message.signaler) {
        const signaler = document.createElement('a'); signaler.className = 'comm-report-link';
        signaler.href = message.signaler; signaler.textContent = 'Signaler à Cécile';
        // Un signalement ne doit pas faire perdre un message en cours de saisie.
        signaler.target = '_blank'; signaler.rel = 'noopener'; article.append(signaler);
      }
      if (elements.has(message.id)) elements.get(message.id).replaceWith(article); else conversation.append(article);
      elements.set(message.id, article);
    }
    let precedent = null;
    for (const message of messages) {
      const element = elements.get(message.id);
      if (precedent) { if (element.previousElementSibling !== precedent) precedent.after(element); }
      else { const premier = conversation.querySelector('.comm-message'); if (premier !== element) premier.before(element); }
      precedent = element;
    }
    if (enBas) conversation.scrollTop = conversation.scrollHeight;
  };
  const actualiser = async () => {
    if (arrete || document.hidden || lectureEnCours || attente) return;
    lectureEnCours = true;
    const version = versionActions;
    try { const donnees = await appel(salon.dataset.url); if (version === versionActions && !attente) { dessiner(donnees.messages); statut.textContent = ''; } }
    catch (erreur) { statut.textContent = erreur.message || 'Connexion interrompue. Les messages affichés restent disponibles.'; }
    finally { lectureEnCours = false; }
  };
  if (formulaire) formulaire.addEventListener('submit', async event => {
    event.preventDefault(); if (attente || arrete) return;
    const texte = formulaire.elements.texte, bouton = formulaire.querySelector('button');
    if (!texte.value.trim()) return;
    const texteEnvoye = texte.value;
    versionActions += 1;
    attente = true; bouton.disabled = true;
    try {
      const donnees = await appel(salon.dataset.url, {method:'POST',body:new URLSearchParams({texte:texteEnvoye,nonce:formulaire.elements.nonce.value,csrf_token:csrf})});
      dessiner(donnees.messages); if (texte.value === texteEnvoye) texte.value = ''; formulaire.elements.nonce.value = donnees.nonce; statut.textContent = ''; texte.focus(); conversation.scrollTop = conversation.scrollHeight;
    } catch (erreur) { statut.textContent = (erreur.message || 'Envoi non confirmé.') + ' Ton texte est conservé ; vérifie la conversation avant de réessayer.'; }
    finally { attente = false; bouton.disabled = false; }
  });
  const demarrer = () => { clearInterval(minuteur); actualiser(); minuteur = setInterval(actualiser, 6000); };
  document.addEventListener('visibilitychange', () => { if (!document.hidden) actualiser(); });
  window.addEventListener('pagehide', () => clearInterval(minuteur));
  window.addEventListener('pageshow', event => { if (event.persisted) { arrete = false; demarrer(); } });
  demarrer();
})();

"""Aperçu HTML sûr du texte d'un mail de cycle, sans modifier le mail envoyé."""

import re
from html import escape

from markupsafe import Markup


TITRES = {"Le mouvement du mois", "Ce qui vient appuyer là où ça compte", "À garder en tête"}


def rendu_brouillon_cycle(texte: str) -> Markup:
    blocs = []
    paragraphe = []

    def vider_paragraphe():
        if paragraphe:
            contenu = " ".join(paragraphe)
            contenu = re.sub(r"\*\*(.+?)\*\*", r"<strong>\1</strong>", contenu)
            blocs.append(f"<p>{contenu}</p>")
            paragraphe.clear()

    for ligne_brute in (texte or "").splitlines():
        ligne = ligne_brute.strip()
        if not ligne:
            vider_paragraphe()
            continue
        if re.match(r"^OBJET\s*:", ligne, re.IGNORECASE):
            vider_paragraphe()
            continue
        titre = re.sub(r"^#{1,3}\s*", "", ligne).strip("* ")
        if (ligne.startswith("#") or (ligne.startswith("**") and ligne.endswith("**"))) and titre in TITRES:
            vider_paragraphe()
            blocs.append(f"<h2>{escape(titre)}</h2>")
            continue
        if ligne in TITRES:
            vider_paragraphe()
            blocs.append(f"<h2>{escape(ligne)}</h2>")
            continue
        paragraphe.append(escape(ligne))
    vider_paragraphe()
    return Markup("\n".join(blocs))

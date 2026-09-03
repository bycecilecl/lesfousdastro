from __future__ import annotations

import re
from typing import List, Tuple


_PATTERN_AXES_UTILISES = re.compile(
    r"<axes_utilises>\s*(.*?)\s*</axes_utilises>",
    flags=re.IGNORECASE | re.DOTALL,
)


def extraire_axes_utilises(texte: str) -> Tuple[str, List[str]]:
    """
    Extrait les codes présents dans la balise <axes_utilises>,
    puis retire cette balise du texte visible.

    Retourne :
    - le texte nettoyé destiné au rapport ;
    - la liste des codes réellement utilisés.
    """
    texte = texte or ""

    correspondance = _PATTERN_AXES_UTILISES.search(texte)

    if not correspondance:
        return texte.strip(), []

    contenu_balise = correspondance.group(1)

    axes_utilises = []

    for ligne in contenu_balise.splitlines():
        code = ligne.strip().lstrip("-").strip()

        if not code:
            continue

        if re.fullmatch(r"[a-z0-9_]+", code):
            axes_utilises.append(code)

    axes_utilises = list(dict.fromkeys(axes_utilises))

    texte_nettoye = _PATTERN_AXES_UTILISES.sub("", texte).strip()

    return texte_nettoye, axes_utilises
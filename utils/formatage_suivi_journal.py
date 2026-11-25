"""Affichage du suivi : texte échappé, sans accepter de HTML généré."""
from html import escape
import re


def formater_bilan(texte):
    blocs = []
    for ligne in (texte or "").splitlines():
        ligne = ligne.strip()
        if not ligne:
            continue
        titre = re.match(r"^#{1,6}\s+(.+)$", ligne)
        contenu = escape(titre.group(1) if titre else ligne)
        contenu = re.sub(r"\*\*(.+?)\*\*", r"<strong>\1</strong>", contenu)
        contenu = re.sub(r"(?<!\*)\*([^*\n]+)\*(?!\*)", r"<em>\1</em>", contenu)
        contenu = re.sub(r"(?<![\w_])_([^_\n]+)_(?![\w_])", r"<em>\1</em>", contenu)
        blocs.append(f"<h3>{contenu}</h3>" if titre else f"<p>{contenu}</p>")
    return "\n".join(blocs)

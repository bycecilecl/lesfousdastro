import re


def _inline_markdown(text: str) -> str:
    """Convertit le gras et l'italique simples sans confondre * et **."""
    text = re.sub(r'\*\*(.+?)\*\*', r'<strong>\1</strong>', text)
    return re.sub(r'(?<!\*)\*([^*\n]+?)\*(?!\*)', r'<em>\1</em>', text)

def md_light_to_html(text: str) -> str:
    if not text:
        return ""
    
    # [NOUVEAU] — pré-nettoyage: supprime exactement "### Introduction" et "### Conclusion"
    # (ligne entière, casse insensible, bords/espaces ok)
    text = re.sub(
        r'(?im)^\s*###\s+(Introduction|Conclusion)\s*$',
        '',
        text
    )
    
    html = []
    in_ul = False
    para_buf = []  # ← on accumule ici les lignes d'un même paragraphe

    def flush_ul():
        nonlocal in_ul
        if in_ul:
            html.append('</ul>')
            in_ul = False

    def flush_para():
        """Fusionne les lignes accumulées en un seul paragraphe propre."""
        nonlocal para_buf
        if para_buf:
            # joindre par espace, retirer doubles espaces
            p = " ".join(para_buf)
            p = re.sub(r'\s{2,}', ' ', p).strip()
            p = _inline_markdown(p)
            html.append(f"<p>{p}</p>")
            para_buf = []

    for raw in text.splitlines():
        line = raw.strip()

        # Ligne vide -> fin de paragraphe éventuel
        if not line:
            flush_ul()
            flush_para()
            continue

        # Titres de premier niveau : ne pas laisser le marqueur Markdown
        # dans le texte envoyé au moteur PDF.
        if line.startswith('# '):
            flush_ul()
            flush_para()
            titre = line[2:].strip()
            titre = _inline_markdown(titre)
            html.append(f'<h1 class="section-title">{titre}</h1>')
            continue

        # Titres ##
        if line.startswith('## '):
            flush_ul()
            flush_para()
            titre = line[3:].strip()
            html.append(f'<h2 class="section-title">{titre}</h2>')
            continue

        # [NOUVEAU] Titres ### -> h3
        if line.startswith('### '):
            flush_ul()
            flush_para()
            titre = line[4:].strip()
            # NB : on a déjà supprimé les cas "Introduction"/"Conclusion" plus haut
            if titre:  # par sûreté
                html.append(f'<h3 class="section-subtitle">{titre}</h3>')
            continue

        # Puces -
        if line.startswith('- '):
            flush_para()
            if not in_ul:
                html.append('<ul>')
                in_ul = True
            item = line[2:].strip()
            item = _inline_markdown(item)
            html.append(f'<li>{item}</li>')
            continue

        # Sinon : ligne de paragraphe → on accumule
        # Normalisation des emphases Markdown avant assemblage du paragraphe.
        line = _inline_markdown(line)
        para_buf.append(line)

    # Fin de texte : flush
    flush_ul()
    flush_para()

    return '\n'.join(html)

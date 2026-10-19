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

        titre = re.fullmatch(r"(#{1,6})\s+(.+?)(?:\s+#+)?", line)
        if titre:
            flush_ul()
            flush_para()
            niveau = len(titre.group(1))
            classe = "section-title" if niveau <= 2 else "section-subtitle"
            html.append(f'<h{niveau} class="{classe}">{_inline_markdown(titre.group(2))}</h{niveau}>')
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

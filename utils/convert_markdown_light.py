import re

def md_light_to_html(text: str) -> str:
    if not text:
        return ""
    
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
            # gras **...**
            p = re.sub(r'\*\*(.+?)\*\*', r'<strong>\1</strong>', p)
            html.append(f"<p>{p}</p>")
            para_buf = []

    for raw in text.splitlines():
        line = raw.strip()

        # Ligne vide -> fin de paragraphe éventuel
        if not line:
            flush_ul()
            flush_para()
            continue

        # Titres ##
        if line.startswith('## '):
            flush_ul()
            flush_para()
            titre = line[3:].strip()
            html.append(f'<h2 class="section-title">{titre}</h2>')
            continue

        # Puces -
        if line.startswith('- '):
            flush_para()
            if not in_ul:
                html.append('<ul>')
                in_ul = True
            item = line[2:].strip()
            item = re.sub(r'\*\*(.+?)\*\*', r'<strong>\1</strong>', item)
            html.append(f'<li>{item}</li>')
            continue

        # Sinon : ligne de paragraphe → on accumule
        # (et on normalise déjà le gras)
        line = re.sub(r'\*\*(.+?)\*\*', r'<strong>\1</strong>', line)
        para_buf.append(line)

    # Fin de texte : flush
    flush_ul()
    flush_para()

    return '\n'.join(html)
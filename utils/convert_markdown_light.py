import re

def md_light_to_html(text: str) -> str:
    if not text:
        return ""
    
    html = []
    in_ul = False
    
    for line in text.split('\n'):
        line = line.strip()
        
        if not line:
            if in_ul:
                html.append('</ul>')
                in_ul = False
            continue
        
        # Titres ##
        if line.startswith('## '):
            if in_ul:
                html.append('</ul>')
                in_ul = False
            titre = line[3:].strip()
            html.append(f'<h2 class="section-title">{titre}</h2>')
        
        # Puces -
        elif line.startswith('- '):
            if not in_ul:
                html.append('<ul>')
                in_ul = True
            item = line[2:].strip()
            item = re.sub(r'\*\*(.+?)\*\*', r'<strong>\1</strong>', item)
            html.append(f'<li>{item}</li>')
        
        # Paragraphe
        else:
            if in_ul:
                html.append('</ul>')
                in_ul = False
            line = re.sub(r'\*\*(.+?)\*\*', r'<strong>\1</strong>', line)
            html.append(f'<p>{line}</p>')
    
    if in_ul:
        html.append('</ul>')
    
    return '\n'.join(html)
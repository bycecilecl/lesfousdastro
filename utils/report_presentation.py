"""Présentation des textes de rapports, sans calcul ni appel IA."""
import re
import markdown


def report_text_to_html(text):
    """Convertit le Markdown sous les titres h2 déjà fournis par le rapport."""
    html = markdown.markdown(text or "", extensions=["extra"])
    def heading(match):
        slash, level = match.groups()
        return f"<{slash}h{min(int(level) + 2, 6)}"
    return re.sub(r"<(/?)h([1-6])(?=[\s>])", heading, html)

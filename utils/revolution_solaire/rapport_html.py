"""Rendu HTML lisible des rapports de révolution solaire."""

from __future__ import annotations

from pathlib import Path
import re

import markdown


def generer_rapport_html(texte_markdown: str, chemin: Path, *, nom: str, annee: int) -> Path:
    """Convertit le Markdown Claude en un document HTML autonome."""
    contenu = markdown.markdown(
        texte_markdown.strip(),
        extensions=["extra", "nl2br", "sane_lists"],
    )
    contenu = re.sub(
        r"<p><em>(Repères techniques\s*:.*?)</em></p>",
        r'<p class="technical-details"><em>\1</em></p>',
        contenu,
        flags=re.IGNORECASE | re.DOTALL,
    )
    avertissement = """
<div class="disclaimer">
  <p><strong>⚠ À propos de cette révolution solaire :</strong><br>
  Elle propose une lecture symbolique des dynamiques de ton année. L'astrologie éclaire des tendances et des périodes possibles ; elle ne remplace ni ton discernement, ni une décision personnelle, médicale, juridique ou financière.</p>
  <p><strong>Note technique :</strong> Les positions, maisons et aspects sont calculés automatiquement. L'interprétation est rédigée avec l'aide d'un système d'IA : de petites répétitions ou imprécisions de formulation peuvent parfois apparaître. Rien ne remplace un échange humain pour approfondir ton vécu et ton thème.</p>
</div>
"""
    html = f"""<!doctype html>
<html lang="fr">
<head>
  <meta charset="utf-8">
  <meta name="viewport" content="width=device-width, initial-scale=1">
  <title>Révolution solaire {annee} — {nom}</title>
  <style>
    :root {{
      --ink: #2b2530;
      --plum: #5e315f;
      --rose: #b8749d;
      --paper: #fffdf9;
      --mist: #f7eff3;
      --line: #e7d8e0;
    }}
    * {{ box-sizing: border-box; }}
    body {{
      max-width: 860px; margin: 0 auto; padding: 56px 28px 80px;
      color: var(--ink); background: var(--paper);
      font: 18px/1.72 Georgia, "Times New Roman", serif;
    }}
    h1, h2, h3 {{ font-family: Arial, Helvetica, sans-serif; line-height: 1.18; color: var(--plum); }}
    h1 {{ margin: 0 0 2.8rem; font-size: clamp(2.2rem, 6vw, 3.5rem); letter-spacing: -.04em; }}
    h2 {{ margin: 3.2rem 0 1.1rem; padding-top: 1.2rem; border-top: 1px solid var(--line); font-size: 1.65rem; }}
    h3 {{ margin: 2rem 0 .7rem; color: #82446f; font-size: 1.18rem; }}
    p {{ margin: 0 0 1.25rem; }}
    strong {{ color: #4c284c; }}
    em {{ color: #614f61; }}
    .technical-details {{ margin: -.35rem 0 1.5rem; padding: .65rem .85rem; border-left: 3px solid var(--rose); border-radius: 0 8px 8px 0; background: var(--mist); color: #614f61; font: .88rem/1.55 Arial, Helvetica, sans-serif; }}
    .disclaimer {{ margin: 0 0 2.5rem; padding: 1rem 1.1rem; border: 1px solid #dee2e6; border-radius: 8px; background: #f8f9fa; color: #4d4d4d; font: .78rem/1.5 Arial, Helvetica, sans-serif; }}
    .disclaimer p {{ margin: 0 0 .75rem; }} .disclaimer p:last-child {{ margin-bottom: 0; }}
    ul, ol {{ margin: 0 0 1.35rem; padding-left: 1.35rem; }}
    li {{ margin-bottom: .45rem; }}
    blockquote {{ margin: 1.8rem 0; padding: .8rem 1.15rem; border-left: 4px solid var(--rose); background: var(--mist); color: #493846; }}
    hr {{ border: 0; border-top: 1px solid var(--line); margin: 2.7rem 0; }}
    table {{ width: 100%; margin: 1.5rem 0; border-collapse: collapse; font-family: Arial, Helvetica, sans-serif; font-size: .92rem; }}
    th, td {{ padding: .7rem; text-align: left; vertical-align: top; border-bottom: 1px solid var(--line); }}
    th {{ background: var(--mist); color: var(--plum); }}
    @media print {{ body {{ max-width: none; padding: 1.2cm; font-size: 11pt; }} h2 {{ break-after: avoid; }} }}
  </style>
</head>
<body>
{avertissement}
{contenu}
</body>
</html>
"""
    chemin.write_text(html, encoding="utf-8")
    return chemin

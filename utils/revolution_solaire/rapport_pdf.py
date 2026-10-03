"""Habillage PDF de la Révolution solaire, aligné sur les autres analyses."""
from __future__ import annotations

import base64
from datetime import date
from html import escape
from pathlib import Path
import re


LOGO = Path(__file__).resolve().parents[2] / "static" / "images" / "logo_les_fous_dastro.webp"


def _date_fr(valeur: str) -> str:
    try:
        return date.fromisoformat(valeur).strftime("%d/%m/%Y")
    except (TypeError, ValueError):
        return str(valeur or "")


def habiller_rapport_pdf(html_rapport: str, *, personne: dict, lieu_rs: dict, annee: int) -> str:
    """Conserve le texte du rapport et lui donne la présentation PDF du site."""
    corps = re.search(r"<body\b[^>]*>(.*?)</body>", html_rapport, flags=re.I | re.S)
    if not corps:
        raise ValueError("Le rapport RS ne contient pas de corps HTML.")
    contenu = corps.group(1).strip()
    # Le titre du Markdown est remplacé par l'en-tête client illustré.
    contenu = re.sub(r"<h1\b[^>]*>.*?</h1>", "", contenu, count=1, flags=re.I | re.S)
    avertissement = re.search(r'<div class="disclaimer">.*?</div>', contenu, flags=re.I | re.S)
    couverture_avertissement = avertissement.group(0) if avertissement else ""
    if avertissement:
        contenu = contenu[:avertissement.start()] + contenu[avertissement.end():]
    logo_base64 = base64.b64encode(LOGO.read_bytes()).decode("ascii")
    nom = escape(str(personne.get("nom") or ""))
    naissance = " — ".join(escape(str(part)) for part in (
        _date_fr(personne.get("date")), personne.get("heure") or "", personne.get("lieu") or ""
    ) if part)
    lieu = escape(str(lieu_rs.get("lieu") or ""))
    return f"""<!doctype html>
<html lang="fr">
<head>
  <meta charset="utf-8">
  <title>Révolution solaire {annee} - {nom}</title>
  <style>
    body {{ font-family: Georgia, serif; margin: 0; padding: 40px; background: #fff;
            color: #2c3e50; line-height: 1.6; }}
    .container {{ max-width: 800px; margin: 0 auto; }}
    .cover {{ break-after: page; }}
    .header {{ text-align: center; margin-bottom: 30px; padding-bottom: 20px;
               border-bottom: 1px solid #eee; break-after: avoid; }}
    .logo {{ display: block; width: auto; height: auto; max-width: 150px;
             max-height: 80px; margin: 0 auto 12px; object-fit: contain; }}
    .header h1 {{ color: #333; font-size: 24px; margin: 0 0 5px; }}
    .personal-info {{ color: #666; font-size: 14px; margin: 5px 0 0; text-align: center; }}
    .return-info {{ color: #1f628e; font-size: 13px; margin: 3px 0 0; text-align: center; }}
    main {{ font-size: 13px; }}
    main h2 {{ color: #34495e; border-bottom: 2px solid #3498db;
               padding-bottom: 5px; margin: 35px 0 15px; break-after: avoid; }}
    main h3 {{ color: #34495e; margin: 27px 0 10px; break-after: avoid; }}
    main p {{ margin: 0 0 15px; text-align: justify; }}
    main ul, main ol {{ margin: 0 0 16px; padding-left: 22px; }}
    main li {{ margin-bottom: 6px; }}
    .disclaimer {{ background: #f8f9fa; border: 1px solid #dee2e6;
                   padding: 16px; margin: 20px 0 30px; border-radius: 8px;
                   font-size: 13px; line-height: 1.5; break-inside: avoid; }}
    .disclaimer p {{ text-align: left; margin: 0 0 8px; }}
    .disclaimer p:last-child {{ margin-bottom: 0; }}
    .technical-details {{ background: #f4f7f9; border-left: 3px solid #3498db;
                          border-radius: 0 6px 6px 0; padding: 9px 12px;
                          color: #526676; font-size: 11px; line-height: 1.5;
                          text-align: left; break-inside: avoid; }}
    blockquote {{ border-left: 3px solid #3498db; padding: 7px 14px;
                  margin: 18px 0; background: #f4f7f9; }}
    table {{ width: 100%; border-collapse: collapse; font-size: 11px; }}
    th, td {{ padding: 6px; border-bottom: 1px solid #d8e3ea; text-align: left; }}
    footer {{ text-align: center; border-top: 1px solid #eee; padding-top: 15px;
              margin-top: 35px; color: #666; font-size: 11px; }}
    footer p {{ margin: 4px 0; }}
    @media print {{ body {{ padding: 20px; }} .container {{ max-width: none; }} }}
  </style>
</head>
<body>
  <div class="container">
    <div class="cover">
      <div class="header">
        <img src="data:image/webp;base64,{logo_base64}" alt="Logo Les Fous d'Astro" class="logo">
        <h1>Révolution Solaire - {nom}</h1>
        <p class="personal-info">{naissance}</p>
        <p class="return-info">Année {annee} — {lieu}</p>
      </div>
      {couverture_avertissement}
      <footer>
        <p><strong>Les Fous d'Astro</strong> - Analyse générée automatiquement</p>
        <p>lesfousdastro.fr | bycecilecl.com | contact@lesfousdastro.fr</p>
        <p>IG : @lesfousdastro • @bycecilecl</p>
      </footer>
    </div>
    <main>{contenu}</main>
  </div>
</body>
</html>"""

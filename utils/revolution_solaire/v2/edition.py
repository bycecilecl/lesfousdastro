"""Finalisation éditoriale locale : aucun fournisseur IA importé ou appelé."""

from dataclasses import asdict
from datetime import datetime
from html import escape
import json
from pathlib import Path
from zoneinfo import ZoneInfo

from ..archives_generation import ecrire_json, lire_json, verrou_demande
from .analyse import ETAPES
from .controle import controler_rapport_final_rs
from .dossier import controler_completude_dossier
from .service import RapportRSV2, assembler_rapport_rs


def date_locale(valeur, fuseau="Europe/Paris"):
    return datetime.fromisoformat(valeur).astimezone(ZoneInfo(fuseau)).strftime("%d/%m/%Y %H:%M")


def reperes_transit(fait, fuseau="Europe/Paris"):
    """Dates et nature du repère proviennent des calculs, jamais du rédacteur."""
    evenement = fait["valeur"]
    datation = evenement.get("datation") or {}
    nom = f"{evenement['planete_transit']} en transit — {evenement['aspect']} {evenement['cible']} {evenement['reference']}"
    if evenement.get("axe_noeuds"):
        contacts = " / ".join(f"{aspect} {noeud}" for noeud, aspect in evenement["axe_noeuds"].items())
        nom = f"{evenement['planete_transit']} en transit — {contacts} ({evenement['reference']})"
    if evenement.get("axe_angles"):
        contacts = " / ".join(f"{aspect} {angle}" for angle, aspect in evenement["axe_angles"].items())
        nom = f"{evenement['planete_transit']} en transit — {contacts} ({evenement['reference']})"
    reperes = [datation, *evenement.get("contacts_complementaires_axe", [])]
    dates_exacts = sorted({p["date_utc"] for r in reperes for p in r.get("passages_exacts", [])})
    exacts = ", ".join(date_locale(date, fuseau) for date in dates_exacts)
    stations = "; ".join(
        f"{date_locale(p['date_utc'], fuseau)} : {p['sens_apres']}, orbe {p['orbe']:.2f}°"
        for p in datation.get("stations", []))
    absence = "Aucun passage exact calculé dans le cycle" if datation else "Datation non affinée : aucun passage exact certifié"
    return {"contact": nom, "exacts": exacts or absence,
            "stations": stations or "—"}


def _fenetre(evenement):
    axe = evenement.get("fenetre_axe")
    if axe:
        if "debut_utc" in axe:
            return date_locale(axe["debut_utc"]) + " → " + date_locale(axe["fin_utc"])
        return axe["debut"] + " → " + axe["fin"] + " (fenêtre quotidienne)"
    datation = evenement.get("datation") or {}
    if datation:
        return date_locale(datation["entree_utc"]) + " → " + date_locale(datation["sortie_utc"])
    return str(evenement.get("debut", "—")) + " → " + str(evenement.get("fin", "—")) + " (fenêtre quotidienne)"


def _paragraphes(texte):
    return "".join("<p>" + escape(p).replace("\n", "<br>") + "</p>"
                   for p in texte.split("\n\n") if p.strip())


def _table(entetes, lignes):
    return '<div class="table"><table><thead><tr>' + "".join(
        "<th>" + escape(str(c)) + "</th>" for c in entetes
    ) + "</tr></thead><tbody>" + "".join(
        "<tr>" + "".join("<td>" + escape(str(c)) + "</td>" for c in ligne) + "</tr>"
        for ligne in lignes) + "</tbody></table></div>"


def _position(p):
    # La valeur du calcul est décimale : 14,39° n'est pas 14°39′.
    minutes = round(p["degre_dans_signe"] * 60)
    return f"{p['signe']} {minutes // 60}°{minutes % 60:02d}′"


def _annexes(dossier):
    html = "<h2 id='inventaires'>Inventaires et repères calculés</h2>"
    for ref in ("natal", "rs"):
        carte = dossier[ref]
        sens = "natal_vers_rs" if ref == "natal" else "rs_vers_natal"
        projections = dossier["comparaison"]["maisons"][sens]
        lignes = []
        for nom, p in carte["positions"].items():
            mouvement = "Rétrograde" if p["retrograde"] else "Direct" if p["retrograde"] is False else "Sans objet"
            lignes.append((nom, _position(p), p["maison"], mouvement, projections["points"][nom]["maison_cible"]))
        for nom, p in carte["angles"].items():
            lignes.append((nom, _position(p), "Angle", "—", projections["points"][nom]["maison_cible"]))
        html += f"<h3>Positions {'natales' if ref == 'natal' else 'RS'}</h3>" + _table(
            ["Point", "Position", "Maison de sa carte", "Mouvement", "Projeté en maison de l’autre carte"], lignes)
        html += "<h3>Les douze cuspides " + ref + "</h3>" + _table(
            ["Maison", "Cuspide", "Maîtres", "Cuspide projetée en maison de l’autre carte"],
            [(n, _position(p), ", ".join(carte["maitrises"][n]["maitres"]),
              projections["cuspides"][n]["maison_cible"]) for n, p in carte["cuspides"].items()])
    html += "<p>La projection d’une cuspide indique où tombe le début de la maison. Elle ne signifie pas que toute la maison tient dans la maison cible.</p>"
    html += "<details><summary>Tous les contacts RS–natal retenus</summary>" + _table(
        ["Point RS", "Aspect", "Point natal", "Orbe"],
        [(e["point_rs"], e["aspect"], e["point_natal"], f"{e['orbe']:.2f}°")
         for e in dossier["comparaison"]["contacts"]]) + "</details>"
    for ref in ("natal", "rs"):
        html += f"<details><summary>Aspects internes {ref}</summary>" + _table(
            ["Point", "Aspect", "Point", "Orbe"],
            [(e["planete1"], e["aspect"], e["planete2"], f"{e['orbe']:.2f}°")
             for e in dossier[ref]["aspects"]]) + "</details>"
    html += "<details><summary>Toutes les fenêtres de transit calculées</summary><p>Heure de Paris. Une station proche d’un aspect ne devient pas un passage exact. Les transits étudiés sont ceux de Mars, Jupiter, Saturne, Uranus, Neptune et Pluton.</p>" + _table(
        ["Référence", "Contact", "Fenêtre sous orbe", "Passages exacts", "Stations de la planète mobile"],
        [(cle, r["contact"], _fenetre(fait["valeur"]), r["exacts"], r["stations"])
         for cle, fait in dossier["faits"].items() if cle.startswith("TRANSIT.")
         for r in [reperes_transit(fait)]]) + "</details>"
    return html


def exporter_rapport_revu(dossier_generation, corps, conclusion, *, provenance):
    """Contrôle, archive et affiche une édition revue sans nouvelle génération."""
    if not isinstance(provenance, str) or not provenance.strip():
        raise ValueError("La provenance de la relecture locale doit être renseignée.")
    dossier = Path(dossier_generation).resolve()
    demande = lire_json(dossier, "demande.json")
    with verrou_demande(demande, dossier.parent) as verrouille:
        if verrouille != dossier:
            raise ValueError("Le dossier ne correspond pas à sa demande.")
        factuel = lire_json(dossier, "dossier_factuel.json")
        controler_completude_dossier(factuel)
        analyses = {nom: lire_json(dossier / nom, "resultat.json") for nom in ETAPES}
        texte = assembler_rapport_rs(corps, conclusion, factuel["cycle"]["annee"])
        controle = controler_rapport_final_rs(texte, factuel, analyses, corps, conclusion)
        edition = dossier / "edition_locale"
        edition.mkdir(exist_ok=True, mode=0o700)
        ecrire_json(edition, "corps.json", corps)
        ecrire_json(edition, "conclusion.json", conclusion)
        ecrire_json(edition, "provenance.json", {"mode": "relecture_locale_sans_appel_ia", "detail": provenance})
        ecrire_json(edition, "controle.json", controle)
        personne = demande["personne"]
        lieu_rs = demande["lieu_rs"]
        annee = factuel["cycle"]["annee"]
        contenu = f"<header><small>RÉVOLUTION SOLAIRE V2 · {annee}–{annee + 1}</small><h1>Ton année, {escape(personne['nom'])}</h1><p>{date_locale(factuel['cycle']['debut_utc'])} → {date_locale(factuel['cycle']['fin_utc'])} (heure de Paris).</p></header>"
        contenu += "<aside>Version de lecture complète. Naissance : " + escape(str(personne.get("heure", ""))) + " à " + escape(str(personne.get("lieu", ""))) + "; RS à " + escape(str(lieu_rs.get("lieu", ""))) + ". Textes repris et corrigés localement par Codex ; conclusion rédigée par Codex. Aucun nouvel appel Claude pour cette édition.</aside>"
        contenu += "<nav><a href='#conclusion'>Conclusion personnalisée</a> · <a href='#inventaires'>Inventaires et calendrier calculé</a></nav>"
        for s in corps["sections"]:
            contenu += "<section><h2>" + escape(s["titre"]) + "</h2>" + _paragraphes(s["texte"])
            refs = [cle for cle in s["preuves"] if cle.startswith("TRANSIT.")]
            if s.get("role") == "periode":
                contenu += "<p><small>Repères calculés : le tableau conserve toutes les reprises du contact dans le cycle, y compris hors du mois de cette section. Une station n’est pas un passage exact.</small></p>"
                contenu += _table(["Repère calculé — heure de Paris", "Passages exacts", "Stations"],
                                  [(r["contact"], r["exacts"], r["stations"])
                                   for cle in refs for r in [reperes_transit(factuel["faits"][cle])]])
            contenu += "</section>"
        contenu += "<section><h2 id='conclusion'>Ce que cette année te demande vraiment</h2>" + _paragraphes(conclusion["texte"]) + "</section>"
        contenu += _annexes(factuel)
        style = "body{margin:0;background:#f7f5f0;color:#27252e;font:18px/1.7 system-ui}main{max-width:960px;margin:auto;padding:36px 24px}header{padding:32px 0}h1{font-size:44px;margin:12px 0}h2{line-height:1.3;margin:45px 0 20px;color:#3f3056}small{letter-spacing:.1em}aside{padding:20px;background:#e9e2ef;border-left:4px solid #70548c;font-size:15px}nav{padding:22px 0}a{color:#594272}section{border-bottom:1px solid #ddd;padding-bottom:24px}table{border-collapse:collapse;width:100%;font-size:14px}th,td{text-align:left;border-bottom:1px solid #ddd;padding:10px;vertical-align:top}th{background:#eee8f2}.table{overflow-x:auto}details{margin:25px 0}summary{cursor:pointer;font-weight:bold}"
        html = '<!doctype html><html lang="fr"><meta charset="utf-8"><meta name="viewport" content="width=device-width"><title>Révolution solaire V2 — ' + escape(personne['nom']) + f' {annee}–{annee + 1}</title><style>' + style + "</style><body><main>" + contenu + "</main></body></html>"
        rapport = RapportRSV2(texte_markdown=texte, html=html,
                            debut_cycle=factuel["cycle"]["debut_utc"], fin_cycle=factuel["cycle"]["fin_utc"],
                            identifiant_generation=dossier.name, dossier_generation=str(dossier))
        (edition / "rapport.html").write_text(html, encoding="utf-8")
        (edition / "rapport.md").write_text(texte, encoding="utf-8")
        ecrire_json(edition, "rapport.json", asdict(rapport))
        # Reprise normale du service : même cache, mêmes contrôles et aucun
        # nouvel appel fournisseur. Les réponses Claude brutes restent intactes.
        for nom, resultat in (("redaction_corps", corps), ("conclusion_contextuelle", conclusion)):
            partie = dossier / nom
            partie.mkdir(exist_ok=True, mode=0o700)
            ancien = lire_json(partie, "resultat.json")
            if ancien is not None and lire_json(partie, "avant_edition_locale.json") is None:
                ecrire_json(partie, "avant_edition_locale.json", ancien)
            ecrire_json(partie, "resultat.json", resultat)
            ecrire_json(partie, "reponse_completee.json", {
                "texte": json.dumps(resultat, ensure_ascii=False),
                "origine": "edition_locale", "source": "edition_locale/provenance.json"})
        ecrire_json(dossier, "controle_final.json", controle)
        ecrire_json(dossier, "rapport.json", asdict(rapport))
        (dossier / "rapport.html").write_text(html, encoding="utf-8")
        (dossier / "rapport.md").write_text(texte, encoding="utf-8")
        ecrire_json(dossier, "etat.json", {"statut": "termine", "etape": "rapport",
                                         "mode": "edition_locale_sans_appel_ia"})
        return rapport

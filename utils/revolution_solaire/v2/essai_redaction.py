"""Rédaction manuelle 7–8 depuis six archives ; aucun recalcul ni relance.

Les archives sources restent intactes. Ce parcours produit un brouillon,
jamais un rapport déclaré validé pour livraison.
"""

from copy import deepcopy
from html import escape
import hashlib
import re
from pathlib import Path

from ..archives_generation import ecrire_json, lire_json, verrou_demande, GenerationAbsente
from . import analyse
from .controle import AnalyseRSInvalide, controler_redaction
from .dossier import controler_completude_dossier
from .filtrage_aspects import filtrer_historique
from .releve_rs import references_prompt, degres_minutes, FIGURES
from .memoire_redaction import construire_memoire, faits_pour_redaction
from .service import _etape_archivee, _fournisseur_borne, _notifier, assembler_rapport_rs


VERSION_BROUILLON = "redaction_memoire_quatre_periodes_2"


def _cle(libelle):
    return re.sub(r"\s*/\s*", "/", libelle.strip())


def _aliases_calcules(faits, etape):
    """Uniquement des libellés reconstruits à partir de faits déjà calculés."""
    catalogue = ({k: v for k, v in faits.items() if k.startswith("RS.")}
                 if etape == "rs_seule" else faits)
    refs = references_prompt({"etape": etape, "faits": catalogue})
    aliases = {}

    def ajouter(libelle, cle):
        nom = _cle(libelle)
        if nom in aliases and aliases[nom] != cle:
            raise AnalyseRSInvalide("Libellé d'archive ambigu : " + libelle)
        aliases[nom] = cle

    for cle, libelle in refs.items():
        ajouter(libelle, cle)
        fait, valeur = faits[cle], faits[cle]["valeur"]
        categorie = fait["type"]
        if categorie == "aspects":
            ajouter(libelle + f" (orbe {degres_minutes(valeur['orbe'])})", cle)
        elif categorie == "angularites":
            ajouter(libelle + f" : orbe {degres_minutes(valeur['orbe'])}", cle)
        elif categorie == "angles":
            ajouter(libelle + f" : {fait['objet']}, {degres_minutes(valeur['degre_dans_signe'])}, {valeur['signe']}", cle)
        elif categorie == "positions":
            dignite = valeur.get("dignite_essentielle")
            morceaux = [libelle, valeur["signe"]]
            if dignite and dignite != "neutre":
                morceaux.append(dignite)
            morceaux.append("maison " + str(valeur["maison"]))
            ajouter(", ".join(morceaux), cle)
        elif categorie == "configurations":
            description = (FIGURES.get(valeur["type"], valeur["type"]) + " : "
                           + "–".join(valeur.get("planetes", [])))
            ajouter(libelle + " — " + description, cle)
    return aliases


def preparer_redaction_archivee(sources, cas):
    """Lecture seule : six réponses, leurs faits et leurs statuts originaux."""
    if set(sources) != set(analyse.ETAPES):
        raise ValueError("La rédaction depuis les archives exige les six sources d'analyse.")
    analyses, statuts, empreintes, adaptations = {}, {}, {}, []
    factuel = demande_source = None
    ids = set()
    for etape in analyse.ETAPES:
        source = Path(sources[etape]).expanduser().resolve()
        dossier = lire_json(source, "dossier_factuel.json")
        reponse = lire_json(source / etape, "reponse.json")
        controle = lire_json(source / etape, "controle.json")
        if any(v is None for v in (dossier, reponse, controle)):
            raise ValueError("Archive incomplète pour " + etape + ". Aucun appel lancé.")
        if factuel is None:
            factuel = dossier
            demande_source = lire_json(source, "demande.json")
            if demande_source is None:
                raise ValueError("Profil de l'archive RS seule absent.")
            for champ in ("personne", "lieu_rs", "annee"):
                if cas.get(champ) != demande_source.get(champ):
                    raise ValueError("Le profil diffère de l'archive pour " + champ + ". Aucun appel lancé.")
        elif dossier != factuel:
            raise ValueError("Les faits de " + etape + " ne correspondent pas au même thème.")
        original = analyse.parser_json_reponse(reponse["texte"])
        resultat = analyse.normaliser_identifiants_enjeux(original, etape)
        aliases = _aliases_calcules(factuel["faits"], etape)
        copie = {"enjeux": []}
        if etape == "rs_seule":
            if not isinstance(resultat.get("ambiance"), str):
                raise AnalyseRSInvalide("Ambiance RS absente de l'archive.")
            copie["ambiance"] = resultat["ambiance"]
        if not isinstance(resultat.get("enjeux"), list) or not resultat["enjeux"]:
            raise AnalyseRSInvalide("Enjeux archivés absents pour " + etape)
        for enjeu in resultat["enjeux"]:
            champs = ("id", "titre", "importance", "lecture", "preuves", "liens", "effet", "exemples")
            if not isinstance(enjeu, dict) or any(c not in enjeu for c in champs):
                raise AnalyseRSInvalide("Enjeu archivé incomplet dans " + etape)
            e = {c: deepcopy(enjeu[c]) for c in champs}
            if not isinstance(e["id"], str) or not e["id"].startswith(etape + "-") or e["id"] in ids:
                raise AnalyseRSInvalide("Identifiant d'enjeu ambigu dans " + etape)
            ids.add(e["id"])
            if "periodes" in enjeu:
                e["periodes"] = deepcopy(enjeu["periodes"])
            if not isinstance(e["exemples"], list) or any(not isinstance(x, dict) for x in e["exemples"]):
                raise AnalyseRSInvalide("Exemples archivés illisibles.")
            for objet in [e, *e["exemples"]]:
                if not isinstance(objet.get("preuves"), list):
                    raise AnalyseRSInvalide("Preuves archivées illisibles.")
                converties = []
                for ref in objet["preuves"]:
                    if not isinstance(ref, str):
                        raise AnalyseRSInvalide("Référence archivée non textuelle.")
                    cle = ref if ref in factuel["faits"] else aliases.get(_cle(ref))
                    if cle is None:
                        raise AnalyseRSInvalide("Référence inconnue dans " + e["id"] + " : " + ref)
                    if cle not in converties:
                        converties.append(cle)
                    if cle != ref:
                        adaptations.append({"etape": etape, "reference_source": ref, "reference_interne": cle})
                objet["preuves"] = converties
            if "periodes" in e and any(p not in factuel["faits"] or not p.startswith("TRANSIT.")
                                       for p in e["periodes"]):
                raise AnalyseRSInvalide("Période de transit archivée inconnue.")
            copie["enjeux"].append(e)
        analyses[etape] = copie
        statuts[etape] = {"statut_controle_source": controle.get("statut", "inconnu"),
                          "raison_controle_source": controle.get("raison", ""),
                          "usage": "Interprétation provisoire ; faits calculés prioritaires ; validation humaine non acquise."}
        noms = ("dossier_factuel.json", "demande.json", etape + "/reponse.json", etape + "/controle.json")
        empreintes[etape] = {"dossier": str(source), "fichiers": {
            nom: hashlib.sha256((source / nom).read_bytes()).hexdigest() for nom in noms}}
    controler_completude_dossier(factuel)
    analyses = filtrer_historique(analyses, factuel["faits"])
    return {"factuel": factuel, "analyses": analyses, "statut_historique": statuts,
            "provenance": empreintes, "adaptations_references": adaptations,
            "demande_source": demande_source}


def rendre_brouillon(dossier, cas):
    """Affiche aussi une réponse bloquée ; ne réécrit jamais son texte."""
    import markdown
    from .edition import _annexes

    dossier = Path(dossier)
    parties, erreurs = {}, {}
    for etape in ("redaction_corps", "conclusion_contextuelle"):
        controle = lire_json(dossier / etape, "controle.json") or {}
        erreurs[etape] = controle
        reponse = lire_json(dossier / etape, "reponse.json")
        if reponse is None:
            reponse = lire_json(dossier / etape, "reponse_partielle.json")
        if reponse:
            try:
                parties[etape] = analyse.parser_json_reponse(reponse["texte"])
            except AnalyseRSInvalide:
                parties[etape] = {"fragment_brut": reponse["texte"]}
    for nom in ("controle_redaction.json", "controle_corps.json", "controle_brouillon.json", "etat.json"):
        controle = lire_json(dossier, nom)
        if controle is not None:
            erreurs[nom] = controle
    if not parties:
        return None
    corps, conclusion = parties.get("redaction_corps", {}), parties.get("conclusion_contextuelle", {})
    sections = corps.get("sections", [])
    blocs = [f"# Ta révolution solaire {cas['annee']}"]
    for s in sections if isinstance(sections, list) else []:
        if isinstance(s, dict) and isinstance(s.get("titre"), str) and isinstance(s.get("texte"), str):
            blocs.append("## " + " ".join(s["titre"].splitlines()) + "\n\n" + s["texte"])
    if isinstance(conclusion.get("texte"), str):
        blocs.append("## Ce que cette année te demande vraiment\n\n" + conclusion["texte"])
    texte = "\n\n".join(blocs)
    for nom, partie in parties.items():
        if "fragment_brut" in partie:
            texte += "\n\n## Réponse incomplète — " + nom + "\n\n" + partie["fragment_brut"]
    complet = bool(sections and isinstance(conclusion.get("texte"), str))
    avertissement = ("Brouillon complet à relire — parcours non validé pour livraison."
                    if complet else "Brouillon partiel — la génération n'a pas produit les deux parties complètes.")
    html = ("<!doctype html><html lang='fr'><meta charset='utf-8'>"
            "<meta name='viewport' content='width=device-width,initial-scale=1'>"
            "<title>RS V2 — brouillon de lecture</title><style>"
            "body{background:#faf8f4;color:#27252e;font:18px/1.7 system-ui;margin:40px auto;max-width:960px;padding:0 24px}"
            "h1,h2{line-height:1.3}h2{margin-top:40px}aside{background:#fff0d6;padding:18px}"
            "pre{white-space:pre-wrap;overflow-wrap:anywhere;font-size:13px}.table{overflow-x:auto}"
            "table{border-collapse:collapse;width:100%;font-size:14px}td,th{padding:10px;border-bottom:1px solid #ddd;text-align:left}"
            "details{margin:22px 0}summary{cursor:pointer}</style><body><aside>" + avertissement
            + " Les textes sont ceux de Claude ; les archives des six analyses sont conservées intactes.</aside>"
            + markdown.markdown(escape(texte, quote=False), extensions=["extra"])
            + "<details><summary>Contrôles des appels 7 et 8</summary><pre>"
            + escape(str(erreurs)) + "</pre></details>"
            + _annexes(lire_json(dossier, "dossier_factuel.json")) + "</body></html>")
    (dossier / "rapport_brouillon.html").write_text(html, encoding="utf-8")
    (dossier / "rapport_brouillon.md").write_text(avertissement + "\n\n" + texte, encoding="utf-8")
    return str(dossier / "rapport_brouillon.html")


def generer_redaction_archivee(preparation, cas, *, modele, stockage_dir, journal=None,
                               autoriser_generation=False, arreter_apres=None, dossier_reprise=None):
    """Deux appels maximum ; arrêt sur erreur, réponses servies depuis le cache en reprise."""
    if not autoriser_generation:
        raise GenerationAbsente("Cécile doit lancer elle-même ce parcours.")
    if arreter_apres not in (None, "redaction_corps"):
        raise ValueError("Ce parcours accepte le corps seul ou le corps et la conclusion.")
    demande = {"mode": VERSION_BROUILLON, "modele": modele, "sources": preparation["provenance"],
               "cas": cas, "empreinte_moteur": preparation["empreinte_moteur"]}
    if dossier_reprise is not None:
        source = Path(dossier_reprise).expanduser().resolve()
        archive = lire_json(source, "demande.json")
        if not isinstance(archive, dict):
            raise ValueError("Demande de rédaction à reprendre absente.")
        for cle in ("mode", "modele", "sources", "cas"):
            if archive.get(cle) != demande[cle]:
                raise ValueError("La reprise diffère de l'archive pour " + cle + ". Aucun appel lancé.")
        if lire_json(source / "redaction_corps", "reponse.json") is None:
            raise ValueError("Reprise refusée : réponse du corps absente. Aucun nouvel appel 7 autorisé.")
        demande, stockage_dir = archive, source.parent
    with verrou_demande(demande, Path(stockage_dir)) as dossier:
        if dossier_reprise is not None and dossier.resolve() != source:
            raise ValueError("Le dossier verrouillé ne correspond pas à la reprise.")
        ecrire_json(dossier, "demande.json", demande)
        ecrire_json(dossier, "dossier_factuel.json", preparation["factuel"])
        ecrire_json(dossier, "historique_utilise.json", preparation["analyses"])
        ecrire_json(dossier, "memoire_redaction.json", construire_memoire(preparation["analyses"]))
        ecrire_json(dossier, "statut_sources.json", preparation["statut_historique"])
        ecrire_json(dossier, "adaptations_references.json", preparation["adaptations_references"])
        appel = _fournisseur_borne(dossier, modele, 1 if arreter_apres else 2, journal=journal)
        factuel, analyses = preparation["factuel"], preparation["analyses"]
        from ..controle_livraison import controler_placements

        def reutiliser(nom, fonction):
            def executer(appeler):
                def verifier_prompt(prompt, **options):
                    partie = dossier / nom
                    if lire_json(partie, "reponse.json") is not None:
                        original = lire_json(partie, "prompt.json")
                        if original != {"prompt": prompt, "options": options}:
                            raise AnalyseRSInvalide("Le prompt " + nom + " a changé : reprise sans nouvel appel refusée.")
                    return appeler(prompt, **options)
                return fonction(verifier_prompt)
            return _etape_archivee(dossier, nom, executer, appel, journal=journal)

        try:
            corps = reutiliser("redaction_corps", lambda appeler:
                analyse.rediger_corps_rapport_rs(factuel, analyses, appeler=appeler,
                    genre=cas["personne"].get("genre", ""), statut_historique=preparation["statut_historique"]))
            classement = controler_redaction(corps, factuel, analyses, couverture_bloquante=False,
                                            faits_autorises=faits_pour_redaction(factuel, analyses))
            ecrire_json(dossier, "controle_redaction.json", classement)
            _notifier(journal, "classements_non_bloquants", details=classement["classements_non_bloquants"])
            _notifier(journal, "avertissements_couverture", details=classement["avertissements_couverture"], bloquant=False)
            controle = controler_placements("\n\n".join(s["texte"] for s in corps["sections"]), factuel["donnees_controle"])
            ecrire_json(dossier, "controle_corps.json", controle)
            _notifier(journal, "controle_placements", nom="redaction_corps", controle=controle)
            if controle["erreurs"]:
                raise AnalyseRSInvalide("Contradiction de placement dans le corps ; conclusion non lancée.")
            if arreter_apres is None:
                conclusion = reutiliser("conclusion_contextuelle", lambda appeler:
                    analyse.rediger_conclusion_contextuelle(factuel, analyses, corps,
                        cas.get("contexte_client", {}), appeler=appeler, genre=cas["personne"].get("genre", ""),
                        statut_historique=preparation["statut_historique"]))
                controle = controler_placements(assembler_rapport_rs(corps, conclusion, cas["annee"]), factuel["donnees_controle"])
                ecrire_json(dossier, "controle_brouillon.json", {**controle, "parcours_complet_valide": False})
                _notifier(journal, "controle_placements", nom="conclusion_contextuelle", controle=controle)
                if controle["erreurs"]:
                    raise AnalyseRSInvalide("Contradiction de placement dans le brouillon ; réponses conservées.")
            ecrire_json(dossier, "etat.json", {"statut": "brouillon_a_relire", "parcours_complet_valide": False})
            return {"dossier": str(dossier)}
        except BaseException as exc:
            ecrire_json(dossier, "etat.json", {"statut": "a_revoir", "parcours_complet_valide": False,
                                               "type_erreur": type(exc).__name__})
            raise
        finally:
            chemin = rendre_brouillon(dossier, cas)
            if chemin:
                _notifier(journal, "lecture_enregistree", chemin=chemin)

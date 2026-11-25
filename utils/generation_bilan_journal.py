"""Un bilan par période de 30 jours pour les abonnés, sans envoi ni relance après échec."""
from datetime import datetime, timezone
from hashlib import sha256
import json
import os
from uuid import uuid4

from utils.parametres_claude_espace import MODEL, preparer_parametres_claude
from utils.suivi_journal import LIMITE_PROMPT, MIN_NOTES_BILAN

FICHIERS = frozenset({"dossier.json", "prompt.txt", "requete.json", "reponse_brute.json", "usage.json", "controle.json", "bilan.txt", "erreur.json"})


def _json(valeur):
    return json.dumps(valeur, ensure_ascii=False, indent=2)


def parametres_bilan_journal(preparation):
    return preparer_parametres_claude({
        "model": os.getenv("ANTHROPIC_MODEL_BILAN_JOURNAL") or MODEL,
        "max_tokens": 3000,
        "messages": [{"role": "user", "content": preparation["prompt"]}],
    })


def empreinte_preparation(preparation):
    return sha256(_json(parametres_bilan_journal(preparation)).encode()).hexdigest()


def dossier_traces(bilan):
    from utils.stockage_espace import racine_privee_espace
    return racine_privee_espace() / "bilans_journal" / str(bilan.utilisateur_id) / bilan.id


def traces_conservees(bilan):
    """Relit les archives, avec les sources durables en base si le disque a changé."""
    contenus = {
        "dossier.json": bilan.dossier_json, "prompt.txt": bilan.prompt,
        "requete.json": bilan.parametres_json, "reponse_brute.json": bilan.reponse_brute,
        "usage.json": bilan.usage_json, "bilan.txt": bilan.texte, "erreur.json": bilan.erreur,
    }
    dossier = dossier_traces(bilan)
    for nom in FICHIERS:
        try:
            contenus[nom] = (dossier / nom).read_text(encoding="utf-8")
        except OSError:
            pass
    return {nom: contenu for nom, contenu in contenus.items() if contenu is not None}


def _ecrire(dossier, nom, contenu):
    with (dossier / nom).open("w", encoding="utf-8") as fichier:
        os.chmod(dossier / nom, 0o600)
        fichier.write(contenu)


def generer_bilan_journal(utilisateur, periode, preparation):
    """Un appel réservé à un compte payant actif, manuel ou planifié."""
    from flask import current_app
    from sqlalchemy.exc import IntegrityError
    from extensions import db
    from models.espace_personnel import BilanJournal30Jours
    from utils.acces_abonnement import exiger_droit_compte

    exiger_droit_compte(utilisateur.id, "bilan_journal_30j")
    from utils.suivi_journal import periode_suivi
    courante = periode_suivi(utilisateur, periode["fuseau"])
    if (periode["debut"], periode["fin"]) != (courante["debut"], courante["fin"]):
        raise ValueError("Cette fenêtre de suivi n’est plus la période courante. Aucun appel IA lancé.")

    if not periode["due"]:
        raise ValueError("La période de suivi n’est pas terminée.")
    if len(preparation["dossier"]["notes"]) < MIN_NOTES_BILAN:
        raise ValueError(f"Il faut au moins {MIN_NOTES_BILAN} notes dans la période. Aucun appel IA lancé.")
    if not preparation["taille_ok"] or len(preparation["prompt"]) > LIMITE_PROMPT:
        raise ValueError("Le dossier dépasse le budget prévu. Aucun appel IA lancé.")
    existant = BilanJournal30Jours.query.filter_by(
        utilisateur_id=utilisateur.id, debut=periode["debut"], fin=periode["fin"],
    ).first()
    if existant:
        return existant, False
    parametres = parametres_bilan_journal(preparation)
    bilan = BilanJournal30Jours(
        id=str(uuid4()), utilisateur_id=utilisateur.id,
        debut=periode["debut"], fin=periode["fin"], fuseau=periode["fuseau"],
        statut="en_cours", dossier_json=_json(preparation["dossier"]),
        prompt=preparation["prompt"], parametres_json=_json(parametres),
        precedent_id=preparation["precedent_id"],
    )
    traces = dossier_traces(bilan)
    traces.mkdir(mode=0o700, parents=True, exist_ok=False)
    os.chmod(traces, 0o700)
    for nom, contenu in (("dossier.json", bilan.dossier_json), ("prompt.txt", bilan.prompt), ("requete.json", _json(parametres))):
        _ecrire(traces, nom, contenu)
    print("[JOURNAL 1/4] Sources conservées ; réservation de la période.", flush=True)
    try:
        db.session.add(bilan)
        db.session.commit()
    except IntegrityError:
        db.session.rollback()
        existant = BilanJournal30Jours.query.filter_by(
            utilisateur_id=utilisateur.id, debut=periode["debut"], fin=periode["fin"],
        ).first()
        if existant is None:
            raise
        return existant, False
    bilan_id = bilan.id
    raison_refus = None

    def conserver_sortie(nom, contenu):
        try:
            _ecrire(traces, nom, contenu)
        except OSError:
            current_app.logger.error("Fichier %s indisponible ; résultat conservé en base pour le bilan %s.", nom, bilan_id)

    try:
        exiger_droit_compte(utilisateur.id, "bilan_journal_30j")
        # Import tardif : consulter ou préparer les sources ne charge aucun client IA.
        from utils.claude_espace import creer_message_claude, extraire_texte_claude
        print("[JOURNAL 2/4] Un seul appel Claude ; aucune relance automatique.", flush=True)
        reponse = creer_message_claude(**parametres)
        bilan.reponse_brute = reponse.model_dump_json(indent=2)
        usage = reponse.usage.model_dump(mode="json")
        bilan.usage_json = _json(usage)
        conserver_sortie("reponse_brute.json", bilan.reponse_brute)
        conserver_sortie("usage.json", bilan.usage_json)
        db.session.commit()
        texte = extraire_texte_claude(reponse)
        if reponse.stop_reason not in {"end_turn", "stop_sequence"}:
            raison_refus = "Réponse interrompue ; résultat brut conservé."
            raise ValueError(raison_refus)
        if texte.startswith("```") and texte.endswith("```"):
            texte = "\n".join(texte.splitlines()[1:-1]).strip()
        try:
            contenu = json.loads(texte)
        except json.JSONDecodeError:
            raison_refus = "La réponse n’est pas un JSON valide ; résultat brut conservé."
            raise
        if not isinstance(contenu, dict) or set(contenu) != {"bilan", "memoire_suivi"}:
            raison_refus = "Structure du bilan non conforme."
            raise ValueError(raison_refus)
        if any(not isinstance(contenu[c], str) or not contenu[c].strip() for c in ("bilan", "memoire_suivi")):
            raison_refus = "Bilan ou mémoire vide."
            raise ValueError(raison_refus)
        if len(contenu["memoire_suivi"]) > 2000:
            raison_refus = "Mémoire de suivi trop longue."
            raise ValueError(raison_refus)
        controle = {"valide": True, "stop_reason": reponse.stop_reason,
                    "nombre_notes": preparation["nombre_notes"], "caracteres_memoire": len(contenu["memoire_suivi"])}
        conserver_sortie("bilan.txt", contenu["bilan"])
        conserver_sortie("controle.json", _json(controle))
        bilan.texte, bilan.memoire_suivi = contenu["bilan"].strip(), contenu["memoire_suivi"].strip()
        bilan.statut, bilan.date_generation = "genere", datetime.now(timezone.utc)
        db.session.commit()
        print("[JOURNAL 3/4] Bilan et mémoire conservés dans l’historique.", flush=True)
        print("[JOURNAL 4/4] " + _json(controle) + "\nJournaux : " + str(traces), flush=True)
    except Exception as erreur:
        db.session.rollback()
        detail = {"type": type(erreur).__name__, "statut_http": getattr(erreur, "status_code", None),
                  "message": raison_refus or "Le bilan a échoué ou sa sauvegarde a été interrompue.",
                  "relance_automatique": False}
        print("[JOURNAL] " + _json(detail) + "\nJournaux : " + str(traces), flush=True)
        try:
            _ecrire(traces, "erreur.json", _json(detail))
            _ecrire(traces, "controle.json", _json({"valide": False, "type_erreur": detail["type"]}))
        except OSError:
            current_app.logger.error("Journaux incomplets pour le bilan de journal %s.", bilan_id)
        bilan = db.session.get(BilanJournal30Jours, bilan_id)
        if bilan.statut != "genere":
            bilan.statut, bilan.erreur = "echec", _json(detail)
            db.session.commit()
    return bilan, True

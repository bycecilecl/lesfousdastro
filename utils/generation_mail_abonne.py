"""Génération explicite d'un brouillon : un appel Claude, logs, aucun envoi."""
from datetime import datetime, timezone
from pathlib import Path
from contextlib import contextmanager
import json
import os
import re
import uuid
from urllib.parse import urlsplit

from flask import current_app
from extensions import db
from utils.brouillon_email_cycle import droits_email, generation_autorisee
from utils.email_cycle_abonnement import convertir_email_texte_en_html
from utils.dossier_mail_essentiel import dossier_essentiel, serialiser_dossier, verifier_budget_prompt
from utils.stockage_espace import racine_privee_espace


FICHIERS_MAIL = ("requete.json", "prompt.txt", "dossier_transmis.json", "controle_entree.json",
                "reponse_brute.txt", "usage.json", "controles.json", "brouillon.txt", "brouillon.html")


def _domaines_externes_mail(texte):
    """Contrôle les URL explicites sans ouvrir aucun lien."""
    domaines = set()
    for adresse in re.findall(r"(?:https?://|www\.)[^\s<>\[\]()\"']+", texte, flags=re.IGNORECASE):
        adresse = adresse.rstrip(".,;:!?")
        try:
            domaine = (urlsplit(adresse if "://" in adresse else "https://" + adresse).hostname or "").lower().rstrip(".")
        except ValueError:
            domaine = "adresse_invalide"
        if domaine != "lesfousdastro.fr" and not domaine.endswith(".lesfousdastro.fr"):
            domaines.add(domaine or "adresse_invalide")
    return sorted(domaines)


def _controle_structure_quinzaine(texte):
    """Contrôle le volume et la place de la RL, sans prétendre juger le fond."""
    from utils.mails_quinzaine import TITRES_MAIL_QUINZAINE

    def normaliser(ligne):
        return ligne.strip().strip("*# ").rstrip(":").strip().replace("’", "'").casefold()

    noms = {normaliser(titre): titre for titre in TITRES_MAIL_QUINZAINE}
    sections = {titre: [] for titre in TITRES_MAIL_QUINZAINE}
    ordre = []
    courante = None
    for ligne in texte.splitlines():
        titre = noms.get(normaliser(ligne))
        if titre is not None:
            ordre.append(titre)
            courante = titre
        elif courante is not None:
            sections[courante].append(ligne)
    nombre_mots = len(texte.split())
    mots_rl = len(" ".join(sections[TITRES_MAIL_QUINZAINE[1]]).split())
    paragraphes_rl = len([p for p in re.split(r"\n\s*\n", "\n".join(sections[TITRES_MAIL_QUINZAINE[1]])) if p.strip()])
    erreurs = []
    if ordre != list(TITRES_MAIL_QUINZAINE):
        erreurs.append("Les quatre sections attendues sont absentes, dupliquées ou dans le mauvais ordre.")
    if paragraphes_rl < 3:
        erreurs.append("La section RL doit développer au moins trois paragraphes.")
    return {
        "nombre_mots": nombre_mots, "mots_section_rl": mots_rl,
        "paragraphes_section_rl": paragraphes_rl, "erreurs": erreurs,
        "controle_du_fond": "non_automatise_relecture_humaine_requise",
    }


def dossier_journaux_mail():
    return racine_privee_espace() / "mails_cycles"


def journaux_mail(email_id):
    dossier = dossier_journaux_mail() / str(email_id)
    if not dossier.is_dir():
        return []
    return [{"id": p.name, "fichiers": [n for n in FICHIERS_MAIL if (p / n).is_file()]}
            for p in sorted(dossier.iterdir(), reverse=True) if p.is_dir()]


@contextmanager
def _verrou(email_id):
    dossier = dossier_journaux_mail()
    dossier.mkdir(parents=True, exist_ok=True)
    verrou = dossier / f"email-{email_id}.lock"
    try:
        fd = os.open(verrou, os.O_CREAT | os.O_EXCL | os.O_WRONLY, 0o600)
    except FileExistsError:
        raise ValueError("Ce brouillon est déjà en cours de génération. Aucun second appel lancé.")
    try:
        os.close(fd)
        yield
    finally:
        verrou.unlink(missing_ok=True)


def generer_mail_enregistre(email, profil, *, nouvel_essai=False, actualiser_journal=False):
    """L'appelant doit avoir explicitement demandé cette génération."""
    from utils.claude_espace import CLIENT, MODEL, creer_message_claude, ouvrir_flux_claude
    from utils.mails_quinzaine import VERSION_CONTRAT, actualiser_mail_quinzaine, preparer_essai_quinzaine, construire_prompt_quinzaine
    from utils.enjeux_annuels import actualiser_enjeux_email
    from utils.confidentialite_journal_mails import filtrer_preparation_journal_mails, lire_choix_journal_mails
    from models.espace_personnel import CycleLunaire

    if email.profil_id != profil.id:
        raise ValueError("Ce brouillon n’appartient pas à ce profil.")
    if actualiser_journal and not nouvel_essai:
        raise ValueError("L'actualisation du journal pour comparaison nécessite un nouvel essai séparé.")
    with _verrou(email.id):
        db.session.refresh(email)
        texte_existant = bool(email.contenu_texte or email.contenu_html)
        if texte_existant and not nouvel_essai:
            return email
        if nouvel_essai and not texte_existant:
            raise ValueError("Un nouvel essai nécessite un premier brouillon conservé pour comparaison.")
        preparation = json.loads(email.declencheur_factuel or "{}")
        if not generation_autorisee(droits_email(profil), preparation):
            raise ValueError("Ce brouillon ne correspond pas à ta formule actuelle.")
        if droits_email(profil).get("emails_par_mois") == 2 and preparation.get("version_contrat") != VERSION_CONTRAT:
            raise ValueError("Ce brouillon vient de l’ancien parcours mensuel. Prépare les deux créneaux civils depuis « Mes emails de cycle ».")
        if nouvel_essai:
            if preparation.get("version_contrat") != VERSION_CONTRAT:
                raise ValueError("Le dossier de ce brouillon est trop ancien pour ce parcours de comparaison.")
            # Les cartes restent celles du premier appel. La relecture avec
            # les notes ajoutées depuis nécessite une option explicite.
            preparation = preparer_essai_quinzaine(
                profil, preparation, actualiser_journal=actualiser_journal,
            )
        elif preparation.get("version_contrat") == VERSION_CONTRAT:
            preparation = actualiser_mail_quinzaine(profil, preparation)
        elif email.cycle_lunaire_id:
            cycle = db.session.get(CycleLunaire, email.cycle_lunaire_id)
            if cycle:
                preparation = actualiser_enjeux_email(profil, preparation, cycle.debut_cycle_utc.replace(tzinfo=timezone.utc))
        # Reconstruire le prompt filtré : ne jamais réutiliser un ancien texte
        # contenant des notes après un retrait d'autorisation.
        preparation = filtrer_preparation_journal_mails(profil, preparation)
        if preparation.get("version_contrat") == VERSION_CONTRAT:
            preparation["prompt"] = construire_prompt_quinzaine(
                profil.prenom, preparation["contrat"], preparation["contexte_client"],
            )
        elif preparation.get("portee", "complet") == "complet":
            from utils.email_cycle_abonnement import construire_prompt_email_cycle
            preparation["prompt"] = construire_prompt_email_cycle(
                profil.prenom, preparation["contrat"], contexte_client=preparation["contexte_client"],
            )
        else:
            from utils.brouillon_email_cycle import _prompt_lunaire
            preparation["prompt"] = _prompt_lunaire(
                preparation["contrat"]["theme_natal"], preparation["contrat"]["revolution_lunaire"],
            )[0]
        if not preparation.get("prompt"):
            raise ValueError("Le prompt de ce brouillon est absent. Prépare de nouveau les données.")
        # Dernière barrière avant tout appel, y compris pour les anciens essais.
        budget = verifier_budget_prompt(preparation["prompt"])
        identifiant = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%S") + "-" + uuid.uuid4().hex[:12]
        dossier = dossier_journaux_mail() / str(email.id) / identifiant
        dossier.mkdir(parents=True, exist_ok=False)

        def conserver(nom, valeur, *, afficher=True):
            texte = valeur if isinstance(valeur, str) else json.dumps(valeur, ensure_ascii=False, indent=2, default=str)
            (dossier / nom).write_text(texte, encoding="utf-8")
            if afficher:
                print(f"\n[MAIL ABONNÉ {email.id}] {nom}\n{texte}", flush=True)

        # Réglage propre aux mails : ne change pas le modèle des rapports RS.
        modele = MODEL
        parametres = {"model": modele, "messages": [{"role": "user", "content": preparation["prompt"]}],
                      "max_tokens": 6500, "stop_sequences": ["<FIN_MAIL>"]}
        if modele == "claude-sonnet-5-5":
            # Sonnet 5.5 refuse les paramètres de sampling historiques.
            # Sans outils, between_tools produit directement le texte du mail.
            parametres.update(thinking={"type": "between_tools"}, output_config={"effort": "medium"})
        mode = "essai_separe" if nouvel_essai else "premier_brouillon"
        conserver("requete.json", {
            **parametres, "relances_automatiques": 0, "mode_execution": mode,
            "mail_reference": email.id, "format_entree": budget["format_dossier"],
        }, afficher=False)
        essentiel = dossier_essentiel(preparation.get("contrat") or {}, preparation.get("contexte_client") or {})
        conserver("dossier_transmis.json", serialiser_dossier(essentiel), afficher=False)
        conserver("controle_entree.json", {**budget, "choix_journal_mails": preparation["choix_journal_mails"]})
        print(f"[MAIL ABONNÉ {email.id}] Paramètres : " + json.dumps(
            {k: v for k, v in parametres.items() if k != "messages"}, ensure_ascii=False), flush=True)
        conserver("prompt.txt", preparation["prompt"])
        if not nouvel_essai:
            email.declencheur_factuel = json.dumps(preparation, ensure_ascii=False, default=str)
            db.session.commit()
        controles = {"mode_execution": mode, "original_conserve": nouvel_essai,
                     "journal_actualise_pour_relecture": actualiser_journal,
                     "choix_journal_mails": preparation["choix_journal_mails"]}
        try:
            if lire_choix_journal_mails(profil.utilisateur_id) != preparation["choix_journal_mails"]:
                controles["raison_lisible"] = "Ton choix sur l'utilisation du journal a changé pendant la préparation. Aucun appel IA effectué. Prépare un nouveau brouillon avec ton choix actuel."
                raise ValueError(controles["raison_lisible"])
            reponse = creer_message_claude(client=CLIENT.with_options(max_retries=0, timeout=180.0), **parametres)
            brut = "".join(bloc.text for bloc in reponse.content if getattr(bloc, "type", None) == "text")
            conserver("reponse_brute.txt", brut)
            usage = {"modele": reponse.model, "tokens_entree": reponse.usage.input_tokens,
                     "tokens_sortie": reponse.usage.output_tokens,
                     "tokens_total": reponse.usage.input_tokens + reponse.usage.output_tokens,
                     "stop_reason": reponse.stop_reason}
            conserver("usage.json", usage)
            if reponse.stop_reason not in ("end_turn", "stop_sequence"):
                raise ValueError("La réponse est tronquée ou interrompue.")
            texte = brut.replace("<FIN_MAIL>", "").strip()
            if not texte:
                raise ValueError("La réponse est vide.")
            objet = next((l.split(":", 1)[1].strip()[:250] for l in texte.splitlines() if l.strip().startswith("OBJET :")), None)
            if not objet:
                raise ValueError("L’objet du mail manque dans la réponse.")
            domaines_externes = _domaines_externes_mail(texte)
            controles["domaines_externes"] = domaines_externes
            if domaines_externes:
                controles["raison"] = "lien_externe_interdit"
                raise ValueError("Le mail contient un lien vers un autre site.")
            html = convertir_email_texte_en_html(texte)
            conserver("brouillon.txt", texte)
            conserver("brouillon.html", html)
            if preparation.get("version_contrat") == VERSION_CONTRAT:
                structure = _controle_structure_quinzaine(texte)
                controles["structure_redactionnelle"] = structure
                if structure["erreurs"]:
                    controles["raison"] = "structure_redactionnelle_insuffisante"
                    controles["raison_lisible"] = " ".join(structure["erreurs"])
                    raise ValueError("La structure rédactionnelle demandée n'est pas respectée.")
            conserver("controles.json", {**controles, "statut": "brouillon_a_relire", "nombre_mots": len(texte.split()),
                       "objet_present": True, "reponse_complete": True, "envoi": False})
        except Exception as erreur:
            conserver("controles.json", {**controles, "statut": "echec", "type_erreur": type(erreur).__name__,
                       "relance": False, "envoi": False})
            detail = controles.get("raison_lisible") or (
                "Le mail contient un lien externe interdit." if controles.get("raison") == "lien_externe_interdit"
                else "La génération a échoué ou sa réponse est incomplète."
            )
            raise ValueError(f"{detail} Résultats conservés dans le journal {identifiant}. Aucun appel n’est relancé.") from None
        if nouvel_essai:
            print(f"[MAIL ABONNÉ {email.id}] Nouvel essai séparé : {dossier / 'brouillon.html'}. Brouillon original inchangé, aucun envoi.", flush=True)
            return {"email_id": email.id, "journal_execution": identifiant, "dossier": str(dossier)}
        email.objet, email.contenu_texte, email.contenu_html = objet, texte, html
        email.question_journal = next((l.strip()[:2000] for l in reversed(texte.splitlines()) if "?" in l), None)
        email.statut, email.date_generation = "brouillon", datetime.now(timezone.utc)
        preparation["usage_ia"], preparation["journal_execution"] = usage, identifiant
        email.declencheur_factuel = json.dumps(preparation, ensure_ascii=False, default=str)
        db.session.commit()
        return email

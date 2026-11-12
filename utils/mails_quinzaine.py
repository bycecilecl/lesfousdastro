"""Deux brouillons par mois civil, RS/RL/lunaisons/journal. Aucun envoi."""
from datetime import datetime, timedelta, timezone
from zoneinfo import ZoneInfo
import json
from pathlib import Path
import os

from extensions import db
from models.espace_personnel import CycleLunaire, CycleSolaire, EmailCycleAbonnement
from utils.brouillon_email_cycle import droits_email, _theme_natal, _lieu_cycles
from utils.cycles_abonnement import creer_cycle_solaire_pour_instant
from utils.revolution_lunaire import prochaine_revolution_lunaire, calculer_theme_revolution_lunaire, priorites_interpretation
from utils.lunaisons import calculer_lunaison, dernieres_lunaisons, completer_contacts_lunaison
from utils.email_cycle_abonnement import construire_contexte_email_cycle
from utils.contexte_journal_cycle import construire_contexte_client_cycle
from utils.enjeux_annuels import contexte_enjeux_annuels
from utils.lecture_lunaison import natal_pour_mail, maitrises_des_maisons, VERSION_CONTACTS_IMPORTANTS
from utils.configurations_astrologiques import analyser_configurations_majeures
from utils.dossier_mail_essentiel import dossier_essentiel, serialiser_dossier, verifier_budget_prompt
from utils.analyses_lunaisons import actualiser_analyses_lunaisons
from utils.confidentialite_journal_mails import filtrer_preparation_journal_mails
from utils.stockage_espace import racine_privee_espace


VERSION_CONTRAT = "quinzaine_v4_figures_maitrises"
HEURE_MAIL = 9
TITRES_MAIL_QUINZAINE = (
    "Le mouvement de la quinzaine",
    "Ce que ta Révolution Lunaire met en jeu",
    "Les rendez-vous lunaires",
    "Ton point d’appui",
)


def _utc(instant):
    return instant.replace(tzinfo=timezone.utc) if instant.tzinfo is None else instant.astimezone(timezone.utc)


def creneaux_mois(mois, tzid):
    try:
        premier = datetime.strptime(mois, "%Y-%m").replace(tzinfo=ZoneInfo(tzid), hour=HEURE_MAIL)
        if premier.strftime("%Y-%m") != mois:
            raise ValueError()
    except (ValueError, TypeError) as erreur:
        raise ValueError("Choisis un mois au format AAAA-MM.") from erreur
    suivant = premier.replace(year=premier.year + 1, month=1) if premier.month == 12 else premier.replace(month=premier.month + 1)
    milieu = premier.replace(day=15)
    return [(premier, milieu), (milieu, suivant)]


def _debut_rl_actif(longitude_natale, instant):
    # Cherche le retour précédent, jamais le prochain par simple commodité.
    curseur = instant - timedelta(days=35)
    precedent = None
    while True:
        retour = prochaine_revolution_lunaire(longitude_natale, apres=curseur)
        # La recherche est précise à la seconde ; la tolérance stabilise les
        # changements de cadre lorsqu'un retour est recalculé à une borne.
        if retour > instant + timedelta(seconds=2):
            if precedent is None:
                raise ValueError("Impossible de déterminer la RL active.")
            return precedent, retour
        precedent = retour
        curseur = retour + timedelta(seconds=1)


def _cadres_periode(profil, natal, lieu, debut, fin):
    cadres = []
    curseur = debut
    while curseur < fin:
        rs = creer_cycle_solaire_pour_instant(profil, curseur)
        contenu = json.loads(rs.theme_technique)
        donnees_rs = contenu["donnees"]
        theme_rs = contenu["theme_revolution_solaire"]
        donnees_rs["periode"] = {"debut": _utc(rs.debut_cycle_utc).isoformat(), "fin": _utc(rs.fin_cycle_utc).isoformat()}
        debut_rl, fin_rl = _debut_rl_actif(natal["planetes"]["Lune"]["longitude"], curseur)
        rl = calculer_theme_revolution_lunaire(
            natal["planetes"]["Lune"]["longitude"], lieu["lat"], lieu["lon"],
            apres=debut_rl - timedelta(seconds=2), theme_natal=natal,
            theme_revolution_solaire=theme_rs, tzid=lieu["tzid"],
        )
        rl["priorites"] = priorites_interpretation(rl)
        cle_rl = debut_rl.strftime("%Y-%m-%d")
        cycle_rl = CycleLunaire.query.filter_by(profil_id=profil.id, cle_cycle=cle_rl).first()
        if cycle_rl is None:
            # La liaison historique d'une RL correspond à sa date de début.
            rs_au_debut_rl = creer_cycle_solaire_pour_instant(profil, debut_rl)
            rl_stockage = rl
            if rs_au_debut_rl.id != rs.id:
                rl_stockage = calculer_theme_revolution_lunaire(
                    natal["planetes"]["Lune"]["longitude"], lieu["lat"], lieu["lon"],
                    apres=debut_rl - timedelta(seconds=2), theme_natal=natal,
                    theme_revolution_solaire=json.loads(rs_au_debut_rl.theme_technique)["theme_revolution_solaire"],
                    tzid=lieu["tzid"],
                )
                rl_stockage["priorites"] = priorites_interpretation(rl_stockage)
            cycle_rl = CycleLunaire(
                profil_id=profil.id, cle_cycle=cle_rl, cycle_solaire_id=rs_au_debut_rl.id,
                debut_cycle_utc=debut_rl, fin_cycle_utc=fin_rl,
                ville=lieu["ville"], fuseau_horaire=lieu["tzid"],
                latitude=lieu["lat"], longitude=lieu["lon"],
                theme_technique=json.dumps(rl_stockage, ensure_ascii=False, default=str), statut="technique",
            )
            db.session.add(cycle_rl)
            db.session.flush()
        borne = min(fin, fin_rl, _utc(rs.fin_cycle_utc))
        if borne <= curseur:
            raise ValueError("Les bornes des cycles RS/RL ne permettent pas de préparer cette période.")
        cadres.append({"debut": curseur, "fin": borne, "rs": rs, "donnees_rs": donnees_rs,
                       "theme_rs": theme_rs, "rl": rl, "cycle_rl": cycle_rl})
        curseur = borne
    return cadres


def _historique(profil_id, debut):
    from sqlalchemy import or_, and_
    emails = EmailCycleAbonnement.query.filter(
        EmailCycleAbonnement.profil_id == profil_id,
        or_(EmailCycleAbonnement.contenu_texte.isnot(None), EmailCycleAbonnement.contenu_html.isnot(None)),
        or_(EmailCycleAbonnement.date_prevue < debut,
            and_(EmailCycleAbonnement.date_prevue.is_(None), EmailCycleAbonnement.date_generation < debut)),
    ).order_by(EmailCycleAbonnement.date_generation.desc()).limit(4).all()
    return [{"id": e.id, "statut": e.statut, "objet": e.objet,
             "texte_recent": (e.contenu_texte or "")[:2500], "question_journal": e.question_journal} for e in emails]


def _rl_precedente(profil_id, debut_rl):
    """Dernière RL terminée et déjà enregistrée ; aucun calcul supplémentaire."""
    cycle = CycleLunaire.query.filter(
        CycleLunaire.profil_id == profil_id,
        CycleLunaire.debut_cycle_utc < debut_rl - timedelta(seconds=2),
        CycleLunaire.fin_cycle_utc <= debut_rl + timedelta(seconds=2),
    ).order_by(CycleLunaire.debut_cycle_utc.desc()).first()
    if cycle is None:
        return None
    theme = json.loads(cycle.theme_technique)
    return {
        "cycle_lunaire_id": cycle.id,
        "debut_utc": _utc(cycle.debut_cycle_utc).isoformat(),
        "fin_utc": _utc(cycle.fin_cycle_utc).isoformat(),
        "usage": "historique astrologique, aucun vécu déduit de la carte",
        "theme": {cle: theme.get(cle) for cle in (
            "instant_local", "planetes", "angles_deg", "maisons",
            "aspects_revolution", "aspects_avec_natal", "priorites",
        )},
    }


def construire_prompt_quinzaine(prenom, contrat, contexte_client):
    dossier = dossier_essentiel(contrat, contexte_client)
    prompt = f"""Rédige le mail astrologique de {prenom} pour la quinzaine indiquée.
Commence par OBJET : ..., puis utilise ces quatre
intertitres dans cet ordre : {" ; ".join(TITRES_MAIL_QUINZAINE)}.

Tutoie, en français vivant, précis et accessible, humoristique, pète-sec et
mordant. L'humour vise les situations, jamais les confidences. 
Aucun jargon accumulé, ton thérapeutique, fausse erreur de date ou commentaire de méthode.

Tu t'adresses à un client qui veut comprendre ses énergies du mois, pas à quelqu'un qui maîtrise l'astrologie.

⚠️ Ce n'est pas un mail de références techniques, utilise le uniquement pour développer l'analyse ! 

PROFONDEUR ATTENDUE
Fais ressortir les enjeux de l'analyse de la RL et des lunaisons concernées.
Ne choisis pas à l'avance un thème éditorial pour le premier ou le deuxième mail.
Pour chaque enjeu, relie les facteurs actuels à la structure natale.
Explique ce qui peut se jouer concrètement : besoins,
aspirations, contradictions, choix et ressources. 
Développe, on ne veut pas un mail de détails techniques.

Le mouvement de la quinzaine présente brièvement le fil qui ressort de la RL
et des lunaisons. La section
« Ce que ta Révolution Lunaire met en jeu » est centrale : développe-la
en au moins trois paragraphes reliés, avant les lunaisons et les transits.
Développe d'abord la RL à partir de sa carte seule, puis relie cette lecture
au thème natal et, si elle apporte un éclairage utile, à la RS.
Ne tiens compte ni du profil ni du journal dans
ce développement : il doit rester complet et compréhensible sans ces informations.

Hiérarchise ce qui organise le cycle : les dominantes, les domaines reliés
par leurs maîtres, les tensions et les soutiens. Explique comment ces éléments
fonctionnent ensemble : pourquoi un sujet prend de la place, quelles aspirations
se confrontent et quelles ressources permettent de composer avec cette tension.
Développe son enjeu principal : pourquoi il compte pour cette personne,
les tensions possibles, les façons de les vivre et les ressources disponibles.
N'ajoute pas de facteurs secondaires tant que cela n'est pas expliqué.
Les rendez-vous lunaires développent les lunaisons comme des analyses à part
entière, puis expliquent leur rencontre avec le contexte de la RL lorsque
les données le permettent.
Lorsqu'une analyse validée de Cécile accompagne une lunaison dans les données,
prends sa lecture comme base éditoriale de cette lunaison, puis personnalise-la
à partir des maisons et contacts calculés du client, du natal et de la RL active.
Garde ses enjeux et ses nuances sans recopier son texte ni lui ajouter un
catalogue technique. Ses exemples collectifs ne sont pas des faits vécus par
le client : ne les lui attribue pas. Les contacts et maisons personnels restent
ceux des données calculées. N'utilise pas cette lecture collective pour orienter
le développement initial de la RL. En son absence, conserve la lecture des
lunaisons à partir des seules données astrologiques fournies.
Ton point d'appui rassemble les ressources, puis accueille le passage
de rapprochement avec le profil et le journal, avant la question finale.

LECTURE ASTROLOGIQUE

La RL et les lunaisons sont le cœur du mail. Le natal précise ce qu'elles
mobilisent chez la personne : ce qui se joue, les tensions, les choix possibles
et les ressources.

Ne représente pas la RS à chaque mail. Mobilise seulement les éléments annuels
qui éclairent directement les enjeux de la quinzaine, sans répéter une
introduction annuelle. Si la RS n'apporte rien de pertinent, ne la mentionne pas.

Pour les points activés, utilise les signes, maisons, aspects et
maîtrises utiles à cette compréhension. Distingue la maison où se
trouve une planète des maisons qu’elle gouverne. Explique les figures
importantes et les répétitions entre les cartes, sans faire un catalogue.

Pour chaque lunaison de la quinzaine, donne sa date locale.

Pour chaque lunaison, construis une analyse personnelle développée à partir de la lecture collective validée de Cécile et des données calculées du client.

Commence par formuler ce que cette lunaison met personnellement en jeu. Explique les besoins des maisons natales activées et leur articulation : ce que la personne cherche à préserver, à développer ou à faire coexister.

Approfondis cette lecture avec les contacts personnels les plus significatifs. Lorsqu’une planète natale est activée, explique ce que sa position, ses aspects et ses maîtrises apportent à la compréhension. Montre pourquoi cette activation prend une coloration particulière chez cette personne.

Développe dans la section lunaire les contacts serrés des maîtres au natal. Si Mercure est maître et revient sur Mercure natal ou touche la Lune natale, explique ce que cela mobilise dans la pensée, le ressenti et l’expression des besoins.

Relie les facteurs qui parlent d’un même enjeu dans un développement cohérent. Ne consacre pas automatiquement un paragraphe à chaque planète ou aspect. Un contact supplémentaire doit approfondir, nuancer ou déplacer l’interprétation.

Développe les contradictions possibles, mais aussi les capacités et les soutiens. Explique comment une même configuration peut trouver plusieurs expressions, sans présupposer un conflit, une difficulté ou un événement.

Commence les paragraphes par leur sens humain. Place les références techniques utiles dans de courtes mentions en italique Markdown (*…*), après l’interprétation. Une traduction de mots-clés ne constitue pas une analyse.

Les liens avec la RL active et la RS pertinente doivent éclairer l’enjeu déjà développé. Leur présence ne demande pas un inventaire supplémentaire.

Garde le profil et le journal pour le rapprochement final avec le vécu déclaré. L’analyse astrologique doit rester complète sans ces informations.

Pour une Nouvelle Lune, explique ce qui cherche à émerger, ses conditions
et ses tensions.

Pour les signes ayant deux maîtres dans les données fournies, utilise
le maître moderne comme maître principal et le maître traditionnel
en complément : Pluton pour le Scorpion, Uranus pour le Verseau,
Neptune pour les Poissons.

Pour les maisons importantes de la RL, développe le lien entre leur
domaine, la maison occupée par leur maître et ses aspects. Lorsque les
deux maîtres sont fournis, explique leurs contributions respectives.

Pour la Pleine Lune, développe les deux pôles et leur articulation.
Explique les besoins de chaque pôle, leur difficulté à coexister et le rôle
d'une éventuelle planète focale.
Pars des maisons natales activées, puis explique ce que les maisons
touchées dans la RS et la RL apportent à cette lecture.

Pour la RL comme pour les lunaisons, réponds à des questions humaines :
qu'est-ce qui se joue, pourquoi ces dimensions sont-elles liées, où est
la contradiction et quelles possibilités et ressources apparaissent ?

Lorsqu'un T-carré est présent, explique la tension entre les deux
pôles et le rôle de la planète focale. Évite une succession d'aspects
simplement énumérés.

Respecte les dates et l’origine des données : natal, RS, RL ou transits.
Appuie-toi uniquement sur les faits fournis. N’invente aucun contact,
événement ni calendrier d’intensification.
Un orbe non nul n’est pas un contact exact : dis « très serré » si pertinent. N’ajoute aucun délai pratique non fourni, même pour conseiller une pause.

PROFIL, JOURNAL ET CONTINUITÉ
Le profil et les notes des 30 jours précédents donnent le vécu déclaré.
Les périodes anciennes recoupant cette fenêtre restent prises en compte.
Un champ absent ne permet aucune supposition. Ne transforme pas les faits
connus du journal en découvertes astrologiques, et ne copie pas les expressions
intimes. Ne décris pas les pensées d'une autre personne.
Les enjeux annuels retenus sont des interprétations sélectionnées, pas du vécu.
S'ils sont absents, appuie-toi sur les faits RS sans inventer.

Un bilan requiert des notes datées qui montrent une évolution. Sinon propose
une observation ouverte. L'historique des mails sert à limiter les répétitions ;
un brouillon n'est pas un mail envoyé. 

Réserve le profil et les notes du journal à un passage en fin de « Ton point d'appui », avant la question finale, si ce contexte est disponible.
Ne les utilise ni pour choisir les enjeux astrologiques ni pour orienter les trois premières sections. Le vécu vient éclairer la lecture déjà développée ; il ne la remplace pas. Retiens un ou deux éléments utiles, sans résumer le journal ni réécrire la RL autour de ces confidences.

CONTRÔLE FINAL AVANT DE LIVRER LE MAIL

Relis et corrige ton texte avant de rendre la version finale.

Chaque paragraphe doit développer une idée compréhensible : PAS UN INVENTAIRE TECHNIQUE.
Si tel est le cas, réécris le. 

Commence par l'interprétation. Les références astrologiques utiles viennent
en appui. Le lecteur doit pouvoir comprendre toute l'analyse en sautant ces mentions. 
Supprime les références qui n'apportent rien au développement.

Dans le bilan final, ne résume pas les notes du journal. Rapproche un élément
du vécu déclaré d'un enjeu déjà développé et explique ce que ce rapprochement
permet de comprendre, de nuancer ou de laisser ouvert. Ne répète pas simplement
à la personne ce qu'elle a écrit.
Évite l’introduction « Tu as écrit que… » ; développe directement ce que ce vécu éclaire ou nuance.

Rends uniquement le mail final, sans compte rendu de cette vérification ni autocorrection visible.

Termine par UNE question liée à l'enjeu central, ouverte sur le vécu ou le
ressenti, sans imposer une négociation ou un exercice de coaching. Puis écris
<FIN_MAIL> seul sur sa ligne.

FAITS ESSENTIELS ET CONTEXTE DÉCLARÉ
{serialiser_dossier(dossier)}
"""
    verifier_budget_prompt(prompt)
    return prompt


def _actualiser_contacts_lunaisons(contrat):
    """Complète les anciens dossiers avec leurs cartes enregistrées, sans IA.

    Ne régénère ni RS ni RL et ne change pas les instants des lunaisons.
    Les dossiers déjà enrichis évitent tout nouveau calcul.
    """
    cartes = {}
    debut_mail = _utc(datetime.fromisoformat(contrat["periode_mail"]["debut_utc"]))
    for lunaison in contrat.get("lunaisons_dans_la_periode", []):
        instant = _utc(datetime.fromisoformat(lunaison["instant_utc"]))
        cadre = next((c for c in contrat.get("cadres_rs_rl", [])
                      if _utc(datetime.fromisoformat(c["valable_du_utc"])) <= instant
                      < _utc(datetime.fromisoformat(c["valable_au_exclu_utc"]))), None)
        if cadre is None:
            raise ValueError("Le cadre RS/RL de cette lunaison manque. Prépare de nouveau les données avant de générer le mail. Aucun appel IA effectué.")
        rl = cadre.get("revolution_lunaire") or {}
        debut_rl = rl.get("debut_utc") or rl.get("instant_local")
        rl_future = (rl.get("usage_editorial") == "date_a_annoncer_sans_interpretation_anticipee"
                     or bool(debut_rl and _utc(datetime.fromisoformat(debut_rl)) > debut_mail + timedelta(seconds=2)))
        lunaison["usage_rl"] = "annoncer_uniquement_la_date" if rl_future else "active_a_la_date_du_mail"
        lecture = lunaison.get("lecture_personnalisee") or {}
        if lecture.get("version_contacts_importants") == VERSION_CONTACTS_IMPORTANTS:
            continue

        def lire_carte(modele, identifiant, nature):
            cle = (nature, identifiant)
            if cle not in cartes:
                cycle = db.session.get(modele, identifiant) if identifiant else None
                if cycle is None:
                    raise ValueError("Une carte enregistrée nécessaire aux contacts de lunaison est absente. Prépare de nouveau les données. Aucun appel IA effectué.")
                contenu = json.loads(cycle.theme_technique)
                cartes[cle] = contenu["theme_revolution_solaire"] if nature == "RS" else contenu
            return cartes[cle]

        theme_rs = lire_carte(CycleSolaire, cadre.get("cycle_solaire_id"), "RS")
        theme_rl = None if rl_future else lire_carte(CycleLunaire, cadre.get("cycle_lunaire_id"), "RL")
        completer_contacts_lunaison(lunaison, theme_natal=contrat["theme_natal"],
                                   theme_rs=theme_rs, theme_rl=theme_rl)
        print(f"[MAIL ABONNÉ] Contacts des planètes importantes complétés pour {lunaison['type']} du {lunaison['instant_local']}, avec les cartes enregistrées. Aucun appel IA à cette étape.", flush=True)


def preparer_essai_quinzaine(profil, preparation, *, actualiser_journal=False, instant=None):
    """Prépare la comparaison, sans nouvelle carte RS/RL ni appel IA."""
    from copy import deepcopy
    copie = deepcopy(preparation)
    _actualiser_contacts_lunaisons(copie["contrat"])
    actualiser_analyses_lunaisons(copie["contrat"])
    if actualiser_journal:
        debut = datetime.fromisoformat(copie["contrat"]["periode_mail"]["debut_utc"])
        connu_avant = _utc(instant or datetime.now(timezone.utc))
        copie["contexte_client"] = construire_contexte_client_cycle(
            profil, min(debut, connu_avant), jours_regardes=30, limite_entrees=None,
            historique_strict=True, connu_avant_utc=connu_avant,
        )
    copie = filtrer_preparation_journal_mails(profil, copie)
    copie["prompt"] = construire_prompt_quinzaine(
        profil.prenom, copie["contrat"], copie.get("contexte_client", {}),
    )
    return copie


def actualiser_mail_quinzaine(profil, preparation):
    """Actualise journal, enjeux retenus et historique avant le premier appel IA."""
    from copy import deepcopy
    copie = deepcopy(preparation)
    _actualiser_contacts_lunaisons(copie["contrat"])
    actualiser_analyses_lunaisons(copie["contrat"])
    debut = datetime.fromisoformat(copie["contrat"]["periode_mail"]["debut_utc"])
    instant_contexte = min(debut, datetime.now(timezone.utc))
    copie["contexte_client"] = construire_contexte_client_cycle(
        profil, instant_contexte, jours_regardes=30, limite_entrees=None,
        historique_strict=True,
    )
    copie["contexte_client"]["connu_avant_utc"] = instant_contexte.isoformat()
    for cadre in copie["contrat"]["cadres_rs_rl"]:
        cadre["enjeux_annuels"] = contexte_enjeux_annuels(profil, datetime.fromisoformat(cadre["valable_du_utc"]))
    copie["contrat"]["mails_precedents"] = (
        _historique(profil.id, debut) if copie["contexte_client"].get("journal_autorise") else []
    )
    copie = filtrer_preparation_journal_mails(profil, copie)
    copie["prompt"] = construire_prompt_quinzaine(profil.prenom, copie["contrat"], copie["contexte_client"])
    return copie


def preparer_mails_mois(profil, mois, *, jour=None):
    """Sérialise la préparation pour un profil/mois, transaction comprise."""
    from flask import current_app
    creneaux_mois(mois, profil.fuseau_cycles or "Europe/Paris")
    if jour not in (None, 1, 15):
        raise ValueError("Choisis le créneau du 1er ou du 15.")
    dossier = racine_privee_espace() / "mails_prepares"
    dossier.mkdir(parents=True, exist_ok=True)
    verrou = dossier / f"profil-{profil.id}-{mois}.lock"
    try:
        fd = os.open(verrou, os.O_CREAT | os.O_EXCL | os.O_WRONLY, 0o600)
    except FileExistsError:
        raise ValueError("La préparation de ces deux créneaux est déjà en cours.")
    try:
        os.close(fd)
        resultat = _preparer_mails_mois(profil, mois, jour=jour)
        db.session.commit()
        return resultat
    except Exception:
        db.session.rollback()
        raise
    finally:
        verrou.unlink(missing_ok=True)


def _preparer_mails_mois(profil, mois, *, jour=None):
    """Prépare les deux créneaux civils sans génération IA ni envoi."""
    droits = droits_email(profil)
    if not droits.get("revolution_solaire") or droits.get("emails_par_mois") != 2:
        raise ValueError("Cette préparation nécessite la formule Accompagnement astral.")
    natal, lieu = _theme_natal(profil), _lieu_cycles(profil)
    fuseau = ZoneInfo(lieu["tzid"])
    resultat = []
    from routes.espace_personnel import _calculer_photo_transits
    for debut_local, fin_locale in creneaux_mois(mois, lieu["tzid"]):
        if jour is not None and debut_local.day != jour:
            continue
        cle = debut_local.date().isoformat()
        email = EmailCycleAbonnement.query.filter_by(profil_id=profil.id, cle_creneau=cle).first()
        if email and (email.contenu_texte or email.contenu_html):
            resultat.append(email)
            continue
        debut, fin = debut_local.astimezone(timezone.utc), fin_locale.astimezone(timezone.utc)
        cadres = _cadres_periode(profil, natal, lieu, debut, fin)
        lunaisons = []
        for nature in ("nouvelle_lune", "pleine_lune"):
            curseur = debut - timedelta(seconds=2)
            while True:
                lunaison = calculer_lunaison(nature, apres=curseur, theme_natal=natal, tzid=lieu["tzid"])
                instant_lunaison = datetime.fromisoformat(lunaison["instant_utc"])
                if instant_lunaison >= fin:
                    break
                if instant_lunaison >= debut:
                    cadre = next(c for c in cadres if c["debut"] <= instant_lunaison < c["fin"])
                    lunaisons.append(calculer_lunaison(
                        nature, apres=curseur, theme_natal=natal,
                        theme_rs=cadre["theme_rs"], theme_rl=cadre["rl"], tzid=lieu["tzid"],
                    ))
                curseur = instant_lunaison + timedelta(seconds=2)
        contrat = {
            "periode_mail": {"debut_utc": debut.isoformat(), "fin_exclue_utc": fin.isoformat(),
                             "debut_local": debut_local.isoformat(), "fin_exclue_locale": fin_locale.isoformat()},
            "theme_natal": natal_pour_mail(natal),
            "profil_calendrier": {
                "anniversaire_mois_jour": profil.date_naissance.strftime("%m-%d"),
                "fuseau_horaire": lieu["tzid"],
            },
            "rl_precedente_de_reference": _rl_precedente(
                profil.id, _utc(datetime.fromisoformat(cadres[0]["rl"]["instant_utc"])),
            ),
            "cadres_rs_rl": [], "lunaisons_dans_la_periode": sorted(lunaisons, key=lambda l: l["instant_utc"]),
            "lunaison_precedente_de_reference": dernieres_lunaisons(
                avant=debut, theme_natal=natal, tzid=lieu["tzid"], nombre=1,
            ),
        }
        for cadre in cadres:
            photo = _calculer_photo_transits(natal, cadre["debut"])
            contexte = construire_contexte_email_cycle(cadre["donnees_rs"], cadre["rl"], photo)
            contexte["revolution_solaire"]["donnees_techniques"] = {
                cle: cadre["donnees_rs"].get(cle) for cle in (
                    "placements_rs", "maisons_rs_occupees", "maisons_gouvernees_rs",
                    "maisons_gouvernees_natales", "aspects_internes_rs",
                    "aspects_rs_natal", "configurations_majeures_rs",
                )
            }
            contexte["revolution_lunaire"].update({
                "debut_utc": _utc(cadre["cycle_rl"].debut_cycle_utc).isoformat(),
                "fin_utc": _utc(cadre["cycle_rl"].fin_cycle_utc).isoformat(),
                "usage_editorial": (
                    "active_a_la_date_du_mail"
                    if _utc(cadre["cycle_rl"].debut_cycle_utc) <= debut + timedelta(seconds=2)
                    else "date_a_annoncer_sans_interpretation_anticipee"
                ),
                "aspects_internes_complets": cadre["rl"].get("aspects_revolution", []),
                "contacts_natals_complets": cadre["rl"].get("aspects_avec_natal", []),
                "angles_deg": cadre["rl"].get("angles_deg", {}),
                "maisons": cadre["rl"].get("maisons", {}),
                "maitrises_des_maisons": maitrises_des_maisons(cadre["rl"].get("maisons", {})),
                "figures": analyser_configurations_majeures(
                    cadre["rl"].get("aspects_revolution", []), cadre["rl"].get("planetes", {}),
                ),
            })
            contrat["cadres_rs_rl"].append({
                "valable_du_utc": cadre["debut"].isoformat(), "valable_au_exclu_utc": cadre["fin"].isoformat(),
                "cycle_solaire_id": cadre["rs"].id, "cycle_lunaire_id": cadre["cycle_rl"].id,
                **contexte,
            })
        preparation = actualiser_mail_quinzaine(profil, {
            "version_contrat": VERSION_CONTRAT, "portee": "complet", "contrat": contrat,
            "cycle_solaire_id": cadres[0]["rs"].id,
        })
        if email is None:
            email = EmailCycleAbonnement(
                profil_id=profil.id, cle_creneau=cle, cycle_lunaire_id=cadres[0]["cycle_rl"].id,
                type_email=f"boussole_quinzaine_{debut_local.day}", statut="prepare",
            )
            db.session.add(email)
        email.date_prevue, email.fin_periode = debut, fin
        email.declencheur_factuel = json.dumps(preparation, ensure_ascii=False, default=str)
        db.session.flush()
        from flask import current_app
        dossier = racine_privee_espace() / "mails_prepares" / str(profil.id) / cle
        dossier.mkdir(parents=True, exist_ok=True)
        (dossier / "preparation.json").write_text(email.declencheur_factuel, encoding="utf-8")
        (dossier / "prompt.txt").write_text(preparation["prompt"], encoding="utf-8")
        print(f"[MAIL ABONNÉ] Créneau {cle} ({fuseau}), {len(lunaisons)} lunaison(s), {len(cadres)} cadre(s) RS/RL. Aucun appel IA.", flush=True)
        print(preparation["prompt"], flush=True)
        resultat.append(email)
    return resultat


def lancer_mois(profil_id, mois, *, generer=False, jour=None, nouvel_essai=False, actualiser_journal=False):
    """Parcours terminal complet, sans pause ; aucune relance en cas d'échec."""
    from main import app
    from models.espace_personnel import ProfilAstral
    from utils.generation_mail_abonne import generer_mail_enregistre

    if nouvel_essai and (not generer or jour not in (1, 15)):
        raise ValueError("Un nouvel essai nécessite --generer et un seul --jour (1 ou 15).")
    if actualiser_journal and not nouvel_essai:
        raise ValueError("L'actualisation du journal pour comparaison nécessite --nouvel-essai.")
    with app.app_context():
        profil = db.session.get(ProfilAstral, profil_id)
        if profil is None:
            raise ValueError("Profil astral introuvable.")
        if nouvel_essai:
            creneaux_mois(mois, profil.fuseau_cycles or "Europe/Paris")
            cle = f"{mois}-{jour:02d}"
            email = EmailCycleAbonnement.query.filter_by(profil_id=profil.id, cle_creneau=cle).first()
            if email is None:
                raise ValueError("Aucun premier brouillon pour ce créneau. Lance d'abord sa génération normale.")
            contexte = "journal actualisé pour relecture" if actualiser_journal else "journal du brouillon conservé"
            print(f"[MAILS ABONNÉ] Nouvel essai du {cle}, données astrologiques conservées, {contexte}. Un seul appel Claude, aucun écrasement ni envoi.", flush=True)
            emails = [email]
        else:
            selection = f"du créneau du {jour}" if jour is not None else "des deux créneaux"
            print(f"[MAILS ABONNÉ] Préparation {selection} de {mois}, profil {profil_id}.", flush=True)
            emails = preparer_mails_mois(profil, mois, jour=jour)
            db.session.commit()
        for email in emails:
            print(f"[MAILS ABONNÉ] Créneau {email.cle_creneau}, fiche http://127.0.0.1:5050/mon-espace/emails-cycle/{email.id}", flush=True)
            if generer:
                generer_mail_enregistre(email, profil, nouvel_essai=nouvel_essai, actualiser_journal=actualiser_journal)
        print("[MAILS ABONNÉ] Parcours terminé. Aucun mail envoyé.", flush=True)

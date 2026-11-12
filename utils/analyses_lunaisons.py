"""Lectures éditoriales communes aux abonnés. Aucun appel IA ni envoi."""
from datetime import datetime, timedelta, timezone
from zoneinfo import ZoneInfo

from sqlalchemy import inspect

from extensions import db
from models.espace_personnel import AnalyseLunaison
from utils.lunaisons import prochain_instant_lunaison


TYPES_LUNAISONS = {"nouvelle_lune": "Nouvelle Lune", "pleine_lune": "Pleine Lune"}
FUSEAU_EDITION = ZoneInfo("Europe/Paris")
MESSAGE_MIGRATION = (
    "L'espace des analyses de lunaisons doit être initialisé. "
    "Lance env/bin/python3.12 script/migrate_analyses_lunaisons.py --apply "
    "depuis le dossier local, puis recharge la page. Aucun appel IA effectué."
)


def utc(instant):
    return instant.replace(tzinfo=timezone.utc) if instant.tzinfo is None else instant.astimezone(timezone.utc)


def verifier_table_analyses():
    moteur = db.session.get_bind(mapper=AnalyseLunaison)
    if not inspect(moteur).has_table(AnalyseLunaison.__tablename__):
        raise ValueError(MESSAGE_MIGRATION)


def lunaisons_du_mois(mois):
    """Calendrier calculé, en heure de Paris, sans dresser de thème client."""
    try:
        debut = datetime.strptime(mois, "%Y-%m").replace(tzinfo=FUSEAU_EDITION)
        if debut.strftime("%Y-%m") != mois or not 1900 <= debut.year <= 2200:
            raise ValueError()
    except (TypeError, ValueError) as erreur:
        raise ValueError("Choisis un mois entre janvier 1900 et décembre 2200.") from erreur
    fin = debut.replace(year=debut.year + 1, month=1) if debut.month == 12 else debut.replace(month=debut.month + 1)
    resultat = []
    for nature in TYPES_LUNAISONS:
        curseur = debut.astimezone(timezone.utc) - timedelta(seconds=2)
        while True:
            instant = prochain_instant_lunaison(nature, apres=curseur)
            if instant >= fin:
                break
            if instant >= debut:
                resultat.append(fiche_lunaison(nature, instant))
            curseur = instant + timedelta(seconds=2)
    return sorted(resultat, key=lambda fiche: fiche["instant"])


def fiche_lunaison(nature, instant):
    instant = utc(instant)
    return {"type": nature, "libelle": TYPES_LUNAISONS[nature], "instant": instant,
            "date_utc": instant.date().isoformat(), "date_locale": instant.astimezone(FUSEAU_EDITION)}


def retrouver_lunaison(nature, date_utc):
    """Vérifie la phase réelle pour éviter de rattacher un texte à une autre Lune."""
    try:
        jour = datetime.strptime(date_utc, "%Y-%m-%d").replace(tzinfo=timezone.utc)
        if nature not in TYPES_LUNAISONS or jour.date().isoformat() != date_utc or not 1900 <= jour.year <= 2200:
            raise ValueError()
        instant = prochain_instant_lunaison(nature, apres=jour - timedelta(seconds=2))
        if instant.date() != jour.date():
            raise ValueError()
    except (ValueError, TypeError) as erreur:
        raise ValueError("Cette date ne correspond pas à la lunaison demandée.") from erreur
    return fiche_lunaison(nature, instant)


def actualiser_analyses_lunaisons(contrat):
    """Remplace les anciennes références par les seules versions validées actuelles.

    Appelé avant préparation/premier appel et lors d'un nouvel essai explicite.
    Les brouillons de mails déjà produits ne sont jamais modifiés ici.
    """
    evenements = contrat.get("lunaisons_dans_la_periode", [])
    if not evenements:
        return
    verifier_table_analyses()
    dates = {utc(datetime.fromisoformat(l["instant_utc"])).date().isoformat() for l in evenements}
    lignes = AnalyseLunaison.query.filter(
        AnalyseLunaison.date_utc.in_(dates), AnalyseLunaison.validee_le.isnot(None),
        AnalyseLunaison.texte_valide.isnot(None),
    ).all()
    par_cle = {(a.type_lunaison, a.date_utc): a for a in lignes}
    for lunaison in evenements:
        lunaison.pop("analyse_cecile", None)
        instant = utc(datetime.fromisoformat(lunaison["instant_utc"]))
        analyse = par_cle.get((lunaison["type"], instant.date().isoformat()))
        if analyse is None or not analyse.texte_valide.strip():
            continue
        if abs((utc(analyse.instant_utc) - instant).total_seconds()) > 120:
            raise ValueError("La date de l'analyse validée ne correspond plus à la lunaison calculée. Vérifie sa fiche avant de générer le mail.")
        lunaison["analyse_cecile"] = {
            "id": analyse.id, "revision": analyse.revision_validee,
            "validee_le": utc(analyse.validee_le).isoformat(),
            "titre": analyse.titre_valide, "texte": analyse.texte_valide,
        }

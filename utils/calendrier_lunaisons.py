"""Relie les événements du calendrier aux lectures validées, sans génération."""
from datetime import datetime, timedelta, timezone

from flask import url_for
from sqlalchemy import func, inspect, select

from extensions import db
from models.espace_personnel import AnalyseLunaison


NATURES = {"nouvelle_lune", "pleine_lune"}
TOLERANCE = timedelta(seconds=120)


def _utc(instant):
    return instant.replace(tzinfo=timezone.utc) if instant.tzinfo is None else instant.astimezone(timezone.utc)


def relier_lectures_lunaisons(evenements):
    """N'expose que l'URL d'une lecture publiée de la même nature et du même instant."""
    cibles = []
    for evenement in evenements:
        evenement.pop("lecture_url", None)
        if evenement.get("nature") not in NATURES:
            continue
        try:
            instant = datetime.fromisoformat(evenement["date"])
            if instant.tzinfo is None:
                continue
            cibles.append((evenement, _utc(instant)))
        except (KeyError, TypeError, ValueError):
            continue
    if not cibles or not inspect(db.session.get_bind(mapper=AnalyseLunaison)).has_table(AnalyseLunaison.__tablename__):
        return
    dates = {instant.date().isoformat() for _, instant in cibles}
    lectures = db.session.execute(select(
        AnalyseLunaison.type_lunaison, AnalyseLunaison.date_utc, AnalyseLunaison.instant_utc,
    ).where(
        AnalyseLunaison.date_utc.in_(dates),
        AnalyseLunaison.type_lunaison.in_(NATURES),
        AnalyseLunaison.validee_le.isnot(None),
        AnalyseLunaison.texte_valide.isnot(None),
        func.trim(AnalyseLunaison.texte_valide) != "",
    )).all()
    for evenement, instant in cibles:
        for nature, date_utc, instant_lecture in lectures:
            if nature == evenement["nature"] and abs(_utc(instant_lecture) - instant) <= TOLERANCE:
                evenement["lecture_url"] = url_for("lunaisons.fiche", nature=nature, date_utc=date_utc)
                break

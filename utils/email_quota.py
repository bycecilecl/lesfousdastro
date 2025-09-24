# utils/email_quota.py
import os, json
from datetime import datetime
try:
    from zoneinfo import ZoneInfo  # Python 3.9+
except Exception:
    ZoneInfo = None

LIMIT_PER_EMAIL = int(os.getenv("FREE_ANALYSES_PER_EMAIL_PER_DAY", "3"))
QUOTA_PATH = os.getenv("EMAIL_QUOTA_PATH", "data/email_quota.json")

def _today_paris():
    now = datetime.now(ZoneInfo("Europe/Paris")) if ZoneInfo else datetime.utcnow()
    return now.strftime("%Y-%m-%d")

def _ensure_dir(path: str):
    d = os.path.dirname(path)
    if d and not os.path.exists(d):
        os.makedirs(d, exist_ok=True)

def check_and_log_email_quota(email: str):
    """Renvoie (allowed: bool, count_today: int). Incrémente si autorisé."""
    if not email:
        return True, 0
    _ensure_dir(QUOTA_PATH)
    data = {}
    if os.path.exists(QUOTA_PATH):
        try:
            with open(QUOTA_PATH, "r", encoding="utf-8") as f:
                data = json.load(f) or {}
        except Exception:
            data = {}

    today = _today_paris()
    day_map = data.get(today, {})
    count = int(day_map.get(email, 0))

    if count >= LIMIT_PER_EMAIL:
        return False, count  # quota atteint → on n’incrémente pas

    day_map[email] = count + 1
    data[today] = day_map

    # Garder le fichier léger (on conserve 3 derniers jours max)
    if len(data) > 5:
        keys = sorted(data.keys())[-3:]
        data = {k: data[k] for k in keys}

    with open(QUOTA_PATH, "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=2)

    return True, count + 1
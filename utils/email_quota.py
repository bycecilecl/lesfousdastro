# utils/email_quota.py
import os
import json
from datetime import datetime
from typing import Optional
try:
    from zoneinfo import ZoneInfo  # Python 3.9+
except Exception:
    ZoneInfo = None

# LIMITES (modifiable via env)
LIMIT_PER_EMAIL = int(os.getenv("FREE_ANALYSES_PER_EMAIL_PER_DAY", "3"))
LIMIT_PER_IP = int(os.getenv("FREE_ANALYSES_PER_IP_PER_DAY", "10"))

# Emplacement du petit fichier JSON (modifiable via env)
QUOTA_PATH = os.getenv("EMAIL_QUOTA_PATH", "data/email_quota.json")

def _today_paris():
    now = datetime.now(ZoneInfo("Europe/Paris")) if ZoneInfo else datetime.utcnow()
    return now.strftime("%Y-%m-%d")

def _ensure_dir(path: str):
    d = os.path.dirname(path)
    if d and not os.path.exists(d):
        os.makedirs(d, exist_ok=True)

def _load_data():
    if os.path.exists(QUOTA_PATH):
        try:
            with open(QUOTA_PATH, "r", encoding="utf-8") as f:
                return json.load(f) or {}
        except Exception:
            return {}
    return {}

def _save_data(data):
    _ensure_dir(QUOTA_PATH)
    with open(QUOTA_PATH, "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=2)

def check_and_log_email_quota(email: str, ip: Optional[str] = None):
    """
    Vérifie et incrémente les compteurs journaliers.
    Retourne (allowed: bool, info: dict)
    info contient : {'email_count': int, 'ip_count': int}
    - Si quota email atteint -> allowed=False
    - Si quota ip atteint -> allowed=False
    - Si Google/FS KO -> autorise par défaut (mais on écrit un warning)
    """
    if not email and not ip:
        return True, {"email_count": 0, "ip_count": 0}

    _ensure_dir(QUOTA_PATH)
    data = _load_data()

    today = _today_paris()
    day_map = data.get(today, {"emails": {}, "ips": {}})

    emails_map = day_map.get("emails", {})
    ips_map = day_map.get("ips", {})

    # compte actuels
    email_count = int(emails_map.get(email, 0)) if email else 0
    ip_count = int(ips_map.get(ip, 0)) if ip else 0

    # si quota atteint pour email ou ip -> on ne change rien et on bloque
    if email and email_count >= LIMIT_PER_EMAIL:
        return False, {"email_count": email_count, "ip_count": ip_count}
    if ip and ip_count >= LIMIT_PER_IP:
        return False, {"email_count": email_count, "ip_count": ip_count}

    # sinon on incrémente et on sauvegarde
    if email:
        emails_map[email] = email_count + 1
    if ip:
        ips_map[ip] = ip_count + 1

    day_map["emails"] = emails_map
    day_map["ips"] = ips_map
    data[today] = day_map

    # garder le JSON léger (garder 5 derniers jours max)
    if len(data) > 7:
        keys = sorted(data.keys())[-5:]
        data = {k: data[k] for k in keys}

    try:
        _save_data(data)
    except Exception as e:
        # si enregistrement impossible -> ne pas bloquer (fail-open)
        print(f"⚠️ [QUOTA] impossible d'enregistrer le quota: {e}")
        return True, {"email_count": email_count, "ip_count": ip_count}

    # renvoyer les compteurs après incrément
    return True, {"email_count": emails_map.get(email, email_count), "ip_count": ips_map.get(ip, ip_count)}
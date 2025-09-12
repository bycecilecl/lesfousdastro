# routes/downloads.py
from flask import Blueprint, redirect, abort
#from utils.s3_utils import presign_key

# ⚠️ Le nom du blueprint DOIT être "downloads" si tu utilises url_for("downloads.dl_point_astral", ...)
downloads_bp = Blueprint("downloads", __name__)  # pas d'url_prefix ici (ou adapte plus bas)

@downloads_bp.route("/dl/point_astral/<int:yyyy>/<int:mm>/<int:dd>/<uuid_hex>.pdf")
def dl_point_astral(yyyy: int, mm: int, dd: int, uuid_hex: str):
    key = f"point_astral/{yyyy:04d}/{mm:02d}/{dd:02d}/{uuid_hex}.pdf"
    try:
        url = presign_key(key)  # renvoie l'URL S3 présignée
    except Exception:
        return abort(404)
    return redirect(url, code=302)
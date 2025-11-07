import os
from datetime import datetime
from flask import Blueprint, render_template, current_app, url_for

site_bp = Blueprint("site_bp", __name__)

@site_bp.route("/temoignages")
def temoignages():
    folder = os.path.join(current_app.static_folder, "temoignages")
    allowed = (".png", ".jpg", ".jpeg", ".webp")
    items = []

    if os.path.isdir(folder):
        for fname in os.listdir(folder):
            if fname.lower().endswith(allowed):
                fpath = os.path.join(folder, fname)
                try:
                    mtime = os.path.getmtime(fpath)
                except OSError:
                    mtime = 0
                base = os.path.splitext(fname)[0]
                caption = base.replace("_", " ").replace("-", " ").strip()
                items.append({
                    "src": url_for("static", filename=f"temoignages/{fname}"),
                    "caption": caption,
                    "ts": mtime,
                    "date": datetime.fromtimestamp(mtime).strftime("%d/%m/%Y"),
                })

    items.sort(key=lambda x: x["ts"], reverse=True)
    print("=== Témoignages trouvés ===")
    print(items)
    return render_template("temoignages.html", items=items)
# utils/s3_utils.py
import os, uuid, mimetypes, boto3
from datetime import datetime, timezone

_S3_BUCKET  = os.getenv("S3_BUCKET_NAME")
_REGION     = os.getenv("AWS_DEFAULT_REGION", "eu-west-3")
_EXPIRES    = int(os.getenv("S3_PRESIGN_EXPIRES", "604800"))  # 7 jours

# ✅ s'assure qu'on a bien un client initialisé
_s3 = boto3.client("s3", region_name=_REGION)

def upload_file_and_presign(local_path: str,
                            key_prefix: str = "point_astral",
                            content_type: str | None = None,
                            expires_in: int | None = None):
    """Upload le fichier dans S3 puis renvoie une URL présignée."""
    if not _S3_BUCKET:
        raise RuntimeError("S3_BUCKET_NAME manquant dans l'environnement")
    if not os.path.exists(local_path):
        raise FileNotFoundError(f"Fichier introuvable: {local_path}")

    try:
        # Clef S3
        today = datetime.now(timezone.utc)
        ext = os.path.splitext(local_path)[1].lower() or ".pdf"
        key = f"{key_prefix.strip('/')}/{today:%Y/%m/%d}/{uuid.uuid4().hex}{ext}"

        # Content-type
        if not content_type:
            guessed, _ = mimetypes.guess_type(local_path)
            content_type = guessed or "application/octet-stream"

        # Upload (private + SSE)
        extra = {
            "ContentType": content_type,
            "ServerSideEncryption": "AES256",
            # "ACL": "private"  # inutile par défaut si le bucket force privé
        }

        print(f"📤 Upload vers s3://{_S3_BUCKET}/{key}")
        _s3.upload_file(local_path, _S3_BUCKET, key, ExtraArgs=extra)

        # 🔖 Nom sympa pour le téléchargement
        base_name = os.path.basename(local_path)
        disposition = f'inline; filename="{base_name}"'

        # URL présignée (avec hints navigateurs)
        url = _s3.generate_presigned_url(
            ClientMethod="get_object",
            Params={
                "Bucket": _S3_BUCKET,
                "Key": key,
                "ResponseContentType": content_type,
                "ResponseContentDisposition": disposition
            },
            ExpiresIn=expires_in or _EXPIRES,
        )

        # ✅ on retourne à la fois 'presigned_url' ET 'url'
        out = {
            "bucket": _S3_BUCKET,
            "key": key,
            "presigned_url": url,
            "url": url
        }
        print(f"✅ URL présignée OK (expire dans {expires_in or _EXPIRES}s)")
        return out

    except Exception as e:
        print(f"❌ Erreur S3: {type(e).__name__}: {str(e)}")
        # utile quand ça plante dans les lambdas dockerisées
        # import traceback; print(traceback.format_exc())
        raise

    # Alias pour compatibilité
presign_key = upload_file_and_presign
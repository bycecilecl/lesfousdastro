"""Stockage temporaire privé des rapports clients avant leur envoi sur S3."""
from __future__ import annotations

import os
from pathlib import Path
from uuid import uuid4

from flask import current_app

from utils.s3_utils import upload_file_and_presign


def private_pdf_path() -> str:
    """Return a non-public, random path for one client report."""
    directory = Path(current_app.instance_path) / "generated_pdfs"
    directory.mkdir(parents=True, exist_ok=True)
    return str(directory / f"{uuid4().hex}.pdf")


def upload_client_pdf(pdf_path: str, *, key_prefix: str, download_filename: str) -> str:
    """Upload a private report and always remove its local temporary copy."""
    try:
        result = upload_file_and_presign(
            pdf_path,
            key_prefix=key_prefix,
            content_type="application/pdf",
            download_filename=download_filename,
        )
        url = result.get("url") or result.get("presigned_url")
        if not url:
            raise RuntimeError("URL S3 présignée manquante")
        return url
    finally:
        try:
            os.remove(pdf_path)
        except FileNotFoundError:
            pass

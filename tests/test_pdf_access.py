import importlib.util
from pathlib import Path
from unittest.mock import Mock
import sys
from types import SimpleNamespace
from flask import Flask

ROOT = Path(__file__).resolve().parents[1]

def load(name, path):
    spec = importlib.util.spec_from_file_location(name, ROOT / path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def test_public_examples_only(tmp_path):
    mod = load('pdf_access_test', 'services/pdf_access.py')
    folder = tmp_path / 'static' / 'pdfs'
    folder.mkdir(parents=True)
    (folder / 'Exemple_Forces_Defis.pdf').write_bytes(b'example')
    (folder / 'client.pdf').write_bytes(b'private')
    app = Flask(__name__, static_folder=str(folder.parent))
    mod.install_pdf_access(app)
    app.add_url_rule('/old/<nom_fichier>', endpoint='amour_blocs.telecharger_amour_pdf', view_func=lambda nom_fichier: 'private')
    client = app.test_client()
    assert client.get('/static/pdfs/Exemple_Forces_Defis.pdf').status_code == 200
    assert client.get('/static/pdfs/client.pdf').status_code == 404
    assert client.get('/old/client').status_code == 404


def test_private_storage_and_failed_upload_recovery(tmp_path, monkeypatch):
    uploader = Mock()
    monkeypatch.setitem(sys.modules, 'utils.s3_utils', SimpleNamespace(upload_file_and_presign=uploader))
    mod = load('client_pdf_storage_test', 'utils/client_pdf_storage.py')
    app = Flask(__name__, instance_path=str(tmp_path / 'private'))
    with app.app_context():
        path = Path(mod.private_pdf_path())
        assert path.parent == tmp_path / 'private' / 'generated_pdfs'
        assert path != Path(mod.private_pdf_path())
        path.write_bytes(b'pdf')
        uploader.side_effect = RuntimeError('S3 unavailable')
        import pytest
        with pytest.raises(RuntimeError):
            mod.upload_client_pdf(str(path), key_prefix='test', download_filename='client.pdf')
        assert path.exists()
        uploader.side_effect = None
        uploader.return_value = {'url': 'https://example.invalid/signed'}
        assert mod.upload_client_pdf(str(path), key_prefix='test', download_filename='client.pdf').endswith('/signed')
        assert not path.exists()

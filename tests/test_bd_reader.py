"""BD images remain public only when published; comments need approval."""

import base64
import importlib.util
import os
import sys
import types
import unittest
from pathlib import Path
from unittest.mock import patch

from flask import Flask, url_for as flask_url_for

from extensions import db
from models.bd_comments import BdComment
_blog_path = Path(__file__).resolve().parents[1] / "routes" / "blog.py"
_spec = importlib.util.spec_from_file_location("bd_blog_under_test", _blog_path)
blog_module = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(blog_module)


class BdReaderTest(unittest.TestCase):
    def setUp(self):
        self.app = Flask(__name__, template_folder="../templates", static_folder="../static")
        self.app.secret_key = "test-only-secret"
        self.app.config.update(SQLALCHEMY_DATABASE_URI="sqlite:///:memory:", TESTING=True)
        db.init_app(self.app)
        self.app.register_blueprint(blog_module.blog_bp)
        self.app.jinja_env.globals["url_for"] = lambda endpoint, **kw: (
            flask_url_for(endpoint, **kw) if endpoint == "static" or endpoint.startswith("blog.") else "#"
        )
        self.app.context_processor(lambda: {"blog_preview": False})
        self.image = b"RIFF" + b"\x00" * 8 + b"WEBP" + b"test-image"
        encoded = base64.b64encode(self.image).decode()
        self.page = {
            "type": "published", "category": "bd", "slug": "soleil-saturne",
            "title": "Soleil conjoint Saturne", "tags": "aspects",
            "content": f'<p><img src="data:image/webp;base64,{encoded}" alt="Planche 1"></p>',
        }
        self.env = patch.dict(os.environ, {"DATABASE_URL": "sqlite:///:memory:",
                                        "EMAIL_ADMIN": "admin@example.test"})
        self.env.start()
        self.pages = patch.object(blog_module, "published_pages", return_value=[self.page])
        self.pages.start()
        with self.app.app_context():
            db.create_all()
        self.client = self.app.test_client()

    def tearDown(self):
        self.pages.stop()
        self.env.stop()
        with self.app.app_context():
            db.session.remove()
            db.drop_all()

    def test_old_article_urls_redirect_to_matching_blog_articles(self):
        destinations = {
            "etude-de-revolution-solaire-de-2020-2021": "revolution-solaire-2020-2021-etude-cas",
            "introduction-a-lastrologie-uranienne": "astrologie-uranienne-introduction",
            "la-lune-la-mere-en-astrologie": "la-lune-la-mere-en-astrologie",
            "les-transneptuniennes-astrologie-uranienne": "planetes-astrologie-uranienne",
        }
        for old, new in destinations.items():
            with self.subTest(old=old):
                response = self.client.get(f"/{old}/")
                self.assertEqual(response.status_code, 301)
                self.assertEqual(response.headers["Location"], f"/blog/{new}")

    def test_published_image_is_a_real_url_and_draft_is_not_served(self):
        page = self.client.get("/bd/soleil-saturne")
        self.assertEqual(page.status_code, 200)
        self.assertIn(b'/bd/soleil-saturne/image/0', page.data)
        self.assertNotIn(b'data:image/webp;base64', page.data)
        self.assertIn(b'facebook.com/sharer/sharer.php?u=', page.data)
        self.assertIn(b'wa.me/?text=', page.data)
        self.assertIn(b'pinterest.com/pin/create/button/?url=', page.data)
        image = self.client.get("/bd/soleil-saturne/image/0")
        self.assertEqual(image.status_code, 200)
        self.assertEqual(image.data, self.image)
        self.assertEqual(image.content_type, "image/webp")
        self.page["type"] = "draft"
        self.assertEqual(self.client.get("/bd/soleil-saturne/image/0").status_code, 404)
        self.assertEqual(self.client.post("/bd/soleil-saturne/commenter", data={}).status_code, 404)

    def test_comment_is_hidden_until_email_moderation(self):
        self.client.get("/bd/soleil-saturne")
        with self.client.session_transaction() as session:
            csrf = session["bd_comment_csrf"]
        email = types.ModuleType("utils.email_sender")
        messages = []
        email.envoyer_email_avec_analyse = lambda **kwargs: messages.append(kwargs) or True
        with patch.dict(sys.modules, {"utils.email_sender": email}):
            response = self.client.post("/bd/soleil-saturne/commenter", data={
                "csrf": csrf, "author": "Luna", "body": "Cette planche est très claire !",
            })
        self.assertEqual(response.status_code, 302)
        self.assertEqual(len(messages), 1)
        with self.app.app_context():
            comment = BdComment.query.one()
            self.assertEqual(comment.status, "pending")
            token = blog_module._moderation_signer().dumps(comment.id)
        self.assertNotIn(b"Cette planche est tr", self.client.get("/bd/soleil-saturne").data)
        moderation = self.client.get(f"/bd/commentaire/moderer/{token}")
        self.assertEqual(moderation.headers["Referrer-Policy"], "no-referrer")
        self.assertNotIn(b"googletagmanager", moderation.data)
        self.assertEqual(self.client.post(f"/bd/commentaire/moderer/{token}",
                                          data={"decision": "approved"}).status_code, 302)
        self.assertIn(b"Cette planche est tr", self.client.get("/bd/soleil-saturne").data)


if __name__ == "__main__":
    unittest.main()

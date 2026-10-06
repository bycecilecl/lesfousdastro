from unittest.mock import Mock

from utils import pdf_utils


def test_offer_is_appended_inside_body_once():
    html = "<html><body><main><p>Ton analyse</p></main></body></html>"

    result = pdf_utils.append_accompaniment_offer(html)

    assert result.index("Ton analyse") < result.index('id="accompaniment-offer"')
    assert result.index('id="accompaniment-offer"') < result.index("</body>")
    assert result.count('id="accompaniment-offer"') == 1
    assert pdf_utils.append_accompaniment_offer(result) == result
    assert pdf_utils.ACCOMPANIMENT_URL in result


def test_offer_is_appended_to_html_fragment():
    result = pdf_utils.append_accompaniment_offer("<p>Ton analyse</p>")

    assert result.startswith("<p>Ton analyse</p>")
    assert 'id="accompaniment-offer"' in result


def test_pdf_generation_includes_offer_by_default(tmp_path, monkeypatch):
    html_factory = Mock()
    html_factory.return_value.write_pdf.return_value = b"%PDF-test"
    monkeypatch.setattr(pdf_utils.weasyprint, "HTML", html_factory)
    monkeypatch.setattr(pdf_utils.weasyprint, "CSS", Mock())
    output = tmp_path / "analyse.pdf"

    assert pdf_utils.html_to_pdf("<html><body>Rapport</body></html>", str(output))
    assert output.read_bytes() == b"%PDF-test"
    assert 'id="accompaniment-offer"' in html_factory.call_args.kwargs["string"]

    assert pdf_utils.html_to_pdf("<p>Autre document</p>", str(output), include_accompaniment_offer=False)
    assert 'id="accompaniment-offer"' not in html_factory.call_args.kwargs["string"]

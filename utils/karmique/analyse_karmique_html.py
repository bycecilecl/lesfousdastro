import markdown
from markupsafe import escape


def build_html_from_blocks(blocks, nom="Analyse karmique", infos=None):

    infos = infos or {}

    sections = []

    for block in blocks:

        if block.get("id") in ("header", "sensitive_points"):
            continue

        title = block.get("title", "")
        llm_txt = (block.get("llm_content") or "").strip()
        content_txt = (block.get("content") or "").strip()

        txt = llm_txt if llm_txt else content_txt

        if not txt:
            continue

        # Supprime un éventuel titre markdown en tête de bloc
        lines = txt.splitlines()
        while lines and not lines[0].strip():
            lines.pop(0)

        if lines and lines[0].lstrip().startswith("#"):
            lines.pop(0)

        txt = "\n".join(lines).strip()

        if not txt:
            continue

        html_txt = markdown.markdown(txt, extensions=["extra", "nl2br"])

        sections.append(f"""
        <section class="chapter">
            <h2>{escape(title)}</h2>
            {html_txt}
        </section>
        """)

    return "".join(sections)
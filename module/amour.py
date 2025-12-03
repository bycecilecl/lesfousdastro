# module/amour.py

from module.amour_blocs.venus_mars import generer_bloc_venus_mars
from module.amour_blocs.soleil_lune import generer_bloc_soleil_lune
from module.amour_blocs.maisons_couple import (
    generer_bloc_maisons_amour,
    generer_bloc_maison7_couple,
    generer_bloc_maison8_intimite,
)
from module.amour_blocs.maniere_aimer import generer_bloc_maniere_aimer
from module.amour_blocs.partenaire_ideal import generer_bloc_partenaire_ideal
from module.amour_blocs.couple_ideal import generer_bloc_couple_ideal
from module.amour_blocs.intimite_sexualite import generer_bloc_intimite_sexualite


def _wrap_bloc_html(titre: str, contenu: str) -> str:
    """
    Met un bloc de texte dans une <section> avec un <h2>.
    Si le contenu contient déjà du HTML, on le laisse tel quel.
    """
    if not contenu:
        return ""

    lower = contenu.lower()
    if any(tag in lower for tag in ("<p", "<pre", "<h1", "<h2", "<section")):
        body = contenu
    else:
        paragraphs = [p.strip() for p in contenu.split("\n\n") if p.strip()]
        if not paragraphs:
            body = f"<p>{contenu.strip()}</p>"
        else:
            body = "".join(
                f"<p>{p.replace('\n', '<br>')}</p>" for p in paragraphs
            )

    return f"""
    <section class="amour-bloc">
      <h2>{titre}</h2>
      {body}
    </section>
    """


def generer_analyse_amour(theme, call_llm: bool = True) -> str:
    """
    Analyse Amour complète avec 4 modules :
      1) Ma manière d’aimer
      2) Partenaire idéal
      3) Couple idéal & dynamique relationnelle
      4) Intimité & sexualité
    """
    blocs_html = []

    # MODULE 1 · Ma manière d’aimer
    try:
        txt_m1 = generer_bloc_maniere_aimer(theme, call_llm=call_llm)
        blocs_html.append(
            _wrap_bloc_html("Module 1 · Ma manière d’aimer", txt_m1)
        )
    except Exception as e:
        blocs_html.append(
            f"<section class='amour-bloc'><h2>Module 1 · Ma manière d’aimer</h2>"
            f"<p>Erreur : {e}</p></section>"
        )

    # MODULE 2 · Partenaire idéal
    try:
        txt_m2 = generer_bloc_partenaire_ideal(theme, call_llm=call_llm)
        blocs_html.append(
            _wrap_bloc_html("Module 2 · Partenaire idéal : ce qui t’attire", txt_m2)
        )
    except Exception as e:
        blocs_html.append(
            f"<section class='amour-bloc'><h2>Module 2 · Partenaire idéal</h2>"
            f"<p>Erreur : {e}</p></section>"
        )

    # MODULE 3 · Couple idéal & dynamique relationnelle
    try:
        txt_m3 = generer_bloc_couple_ideal(theme, call_llm=call_llm)
        blocs_html.append(
            _wrap_bloc_html("Module 3 · Couple idéal & dynamique relationnelle", txt_m3)
        )
    except Exception as e:
        blocs_html.append(
            f"<section class='amour-bloc'><h2>Module 3 · Couple idéal & dynamique relationnelle</h2>"
            f"<p>Erreur : {e}</p></section>"
        )

    # MODULE 4 · Intimité & sexualité
    try:
        # polarite="Femme" en dur pour l’instant, comme dans les autres blocs
        txt_m4 = generer_bloc_intimite_sexualite(theme, call_llm=call_llm, polarite="Homme")
        blocs_html.append(
            _wrap_bloc_html("Module 4 · Intimité & sexualité", txt_m4)
        )
    except Exception as e:
        blocs_html.append(
            f"<section class='amour-bloc'><h2>Module 4 · Intimité & sexualité</h2>"
            f"<p>Erreur : {e}</p></section>"
        )

    html = """
    <div class="amour-analyse">
    """ + "\n".join(b for b in blocs_html if b) + """
    </div>
    """

    return html



# def generer_analyse_amour(theme, call_llm: bool = True) -> str:
#     blocs_html = []

#     # 1) Vénus / Mars
#     try:
#         txt_vm = generer_bloc_venus_mars(theme, call_llm=call_llm)
#         blocs_html.append(
#             _wrap_bloc_html("Vénus & Mars : ton désir et ton langage amoureux", txt_vm)
#         )
#     except Exception as e:
#         blocs_html.append(
#             f"<section class='amour-bloc'><h2>Vénus & Mars</h2>"
#             f"<p>Erreur : {e}</p></section>"
#         )

#     # 2) Soleil / Lune
#     try:
#         txt_sl = generer_bloc_soleil_lune(theme, call_llm=call_llm)
#         blocs_html.append(
#             _wrap_bloc_html("Soleil & Lune : ton cœur et ta sensibilité", txt_sl)
#         )
#     except Exception as e:
#         blocs_html.append(
#             f"<section class='amour-bloc'><h2>Soleil & Lune</h2>"
#             f"<p>Erreur : {e}</p></section>"
#         )

#     # 3) Maison 5
#     try:
#         txt_m5 = generer_bloc_maisons_amour(theme, call_llm=call_llm)
#         blocs_html.append(
#             _wrap_bloc_html("Maison 5 : ta manière d’aimer et de séduire", txt_m5)
#         )
#     except Exception as e:
#         blocs_html.append(
#             f"<section class='amour-bloc'><h2>Maison 5</h2>"
#             f"<p>Erreur : {e}</p></section>"
#         )

#     # 4) Maison 7
#     try:
#         txt_m7 = generer_bloc_maison7_couple(theme, call_llm=call_llm)
#         blocs_html.append(
#             _wrap_bloc_html("Maison 7 : le couple et le partenaire", txt_m7)
#         )
#     except Exception as e:
#         blocs_html.append(
#             f"<section class='amour-bloc'><h2>Maison 7</h2>"
#             f"<p>Erreur : {e}</p></section>"
#         )

#     # 5) Maison 8
#     try:
#         txt_m8 = generer_bloc_maison8_intimite(theme, call_llm=call_llm)
#         blocs_html.append(
#             _wrap_bloc_html("Maison 8 : intimité, fusion et transformation", txt_m8)
#         )
#     except Exception as e:
#         blocs_html.append(
#             f"<section class='amour-bloc'><h2>Maison 8</h2>"
#             f"<p>Erreur : {e}</p></section>"
#         )

#     # Assemblage final
#     html = """
#     <div class="amour-analyse">
#     """ + "\n".join(b for b in blocs_html if b) + """
#     </div>
#     """

#     return html
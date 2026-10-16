"""Reprise des blocs 3 et 5, avec les blocs 1, 2 et 4 conservés."""

from .execution import ROOT
from ...archives_generation import lire_json
from .execution_bloc_3_prompt_personnel import lancer_bloc_3_prompt_personnel
from .execution_bloc_5_prompt_personnel import charger_lectures, lancer_bloc_5_prompt_personnel
from .export_pdf import exporter_pdf, verifier_export_pdf


def lancer_blocs_3_et_5(cas_a_tester, *, source_bloc_4):
    """Deux appels maximum puis assemblage et PDF, sans régénérer les transits."""
    if len(cas_a_tester) != 1:
        raise ValueError("Un seul profil est attendu.")
    cas = cas_a_tester[0]
    reference = (ROOT / source_bloc_4).expanduser().resolve()
    # Vérifier les archives avant tout appel, sans modifier les anciens rapports.
    charger_lectures(cas, reference)
    demande_4 = lire_json(reference, "demande.json")
    demande_3 = lire_json((ROOT / demande_4["source_bloc_3"]).resolve(), "demande.json")
    source_2 = demande_3["source_bloc_2"]
    verifier_export_pdf()
    sources = {}

    def conserver_bloc_3(chemin):
        sources[3] = chemin

    def conserver_bloc_5(chemin):
        sources[5] = chemin

    print("REPRISE CIBLÉE — BLOC 3 PUIS BLOC 5", flush=True)
    print("Deux appels maximum ; blocs 1, 2 et 4 conservés. Aucun appel pour les transits.")
    code = lancer_bloc_3_prompt_personnel(
        cas_a_tester, source_bloc_2=source_2, sur_dossier=conserver_bloc_3)
    if code != 0:
        print("Le bloc 3 n'a pas terminé ; le bloc 5 n'est pas lancé. Aucune relance automatique.")
        return code
    code = lancer_bloc_5_prompt_personnel(
        cas_a_tester, source_bloc_4=reference, source_bloc_3=sources[3],
        sur_dossier=conserver_bloc_5)
    if code != 0:
        return code
    dossier = sources[5]
    pdf = exporter_pdf(dossier / "rapport_complet_assemble.html", dossier / "rapport_rs_v2.pdf",
                       personne=cas["personne"], lieu_rs=cas["lieu_rs"], annee=cas["annee"])
    print("\nREPRISE TERMINÉE — rapport à relire, nouveau bloc 3 et transits conservés.")
    print("Bloc 3 :", sources[3] / "lecture_bloc_3.html")
    print("Bloc 5 :", dossier / "lecture_bloc_5.html")
    print("Rapport entier :", dossier / "rapport_complet_assemble.html")
    print("PDF :", pdf)
    return 0

"""Reprise ciblée des blocs 3 et 4 depuis un bloc 2 archivé."""

from .execution_bloc_3_prompt_personnel import lancer_bloc_3_prompt_personnel
from .execution_bloc_4_prompt_personnel import lancer_bloc_4_prompt_personnel


def lancer_blocs_3_et_4(cas_a_tester, *, source_bloc_2):
    """Deux appels maximum ; aucune génération des blocs 1, 2 ou 5."""
    sources = {}

    def conserver_bloc_3(chemin):
        sources[3] = chemin

    def conserver_bloc_4(chemin):
        sources[4] = chemin

    print("REPRISE CIBLÉE — BLOC 3 PUIS BLOC 4", flush=True)
    print("Deux appels maximum ; les blocs 1 et 2 sont conservés, le bloc 5 n'est pas lancé.")
    code = lancer_bloc_3_prompt_personnel(
        cas_a_tester, source_bloc_2=source_bloc_2, sur_dossier=conserver_bloc_3)
    if code != 0:
        print("Le bloc 3 n'a pas terminé ; le bloc 4 n'est pas lancé. Aucune relance automatique.")
        return code
    if 3 not in sources:
        raise RuntimeError("Archive du bloc 3 absente ; aucun bloc 4 lancé.")

    code = lancer_bloc_4_prompt_personnel(
        cas_a_tester, source_bloc_3=sources[3], sur_dossier=conserver_bloc_4)
    if code != 0:
        return code
    print("\nBLOCS 3 ET 4 TERMINÉS — textes à relire.")
    for numero in (3, 4):
        print(f"Bloc {numero} :", sources[numero] / f"lecture_bloc_{numero}.html")
    return 0

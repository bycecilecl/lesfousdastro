# module/amour_bdd.py

import os
import re
import unicodedata
from functools import lru_cache

import pandas as pd

# On part du dossier courant (module/) et on remonte à la racine du projet
BASE_DIR = os.path.dirname(os.path.dirname(__file__))
AMOUR_DATA_DIR = os.path.join(BASE_DIR, "data", "amour")


def _normalize_col_name(name: str) -> str:
    """Normalise un nom de colonne en ascii lowercase avec underscores."""
    if name is None:
        return ""
    nfkd = unicodedata.normalize("NFKD", str(name))
    ascii_str = "".join(c for c in nfkd if not unicodedata.combining(c))
    ascii_str = ascii_str.lower()
    for ch in [" ", "-", "’", "'", "(", ")", "/"]:
        ascii_str = ascii_str.replace(ch, "_")
    ascii_str = "_".join(part for part in ascii_str.split("_") if part)
    return ascii_str


def _normalize_value(val: str) -> str:
    """Normalise une valeur pour comparaison (minuscules, trim, accents retirés)."""
    if val is None:
        return ""
    nfkd = unicodedata.normalize("NFKD", str(val))
    ascii_str = "".join(c for c in nfkd if not unicodedata.combining(c))
    return ascii_str.strip().lower()


@lru_cache(maxsize=None)
def _load_table(nom: str) -> pd.DataFrame:
    """
    Charge un CSV dans data/amour/ et normalise les colonnes.
    nom = 'placements', 'aspects', 'maisons_amour', 'maitre_en_maison', 'etat_planete'
    Gère aussi le cas des fichiers séparés par ';'.
    """
    path = os.path.join(AMOUR_DATA_DIR, nom + ".csv")
    if not os.path.exists(path):
        raise FileNotFoundError(f"Fichier amour introuvable : {path}")

    # 1er essai : séparateur par défaut (virgule)
    df = pd.read_csv(path)

    # Si on n'a qu'une seule colonne, c'est probablement un CSV avec ';'
    if len(df.columns) == 1:
        df = pd.read_csv(path, sep=";")

    # DEBUG éventuel
    print(f"[DEBUG] Fichier {nom}.csv - Colonnes brutes : {list(df.columns)}")

    df.columns = [_normalize_col_name(c) for c in df.columns]

    print(f"[DEBUG] Fichier {nom}.csv - Colonnes normalisées : {list(df.columns)}")

    return df


def _filtrer(df: pd.DataFrame, **criteres) -> pd.DataFrame:
    """
    Filtre générique : bloc="...", planete_1="Vénus", type_donnee="Signe",
    valeur="Balance", polarite="Femme", etc.
    Utilise _normalize_value pour éviter les bugs d'espaces / accents.
    Refuse tout critère actif dont la colonne est absente, même sans lignes.
    """
    colonnes_manquantes = sorted({
        _normalize_col_name(nom)
        for nom, valeur in criteres.items()
        if valeur is not None and _normalize_col_name(nom) not in df.columns
    })
    if colonnes_manquantes:
        raise ValueError(
            "Recherche BDD amour refusée : colonne(s) de filtre absente(s) : "
            + ", ".join(colonnes_manquantes)
            + ". Colonnes disponibles : " + ", ".join(map(str, df.columns))
        )
    if df.empty:
        return df

    mask = pd.Series(True, index=df.index)

    for col_logique, val in criteres.items():
        if val is None:
            continue
        col = _normalize_col_name(col_logique)

        # 🌟 Cas particulier pour POLARITÉ : accepter "Femme, Homme"
        if col == "polarite":
            series = df[col].astype(str).fillna("")
            val_norm = _normalize_value(val)

            def _match_polarite(x: str) -> bool:
                morceaux = [p for p in x.split(",") if p.strip()]
                morceaux_norm = [_normalize_value(p) for p in morceaux]
                return val_norm in morceaux_norm

            mask &= series.apply(_match_polarite)
        else:
            series_norm = df[col].astype(str).fillna("").map(_normalize_value)
            val_norm = _normalize_value(val)
            mask &= (series_norm == val_norm)

    return df[mask]


def get_from_placements(
    planete=None,
    type_donnee=None,
    valeur=None,
    bloc=None,
    polarite=None,
):
    """
    Lit placements.csv et filtre selon les paramètres.
    Gère automatiquement la colonne planète : PLANÈTE ou PLANÈTE_1.
    Pour les maisons, accepte 5, "5", "Maison_5" et "Maison 5".
    """
    df = _load_table("placements")

    if _normalize_value(type_donnee) == "maison" and valeur is not None:
        match = re.fullmatch(r"(?:maison[_\s]+)?(0?[1-9]|1[0-2])", _normalize_value(valeur))
        if match:
            valeur = str(int(match.group(1)))

    criteres = {
        "bloc": bloc,
        "polarite": polarite,
        "type_donnee": type_donnee,
        "valeur": valeur,
    }

    cols = df.columns
    if planete is not None:
        if "planete_1" in cols:
            criteres["planete_1"] = planete
        elif "planete" in cols:
            criteres["planete"] = planete
        else:
            # Conserver le critère pour que _filtrer signale le schéma invalide.
            criteres["planete"] = planete

    return _filtrer(df, **criteres)


def get_from_aspects(planete_1=None, planete_2=None, valeur=None, bloc=None, polarite=None):
    """
    Lit aspects.csv et filtre selon les paramètres.
    """
    df = _load_table("aspects")
    return _filtrer(
        df,
        bloc=bloc,
        polarite=polarite,
        planete_1=planete_1,
        planete_2=planete_2,
        valeur=valeur,
    )


def get_from_aspects_maitre(maitre, autre, aspect, bloc, polarite):
    """Aspect exact du maître, dans les deux orientations, sans autre type en repli."""
    valeur = {
        "conjonction": "Conjonction",
        "carre": "Carré",
        "opposition": "Opposition",
    }.get(_normalize_value(aspect), aspect)
    df = get_from_aspects(maitre, autre, valeur, bloc, polarite)
    if df.empty:
        df = get_from_aspects(autre, maitre, valeur, bloc, polarite)
    return df


def get_from_etat_planete(planete_1=None, valeur=None, bloc=None, polarite=None):
    """
    Lit etat_planete.csv et filtre selon les paramètres.
    Le paramètre historique planete_1 correspond à la colonne PLANÈTE du CSV.
    """
    df = _load_table("etat_planete")
    return _filtrer(
        df,
        bloc=bloc,
        polarite=polarite,
        planete=planete_1,
        valeur=valeur,
    )


def df_to_snippets(df: pd.DataFrame) -> str:
    """
    Concatène les colonnes INTERPRÉTATION / CE_QUE_TU_RECHERCHES /
    COMMENT_TU_VIS_L_AMOUR / DIFFICULTÉS / MOTS_CLÉS en une liste à puces.
    """
    if df is None or df.empty:
        return ""

    cols_prioritaires = [
        "interpretation",
        "ce_que_tu_recherches",
        "comment_tu_vis_l_amour",
        "difficultes",
        "mots_cles",
    ]

    cols_presentes = [c for c in cols_prioritaires if c in df.columns]

    lignes = []
    for _, row in df.iterrows():
        for col in cols_presentes:
            val = str(row[col]).strip()
            if val and val.lower() != "nan":
                lignes.append(f"- {val}")
    return "\n".join(lignes)


def get_from_maisons_amour(
    maison=None,
    type_donnee=None,
    valeur=None,
    bloc=None,
    polarite=None,
):
    """
    Lit maisons_amour.csv et filtre selon ta structure réelle :

    BLOC, POLARITÉ, MAISON, TYPE_DONNÉE, VALEUR, ...

    Exemples :
        Maison 5 en Verseau :
            get_from_maisons_amour(
                maison="Maison 5",
                type_donnee="Signe",
                valeur="Verseau",
                bloc="Style",
                polarite="Femme",
            )

        Vénus en Maison 5 :
            get_from_maisons_amour(
                maison="Maison 5",
                type_donnee="Planète",
                valeur="Vénus",
                bloc="Style",
                polarite="Femme",
            )
    """
    df = _load_table("maisons_amour")
    return _filtrer(
        df,
        bloc=bloc,
        polarite=polarite,
        maison=maison,
        type_donnee=type_donnee,
        valeur=valeur,
    )


def get_from_maitre_en_maison(maitre_maison=None, type_donnee=None, valeur=None, bloc=None, polarite=None):
    """
    Lit maitre_en_maison.csv et filtre comme les autres helpers.
    
    Exemple :
        get_from_maitre_en_maison(
            maitre_maison="maitre_maison_7",
            type_donnee="Maison",
            valeur="1",
            bloc="Style",
            polarite="Femme",
        )
    """
    df = _load_table("maitre_en_maison")
    return _filtrer(
        df,
        bloc=bloc,
        polarite=polarite,
        maitre_maison=maitre_maison,  # 🌟 AJOUT
        type_donnee=type_donnee,
        valeur=valeur,
    )


def get_from_noeuds(type_donnee: str, valeur: str, bloc: str, polarite: str):
    """Nœud Nord en signe : source unique placements.csv, sans omission silencieuse."""
    # Compatibilité avec l'ancien appel du module Couple.
    if _normalize_value(type_donnee) == "noeud_nord":
        type_donnee = "Signe"
    df = get_from_placements(
        planete="Noeud Nord", type_donnee=type_donnee, valeur=valeur,
        bloc=bloc, polarite=polarite,
    )
    if (df.empty or "interpretation" not in df.columns
            or df["interpretation"].fillna("").astype(str).str.strip().eq("").any()):
        raise ValueError(
            "Interprétation obligatoire du Nœud Nord absente ou vide dans "
            f"data/amour/placements.csv : type={type_donnee!r}, "
            f"valeur={valeur!r}, bloc={bloc!r}, polarite={polarite!r}."
        )
    return df

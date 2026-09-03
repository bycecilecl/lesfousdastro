# utils/transits/prompts.py

def interpretation_courte_transit(transit) -> str:
    """
    V1 déterministe : mini phrase de sens.
    Plus tard, ce sera remplacé/enrichi par le LLM.
    """

    t = transit.planete_transit
    n = transit.planete_natale
    aspect = transit.aspect

    return (
        f"{t} en {aspect} à {n} natal indique une période où "
        f"cette zone du thème est activée avec plus d'intensité."
    )

# utils/transits/prompts.py

def construire_prompt_bloc_transits(
    transits: list,
    interpretations_structurees: list[str],
    nom: str = "la personne",
    ascendant: str | None = None,
    dynamiques_periode: dict | None = None,
    genre: str | None = None,
) -> str:
    """
    Construit le prompt pour générer un bloc d'analyse de transits
    selon la méthode Bernadette Brady.

    Args:
        transits: liste de TransitActif, triés par importance décroissante.
        interpretations_structurees: une interprétation Brady par transit (même ordre).
        nom: prénom ou nom de la personne consultante.
        ascendant: signe ascendant (optionnel, enrichit le contexte).

    Returns:
        str: prompt complet prêt à envoyer au LLM.
    """
    if len(transits) != len(interpretations_structurees):
        raise ValueError(
            f"Mismatch entre transits ({len(transits)}) "
            f"et interprétations ({len(interpretations_structurees)})"
        )

    if not transits:
        raise ValueError("La liste de transits est vide.")

    # Bloc personne
    contexte_personne = f"Personne : {nom}"
    if ascendant:
        contexte_personne += f", ascendant {ascendant}"

    genre_normalise = (genre or "").strip().lower()
    if genre_normalise in {"femme", "female", "f", "woman", "w"}:
        consigne_genre = (
            "Accords grammaticaux : féminin. Accorde toutes les formulations "
            "qui désignent la personne au féminin."
        )
    elif genre_normalise in {"homme", "male", "m", "man", "h"}:
        consigne_genre = (
            "Accords grammaticaux : masculin. Accorde toutes les formulations "
            "qui désignent la personne au masculin."
        )
    else:
        consigne_genre = (
            "Le genre n’est pas renseigné : n’en déduis aucun à partir du prénom."
        )

    # Blocs transits — interprétation structurée uniquement,
    # données brutes en référence condensée
    blocs = []
    for i, (transit, interpretation) in enumerate(
        zip(transits, interpretations_structurees), start=1
    ):
        ctx = transit.contexte or {}

        maison_transit   = ctx.get("maison_transit", "?")
        maison_nat_t     = ctx.get("maison_natale_transit", "?")
        maison_nat_n     = ctx.get("maison_natale_planete", "?")
        maisons_reg_t    = ctx.get("maisons_gouvernees_transit") or "—"
        maisons_reg_n    = ctx.get("maisons_gouvernees_natale") or "—"

        conjonctions_associees = getattr(transit, "conjonctions_associees", [])

        if conjonctions_associees:
            texte_conjonctions = (
                f"\nContexte natal de {transit.planete_natale} : "
                f"{transit.planete_natale} est conjoint à "
                f"{', '.join(conjonctions_associees)}. "
                f"Le transit doit donc être interprété comme l’activation de cette configuration natale, "
                f"et pas comme un aspect isolé à {transit.planete_natale}."
            )
        else:
            texte_conjonctions = ""

        blocs.append(f"""
--- Transit {i} ---
{transit.planete_transit} {transit.aspect} {transit.planete_natale}
{texte_conjonctions}
Orbe actuel : {transit.orbe}°
Maisons activées (Brady) :
  - {transit.planete_transit} transite la maison {maison_transit}
  - {transit.planete_transit} natal : maison {maison_nat_t} | gouverne {maisons_reg_t}
  - {transit.planete_natale} natal : maison {maison_nat_n} | gouverne {maisons_reg_n}
Lecture structurée :
{interpretation.strip()}
""")

    contenu = "\n".join(blocs)

    bloc_dynamique = ""

    if dynamiques_periode:
        lignes = []

        for planete, infos in dynamiques_periode.items():

            lignes.append(f"\n=== {planete} ===")

            for evt in infos["evenements"]:

                txt = (
                    f"- {evt['aspect']} "
                    f"{evt['planete_natale']} "
                    f"(orbe {evt['orbe']}°)"
                )

                conjs = evt.get("conjonctions_associees", [])

                if conjs:
                    configuration = [evt["planete_natale"]] + conjs

                    txt += (
                        " | CONFIGURATION NATALE ACTIVÉE : "
                        + " + ".join(configuration)
                        + ". Cette configuration doit être interprétée comme un ensemble central, "
                        + "pas comme une simple note secondaire."
                    )

                lignes.append(txt)

            lignes.append(f"Score période : {infos['score']}")

        bloc_dynamique = "\n".join(lignes)

    return f"""
Tu es expert en astrologie psychologique, formé à la méthode Bernadette Brady.
{contexte_personne}.
{consigne_genre}

Voici les transits actifs, classés par importance décroissante :
{contenu}

Grandes dynamiques de la période :
{bloc_dynamique}

Consigne de rédaction :
Rédige une analyse en texte fluide, sans titres, sans numérotation, en "tu".
- Il s'agit d'un Flash Transits : une photographie de la période actuelle, pas
  d'une prévision mensuelle ni d'une chronologie des événements.
- Commence par une ou deux phrases sur le climat général du moment.
- Développe les transit dominants avec profondeur.
- Si une même planète en transit revient plusieurs fois, considère qu’elle peut former le climat dominant de la période, surtout si elle touche le Soleil, la Lune ou l’Ascendant.
- Si un transit touche une planète natale conjointe à d'autres planètes ou angles, interprète le transit comme l'activation de toute cette configuration natale, et non comme un aspect isolé.
- Les transits aux angles, surtout Ascendant et Milieu du Ciel, doivent être traités comme des marqueurs majeurs de période. 
- Un transit au Milieu du Ciel doit être relié explicitement à la carrière, la visibilité, la direction de vie et la reconnaissance sociale.
- Intègre les autres dynamiques naturellement, sans les lister mécaniquement.
- Conclus avec ce qui est concret : ce que la personne peut observer, traverser ou initier.

Style :
- Direct, incarné, psychologique
- Pas de formules d'horoscope ("les astres vous invitent à...")
- Pas de prédictions fatalistes
- Pas de spiritualité floue
- Tutoiement ("tu") du début à la fin

Longueur : entre 600 et 700 mots, pas plus.
""".strip()

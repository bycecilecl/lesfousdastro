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
                    f"(orbe minimal observé {evt['orbe']}°, "
                    f"autour du {evt.get('date_detection') or 'jour non précisé'})"
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
Rédige une analyse approfondie, personnalisée et structurée, en "tu".
Utilise exactement les six titres ci-dessous, précédés de "## ", avec une ligne
vide après chaque titre. N'ajoute aucun autre titre et aucune numérotation.

## Le climat dominant
Synthétise les deux ou trois forces majeures et surtout leur interaction. Ne fais
pas une simple succession de transits. Limite cette ouverture à deux ou trois
paragraphes denses : elle pose la vision d'ensemble sans déjà épuiser tous les
détails développés ensuite.

## Ce qui travaille en profondeur
Développe les transits lents dominants, les fonctions psychologiques touchées,
les maisons activées et les éventuelles configurations natales réveillées. C'est
ici, et uniquement ici, que tu expliques en détail la mécanique astrologique de
chaque transit majeur.

## Comment cela peut se manifester
Traduis l'analyse dans les domaines de vie réellement indiqués par les maisons :
relations, travail, orientation, foyer, émotions, argent ou décisions. Donne des
manifestations possibles et concrètes, sans affirmer qu'elles vont nécessairement
se produire et sans inventer de contexte biographique. Ne réexplique pas les
aspects ni les maîtrises déjà analysés : approfondis leurs conséquences vécues.

## Le rythme autour de la date choisie
À partir des grandes dynamiques de la période, distingue ce qui monte, ce qui est
le plus sensible autour des dates fournies et ce qui commence à se relâcher. Les
dates proviennent d'un échantillonnage : emploie toujours "autour de" ou "vers",
jamais une date comme certitude ni comme prédiction d'événement.
Ne reprends pas l'analyse psychologique complète des transits : concentre cette
section sur l'évolution, les croisements et les moments les plus sensibles.

## Tes points de vigilance
Expose deux à quatre pièges ou réactions possibles, précisément reliés aux
transits dominants. Reste lucide et nuancé, sans dramatisation.
Ne répète pas leur définition astrologique.

## Comment utiliser cette période
Propose des pistes concrètes et personnalisées : ce que la personne peut observer,
clarifier, initier, ralentir ou protéger. Termine par une synthèse mémorable mais
non fataliste. Chaque conseil doit apporter une réponse pratique nouvelle, et non
reformuler un point de vigilance précédent.

- Il s'agit d'un Point Transits centré sur la période actuelle et les six semaines
  qui l'entourent, pas d'une prévision annuelle.
- Développe les transits dominants avec profondeur.
- Si une même planète en transit revient plusieurs fois, considère qu’elle peut former le climat dominant de la période, surtout si elle touche le Soleil, la Lune ou l’Ascendant.
- Si un transit touche une planète natale conjointe à d'autres planètes ou angles, interprète le transit comme l'activation de toute cette configuration natale, et non comme un aspect isolé.
- Les transits aux angles, surtout Ascendant et Milieu du Ciel, doivent être traités comme des marqueurs majeurs de période. 
- Un transit au Milieu du Ciel doit être relié explicitement à la carrière, la visibilité, la direction de vie et la reconnaissance sociale.
- Intègre les autres dynamiques naturellement, sans les lister mécaniquement.
- Préserve la profondeur psychologique et la richesse concrète de chaque section.
- Chaque transit majeur reçoit une analyse approfondie complète, mais une seule
  fois. Dans les sections suivantes, fais progresser la lecture au lieu de répéter
  sa signification, ses maisons, ses maîtrises ou les mêmes mises en garde.
- Les répétitions lexicales et les rappels utiles sont permis lorsqu'ils assurent
  la cohérence ; seules les redites qui n'apportent aucune information sont à retirer.
- Le mot "conjonction" désigne un aspect situé dans l'orbe admis, pas une
  superposition exacte. N'emploie jamais "pile", "exact", "exactement",
  "culmine" ou "culmination" pour qualifier un aspect ou une date : les données
  fournies ne calculent pas l'instant d'exactitude. Même un orbe affiché à 0,00°
  est arrondi et un minimum observé reste une approximation.

Style :
- Direct, incarné, psychologique
- Pas de formules d'horoscope ("les astres vous invitent à...")
- Pas de prédictions fatalistes
- Pas de spiritualité floue
- Tutoiement ("tu") du début à la fin

Longueur : entre 1300 et 1600 mots. Privilégie la densité, la profondeur et la
personnalisation ; n'allonge jamais artificiellement avec des généralités.
""".strip()

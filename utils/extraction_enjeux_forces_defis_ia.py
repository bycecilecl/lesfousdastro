"""Synthèse courte des enjeux durables d'un rapport Potentiels & Défis.

Le module n'est appelé qu'après une action explicite de la personne dans son
espace. Il ne régénère jamais le rapport d'origine.
"""

from utils.extraction_enjeux_transits_ia import (
    EnjeuExtrait,
    construire_messages_enjeux_transits,
    valider_reponse_enjeux_transits,
)


def construire_messages_enjeux_forces_defis(sections):
    """Construit la consigne spécifique aux enjeux structurels du thème."""
    messages = construire_messages_enjeux_transits(sections)
    messages[0]["content"] = """Tu synthétises un rapport astrologique Potentiels & Défis déjà rédigé.
Tu ne recrées pas le rapport : tu en fais ressortir seulement les enjeux de fond
du thème. Ils décrivent des dynamiques durables, jamais un destin, un diagnostic
ni un événement certain. Tu conserves le tutoiement et le ton direct du rapport
sans augmenter son degré de certitude. Réponds exclusivement avec un objet JSON
valide, sans markdown ni commentaire."""
    messages[1]["content"] = messages[1]["content"].replace(
        "une seule phrase courte sur un enjeu dominant de la période",
        "une seule phrase courte sur un enjeu durable du thème",
    ).replace(
        "tendances répétées ou fortement structurantes",
        "dynamiques structurelles, tensions et ressources réellement récurrentes",
    ).replace(
        "possibilité temporaire",
        "possibilité astrologique",
    ).replace(
        "Aucune section de Transits exploitable n'a été fournie.",
        "Aucune section Potentiels & Défis exploitable n'a été fournie.",
    )
    return messages


def generer_enjeux_forces_defis_avec_claude(sections, modele=None):
    """Appelle Claude explicitement et valide les enjeux extraits."""
    from utils.claude_espace import CLIENT, MODEL, creer_message_claude, ouvrir_flux_claude

    messages = construire_messages_enjeux_forces_defis(sections)
    reponse = creer_message_claude(client=CLIENT, 
        model=modele or MODEL,
        system=messages[0]["content"],
        messages=[{"role": "user", "content": messages[1]["content"]}],
        temperature=0.2,
        max_tokens=900,
    )
    contenu = "".join(
        bloc.text
        for bloc in reponse.content
        if getattr(bloc, "type", None) == "text"
    ).strip()
    enjeux: list[EnjeuExtrait] = valider_reponse_enjeux_transits(contenu, sections)
    usage = {
        "tokens_entree": reponse.usage.input_tokens,
        "tokens_sortie": reponse.usage.output_tokens,
        "tokens_total": reponse.usage.input_tokens + reponse.usage.output_tokens,
    }
    return enjeux, usage

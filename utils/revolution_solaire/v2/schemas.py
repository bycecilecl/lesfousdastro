"""Schémas API : enjeux, exemples, preuves et liens, sans grille par fait."""


def objet(proprietes):
    return {"type": "object", "properties": proprietes, "required": list(proprietes),
            "additionalProperties": False}


def liste_textes():
    return {"type": "array", "items": {"type": "string"}}


def schema_analyse(etape, entree):
    texte = {"type": "string"}
    enjeu = {
        "id": texte, "titre": texte, "importance": {"type": "string", "enum": ["majeur", "secondaire"]},
        "lecture": texte, "preuves": liste_textes(), "liens": liste_textes(),
        "effet": {"type": "string", "enum": ["initial", "confirme", "amplifie", "nuance", "contredit", "distinct"]},
        "exemples": {"type": "array", "items": objet({"texte": texte, "preuves": liste_textes()})},
    }
    if etape == "activations_annuelles":
        enjeu["periodes"] = liste_textes()
    schema = {"enjeux": {"type": "array", "items": objet(enjeu)}}
    if etape == "rs_seule":
        schema["ambiance"] = texte
    return objet(schema)


def schema_corps():
    texte = {"type": "string"}
    return objet({"sections": {"type": "array", "items": objet({
        "role": {"type": "string", "enum": ["ambiance", "enjeu", "profection", "periode"]},
        "titre": texte, "texte": texte, "enjeux": liste_textes(), "preuves": liste_textes(),
    })}})


def schema_conclusion():
    return objet({"texte": {"type": "string"}, "enjeux": liste_textes(), "preuves": liste_textes()})

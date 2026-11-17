"""Configuration pure des requêtes de l’espace ; aucun client ni appel API."""
import os

MODEL = os.getenv("ANTHROPIC_MODEL_MAIL_ABONNE", "claude-sonnet-5-5")

def preparer_parametres_claude(parametres):
    resultat = dict(parametres)
    resultat.setdefault("model", MODEL)
    if str(resultat["model"]).startswith("claude-sonnet-5-5"):
        for nom in ("temperature", "top_p", "top_k"):
            resultat.pop(nom, None)
        if "thinking" not in resultat:
            resultat["thinking"] = {"type": "between_tools"}
        elif resultat["thinking"].get("type") == "disabled":
            resultat["thinking"] = {"type": "between_tools"}
        supplement = dict(resultat.get("extra_body") or {})
        configuration = dict(supplement.get("output_config") or {})
        configuration.update(resultat.pop("output_config", {}) or {})
        configuration.setdefault("effort", "medium")
        supplement["output_config"] = configuration
        resultat["extra_body"] = supplement
    return resultat

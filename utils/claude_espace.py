"""Appels propres à l’espace ; le client des rapports reste inchangé."""
from contextlib import contextmanager
import json
import logging
import os
from utils.claude_llm import CLIENT, BlocTronqueError
MODEL = os.getenv("ANTHROPIC_MODEL_MAIL_ABONNE", "claude-sonnet-5-5")
logger = logging.getLogger(__name__)

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


def extraire_texte_claude(reponse):
    return "\n".join(
        bloc.text for bloc in reponse.content
        if getattr(bloc, "type", None) == "text"
    ).strip()


def _afficher_requete_claude(parametres):
    print("\n=== CLAUDE : PARAMETRES ET PROMPTS EFFECTIFS ===", flush=True)
    print(json.dumps(parametres, ensure_ascii=False, indent=2), flush=True)


def _afficher_reponse_claude(reponse):
    print("\n=== CLAUDE : REPONSE BRUTE ET TOKENS ===", flush=True)
    print(reponse.model_dump_json(indent=2), flush=True)
    logger.info("Claude model=%s stop_reason=%s input_tokens=%s output_tokens=%s",
                reponse.model, reponse.stop_reason,
                reponse.usage.input_tokens, reponse.usage.output_tokens)


def creer_message_claude(*, client=None, **parametres):
    parametres = preparer_parametres_claude(parametres)
    _afficher_requete_claude(parametres)
    actif = (CLIENT if client is None else client).with_options(max_retries=0)
    reponse = actif.messages.create(**parametres)
    _afficher_reponse_claude(reponse)
    return reponse


class _FluxClaude:
    """Conserve le message final sans declencher deux fois les traces du moteur."""
    def __init__(self, flux):
        self._flux = flux
        self._message = None

    def get_final_message(self):
        if self._message is None:
            self._message = self._flux.get_final_message()
        return self._message

    def __getattr__(self, nom):
        return getattr(self._flux, nom)


@contextmanager
def ouvrir_flux_claude(*, client=None, **parametres):
    parametres = preparer_parametres_claude(parametres)
    _afficher_requete_claude(parametres)
    actif = (CLIENT if client is None else client).with_options(max_retries=0)
    with actif.messages.stream(**parametres) as flux:
        suivi = _FluxClaude(flux)
        try:
            yield suivi
        except BaseException:
            # Afficher un fragment recu sans masquer l'erreur initiale.
            try:
                partiel = flux.current_message_snapshot
                print("=== CLAUDE : REPONSE PARTIELLE ===", flush=True)
                print(partiel.model_dump_json(indent=2), flush=True)
            except Exception:
                pass
            raise
        else:
            _afficher_reponse_claude(suivi.get_final_message())


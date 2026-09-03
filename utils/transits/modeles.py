# utils/transits/modeles.py

from dataclasses import dataclass, field
from typing import List, Optional, Dict, Any



@dataclass
class TransitActif:
    planete_transit: str
    planete_natale: str
    aspect: str
    orbe: float
    date_exacte: Optional[str] = None
    importance: int = 1
    application: bool = True
    contexte: Dict[str, Any] = field(default_factory=dict)
    conjonctions_associees: List[str] = field(default_factory=list)


@dataclass
class ResultatTransits:
    nom: str
    periode: str
    transits_actifs: List[TransitActif] = field(default_factory=list)
    donnees_calcul: Dict[str, Any] = field(default_factory=dict)
    texte_html: str = ""
    erreur: Optional[str] = None

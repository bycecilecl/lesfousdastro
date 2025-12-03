# module/amour_blocs/dignites.py

def get_dignite_planete(planete: str, signe: str) -> str | None:
    """
    Retourne l'état de dignité d'une planète dans un signe donné.
    
    Retourne :
    - "Domicile" : planète chez elle
    - "Exaltation" : planète renforcée
    - "Exil" : planète en difficulté
    - "Chute" : planète affaiblie
    - None : dignité neutre (péregrine)
    """
    # Normaliser les noms
    planete = planete.strip()
    signe = signe.strip()
    
    # Dictionnaire des dignités
    dignites = {
        "Soleil": {
            "Domicile": ["Lion"],
            "Exaltation": ["Bélier"],
            "Exil": ["Verseau"],
            "Chute": ["Balance"],
        },
        "Lune": {
            "Domicile": ["Cancer"],
            "Exaltation": ["Taureau"],
            "Exil": ["Capricorne"],
            "Chute": ["Scorpion"],
        },
        "Mercure": {
            "Domicile": ["Gémeaux", "Vierge"],
            "Exaltation": ["Vierge"],  # Certains disent Verseau
            "Exil": ["Sagittaire", "Poissons"],
            "Chute": ["Poissons"],
        },
        "Vénus": {
            "Domicile": ["Taureau", "Balance"],
            "Exaltation": ["Poissons"],
            "Exil": ["Bélier", "Scorpion"],
            "Chute": ["Vierge"],
        },
        "Mars": {
            "Domicile": ["Bélier", "Scorpion"],
            "Exaltation": ["Capricorne"],
            "Exil": ["Taureau", "Balance"],
            "Chute": ["Cancer"],
        },
        "Jupiter": {
            "Domicile": ["Sagittaire", "Poissons"],
            "Exaltation": ["Cancer"],
            "Exil": ["Gémeaux", "Vierge"],
            "Chute": ["Capricorne"],
        },
        "Saturne": {
            "Domicile": ["Capricorne", "Verseau"],
            "Exaltation": ["Balance"],
            "Exil": ["Cancer", "Lion"],
            "Chute": ["Bélier"],
        },
    }
    
    if planete not in dignites:
        return None
    
    for etat, signes in dignites[planete].items():
        if signe in signes:
            return etat
    
    return None  # Péregrine (dignité neutre)
# test_calcul_theme.py
from main import calcul_theme  # ou le vrai chemin si déplacé

theme = calcul_theme(
    nom="Test",
    date_naissance="1995-04-22",
    heure_naissance="13:15",
    lieu_naissance="Chambray-les-Tours"
)

print("🌑 Lune Noire :", theme['planetes'].get('Lune Noire'))
print("🪐 Chiron :", theme['planetes'].get('Chiron'))
print("🔒 Axes interceptés :", theme.get('interceptions'))
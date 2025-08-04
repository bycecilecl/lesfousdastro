from utils.email_sender import envoyer_email_avec_analyse

# Test avec analyse simple en HTML
contenu_html = """
<h1>Ton Analyse Astrologique</h1>
<p>Voici un aperçu de ton thème natal. Soleil en Lion, Ascendant Gémeaux… ça brille et ça parle beaucoup 😄</p>
"""

destinataire = "cecilecl@gmail.com"  # Mets une adresse valide que tu peux vérifier
sujet = "Test : Analyse Astrologique Gratuite"

# Sans pièce jointe
envoyer_email_avec_analyse(destinataire, sujet, contenu_html)

# 👉 ou AVEC pièce jointe (ex: PDF généré)
# envoyer_email_avec_analyse(destinataire, sujet, contenu_html, pdf_path="chemin/vers/analyse.pdf")
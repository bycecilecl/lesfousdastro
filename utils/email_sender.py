# ─────────────────────────────────────────────────────────────────────────────
# UTIL : envoyer_email_avec_analyse()
# Rôle : envoie un email (HTML) au destinataire via yagmail, avec option de PDF
#        en pièce jointe.
# Entrées :
#   - destinataire (str) : adresse email de réception
#   - sujet (str)        : sujet du message
#   - contenu_html (str) : corps du mail en HTML
#   - pdf_path (str|None): chemin du PDF à joindre (optionnel)
# Dépendances :
#   - Variables d’environnement chargées via .env :
#       EMAIL_ENVOI   → adresse expéditrice (ex : ton Gmail)
#       EMAIL_PASSWORD→ mot de passe applicatif (Gmail : “App Password”)
#   - yagmail (SMTP simplifié)
# Sortie : log console “✅ Email envoyé …” ou message d’erreur.
# Où c’est utilisé :
#   - Analyse gratuite : envoi du texte généré à l’utilisateur
#   - Point Astral (route afficher_point_astral) : envoi du lien de téléchargement PDF
# Remarques :
#   - Si tu utilises Gmail : nécessite un “mot de passe d’application”.
#   - `attachments` n’est ajouté que si `pdf_path` est fourni.
# ─────────────────────────────────────────────────────────────────────────────


import yagmail
import os
from dotenv import load_dotenv

load_dotenv()

def envoyer_email_avec_analyse(destinataire, sujet, contenu_html, pdf_path=None):
    email_exp = os.getenv("EMAIL_ENVOI")
    mdp_app = os.getenv("EMAIL_PASSWORD")

    try:
        yag = yagmail.SMTP(user=email_exp, password=mdp_app)
        attachments = [pdf_path] if pdf_path else None

        # 🎯 SOLUTION : Expliciter le format HTML avec yagmail
        yag.send(
            to=destinataire,
            subject=sujet,
            contents=[contenu_html],  # ⚡ Liste au lieu de string directe
            attachments=attachments,
            # 🆕 Forcer le HTML explicitement
            headers={'Content-Type': 'text/html; charset=utf-8'}
        )

        print(f"✅ Email envoyé à {destinataire}")

    except Exception as e:
        print(f"❌ Erreur lors de l'envoi de l'email à {destinataire} : {e}")


def creer_email_point_astral_compatible(prenom, url_drive):
    """
    Template email ultra-compatible avec tous les clients mail
    """
    
    # Version texte (fallback)
    contenu_texte = f"""
Bonjour {prenom} !

Merci pour ta confiance !

Ton Point Astral est prêt. Tu peux le télécharger ici :
https://tonsite.com{url_drive}

À bientôt,
L'équipe des Fous d'Astro
    """
    
    # Version HTML ultra-compatible
    contenu_html = f"""
<!DOCTYPE html>
<html>
<head>
    <meta charset="utf-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>Ton Point Astral - Les Fous d'Astro</title>
</head>
<body style="margin: 0; padding: 20px; font-family: Arial, Helvetica, sans-serif; line-height: 1.6; background-color: #f5f5f5;">
    
    <!-- Container principal -->
    <table width="100%" cellpadding="0" cellspacing="0" style="max-width: 600px; margin: 0 auto; background-color: white; border-radius: 10px; overflow: hidden; box-shadow: 0 4px 15px rgba(0,0,0,0.1);">
        
        <!-- Header avec logo et couleurs -->
        <tr>
            <td style="background: linear-gradient(135deg, #1f628e 0%, #00a8a8 100%); padding: 30px 20px; text-align: center;">
                <h1 style="color: white; margin: 0; font-size: 24px; font-weight: bold;">✨ Les Fous d'Astro ✨</h1>
                <p style="color: rgba(255,255,255,0.9); margin: 10px 0 0 0; font-size: 16px;">Ton Point Astral est prêt !</p>
            </td>
        </tr>
        
        <!-- Contenu principal -->
        <tr>
            <td style="padding: 40px 30px;">
                
                <!-- Salutation -->
                <h2 style="color: #1f628e; margin: 0 0 20px 0; font-size: 22px;">Bonjour {prenom} ! 🌟</h2>
                
                <!-- Message principal -->
                <p style="color: #333; margin: 0 0 25px 0; font-size: 16px; line-height: 1.7;">
                    Merci pour ta confiance ! Nous espérons que cette analyse t'apportera des insights précieux sur ton potentiel astrologique.
                </p>
                
                <!-- Bouton de téléchargement -->
                <table width="100%" cellpadding="0" cellspacing="0" style="margin: 30px 0;">
                    <tr>
                        <td style="text-align: center;">
                            <a href="https://tonsite.com{url_drive}" 
                               style="display: inline-block; padding: 15px 30px; background: linear-gradient(135deg, #1f628e, #00a8a8); color: white; text-decoration: none; border-radius: 25px; font-weight: bold; font-size: 16px; border: none;">
                                📄 Télécharger ton Point Astral
                            </a>
                        </td>
                    </tr>
                </table>
                
                <!-- Lien de secours -->
                <p style="color: #666; font-size: 14px; text-align: center; margin: 20px 0 0 0;">
                    Si le bouton ne fonctionne pas, copie ce lien dans ton navigateur :<br>
                    <a href="https://tonsite.com{url_drive}" style="color: #1f628e; word-break: break-all;">https://tonsite.com{url_drive}</a>
                </p>
                
            </td>
        </tr>
        
        <!-- Footer -->
        <tr>
            <td style="background-color: #f8f9fa; padding: 25px 30px; text-align: center; border-top: 1px solid #e9ecef;">
                <p style="color: #666; margin: 0; font-size: 14px;">
                    À bientôt pour de nouvelles découvertes astrologiques !<br>
                    <strong style="color: #1f628e;">L'équipe des Fous d'Astro</strong>
                </p>
                
                <!-- Infos légales -->
                <p style="color: #999; margin: 15px 0 0 0; font-size: 12px;">
                    Cet email a été envoyé car tu as commandé une analyse sur notre site.<br>
                    Si tu as des questions, réponds simplement à cet email.
                </p>
            </td>
        </tr>
        
    </table>
    
    <!-- Version texte cachée pour compatibilité -->
    <div style="display: none; font-size: 1px; color: #ffffff; line-height: 1px; max-height: 0px; max-width: 0px; opacity: 0; overflow: hidden;">
        {contenu_texte.replace(chr(10), ' ')}
    </div>
    
</body>
</html>
    """
    
    return contenu_html


# 🎯 NOUVELLE FONCTION PRINCIPALE RECOMMANDÉE
def envoyer_email_point_astral_v2(destinataire, prenom, url_drive, pdf_path=None):
    """
    Version améliorée pour envoyer l'email du Point Astral
    """
    email_exp = os.getenv("EMAIL_ENVOI")
    mdp_app = os.getenv("EMAIL_PASSWORD")
    
    try:
        yag = yagmail.SMTP(user=email_exp, password=mdp_app)
        
        # Créer le contenu compatible
        contenu_html = creer_email_point_astral_compatible(prenom, url_drive)
        
        # Version texte de secours
        contenu_texte = f"""
Bonjour {prenom} !

Merci pour ta confiance !

Ton Point Astral est prêt. Tu peux le télécharger ici :
https://tonsite.com{url_drive}

À bientôt,
L'équipe des Fous d'Astro
        """
        
        # Envoi multipart (texte + HTML)
        yag.send(
            to=destinataire,
            subject=f"✨ Ton Point Astral est prêt, {prenom} !",
            contents=[
                contenu_texte,  # Version texte
                contenu_html    # Version HTML
            ],
            attachments=[pdf_path] if pdf_path else None
        )
        
        print(f"✅ Email Point Astral envoyé à {destinataire}")
        
    except Exception as e:
        print(f"❌ Erreur envoi email Point Astral à {destinataire} : {e}")
        # Fallback : version simple
        envoyer_email_simple_fallback(destinataire, prenom, url_drive, pdf_path)


def envoyer_email_simple_fallback(destinataire, prenom, url_drive, pdf_path=None):
    """
    Version de secours ultra-simple si la version HTML échoue
    """
    email_exp = os.getenv("EMAIL_ENVOI")
    mdp_app = os.getenv("EMAIL_PASSWORD")
    
    try:
        yag = yagmail.SMTP(user=email_exp, password=mdp_app)
        
        contenu_simple = f"""
Bonjour {prenom} !

Ton Point Astral est prêt ! 🌟

Télécharge-le ici : https://tonsite.com{url_drive}

Merci pour ta confiance !

L'équipe des Fous d'Astro ✨
        """
        
        yag.send(
            to=destinataire,
            subject=f"Ton Point Astral - {prenom}",
            contents=contenu_simple,
            attachments=[pdf_path] if pdf_path else None
        )
        
        print(f"✅ Email simple envoyé à {destinataire}")
        
    except Exception as e:
        print(f"❌ Erreur critique email : {e}") 
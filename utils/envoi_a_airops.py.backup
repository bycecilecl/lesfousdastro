import requests

def envoyer_a_airops(email, prenom, texte_analyse):
    url = "https://app.airops.com/public_api/airops_apps/066dc3e4-4acd-4b04-bc83-d09c239b7424/execute"

    payload = {
        "inputs": {
            "email": email,
            "prenom": prenom,
            "texte_analyse": texte_analyse
        }
    }

    headers = {
        "Content-Type": "application/json"
    }

    response = requests.post(url, headers=headers, json=payload)
    print("🧾 Code retour :", response.status_code)
    print("🔍 Réponse brute :", response.text)

    response.raise_for_status()
    print("✅ Analyse envoyée via AirOps.")
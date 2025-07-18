# Utilise une image officielle Python avec gcc pour compiler pyswisseph
FROM python:3.10-slim

# Installations système nécessaires pour compiler pyswisseph
RUN apt-get update && \
    apt-get install -y build-essential curl wget unzip && \
    apt-get clean

# Crée le dossier de travail
WORKDIR /app

# Copie les fichiers de l'app dans le conteneur
COPY . .

# Installe les dépendances Python
RUN pip install --upgrade pip
RUN pip install -r requirements.txt

# Expose le port sur lequel ton app tourne
EXPOSE 8080

# Commande de démarrage (gunicorn pour Render)
CMD ["gunicorn", "--bind", "0.0.0.0:8080", "main:app"]

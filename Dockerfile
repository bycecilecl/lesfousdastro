# Utilise une image officielle Python avec gcc pour compiler pyswisseph
FROM python:3.10-slim

# Installation des bibliothèques nécessaires à pyswisseph ET WeasyPrint
RUN apt-get update && apt-get install -y \
    build-essential \
    curl \
    wget \
    unzip \
    libffi-dev \
    libpango-1.0-0 \
    libpangocairo-1.0-0 \
    libcairo2 \
    libgdk-pixbuf2.0-0 \
    libglib2.0-0 \
    libxml2 \
    libxslt1.1 \
    libjpeg62-turbo \
    libfontconfig1 \
    libgobject-2.0-0 \
    && apt-get clean && rm -rf /var/lib/apt/lists/*

# Crée le dossier de travail
WORKDIR /app

# Copie les fichiers de l'app dans le conteneur
COPY . .

# Installe les dépendances Python
RUN pip install --upgrade pip
RUN pip install -r requirements.txt

# Expose le port sur lequel ton app tourne
EXPOSE 8080

# Commande de démarrage (gunicorn pour Render ou Railway)
CMD ["gunicorn", "--bind", "0.0.0.0:8080", "main:app"]
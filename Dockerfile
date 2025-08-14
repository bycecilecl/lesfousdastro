FROM python:3.12-slim-bookworm

ENV DEBIAN_FRONTEND=noninteractive

# Dépendances RUNTIME pour WeasyPrint (pas les *-dev) + utilitaires
RUN apt-get update -o Acquire::Retries=3 && \
    apt-get install -y --no-install-recommends \
      curl \
      wget \
      unzip \
      libcairo2 \
      libpango-1.0-0 \
      libgdk-pixbuf-2.0-0 \
      libxml2 \
      libxslt1.1 \
      shared-mime-info \
      fonts-dejavu-core \
      && rm -rf /var/lib/apt/lists/*

# (optionnel) Si un package Python compile des wheels natifs, décommente:
# RUN apt-get update -o Acquire::Retries=3 && \
#     apt-get install -y --no-install-recommends build-essential pkg-config libffi-dev && \
#     rm -rf /var/lib/apt/lists/*

# Copie des éphémérides AVANT l’installation (utile pour tests)
COPY ephe/ /app/ephe/

WORKDIR /app
COPY requirements.txt .
RUN pip install --no-cache-dir --upgrade pip && \
    pip install --no-cache-dir -r requirements.txt

COPY . .
EXPOSE 8080

# Gunicorn en prod
CMD ["gunicorn", "--bind", "0.0.0.0:8080", "main:app"]
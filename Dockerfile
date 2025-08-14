FROM python:3.12-slim-bookworm

# Logs lisibles + pas de .pyc
ENV DEBIAN_FRONTEND=noninteractive \
    PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1

# Dépendances RUNTIME (WeasyPrint) + outils de build (temporaires)
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
      build-essential \
      gcc \
      pkg-config \
      libffi-dev \
      python3-dev \
      && rm -rf /var/lib/apt/lists/*

# Éphémérides (Swisseph) copiées avant l'install
COPY ephe/ /app/ephe/

WORKDIR /app

# Dépendances Python
COPY requirements.txt .
RUN pip install --no-cache-dir --upgrade pip && \
    pip install --no-cache-dir -r requirements.txt && \
    # 🧹 purge des outils de build (image plus légère)
    apt-get purge -y build-essential gcc pkg-config libffi-dev python3-dev && \
    apt-get autoremove -y && \
    rm -rf /var/lib/apt/lists/*

# Code de l'app
COPY . .

EXPOSE 8080

# Lancement prod
CMD ["gunicorn", "--bind", "0.0.0.0:8080", "main:app"]
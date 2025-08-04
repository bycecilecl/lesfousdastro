FROM python:3.10-slim

# Installation des dépendances pour WeasyPrint et pyswisseph en une seule fois
RUN apt-get update && apt-get install -y \
    build-essential \
    curl \
    wget \
    unzip \
    python3-weasyprint \
    python3-cffi \
    python3-brotli \
    libpango-1.0-0 \
    libharfbuzz0b \
    libpangoft2-1.0-0 \
    libgdk-pixbuf2.0-0 \
    libfontconfig1 \
    && apt-get clean && rm -rf /var/lib/apt/lists/*

WORKDIR /app

COPY requirements.txt .
RUN pip install --upgrade pip

# Installer les dépendances Python
RUN pip install -r requirements.txt

COPY . .

EXPOSE 8080

CMD ["gunicorn", "--bind", "0.0.0.0:8080", "main:app"]
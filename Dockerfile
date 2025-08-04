FROM python:3.10-slim

# Dépendances système pour WeasyPrint
RUN apt-get update && apt-get install -y \
    build-essential \
    libcairo2-dev \
    libpango1.0-dev \
    libpangocairo-1.0-0 \
    libgdk-pixbuf2.0-dev \
    libffi-dev \
    libxml2-dev \
    libxslt1-dev \
    libjpeg-dev \
    libfontconfig1-dev \
    libglib2.0-0 \
    libglib2.0-dev \
    libgobject-2.0-0 \
    libgirepository-1.0-1 \
    pkg-config \
    curl \
    wget \
    unzip \
 && apt-get clean && rm -rf /var/lib/apt/lists/*

WORKDIR /app

COPY requirements.txt .
RUN pip install --upgrade pip
RUN pip install -r requirements.txt

COPY . .

EXPOSE 8080

CMD ["gunicorn", "--bind", "0.0.0.0:8080", "main:app"]
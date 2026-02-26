FROM python:3.12-slim

WORKDIR /app

# System dependencies for PyMuPDF, pytesseract, etc.
RUN apt-get update && apt-get install -y \
    build-essential \
    tesseract-ocr \
    libtesseract-dev \
    gcc \
    libreoffice-core \
    libreoffice-writer \
    libreoffice-impress \
    libreoffice-common \
    fonts-liberation \
    && rm -rf /var/lib/apt/lists/*

COPY requirements.txt .

RUN pip install --no-cache-dir -r requirements.txt

# Copy backend source code
COPY . /app/backend

# The main.py is in backend.main
EXPOSE 8000

ENV PYTHONPATH=/app

CMD ["uvicorn", "backend.main:app", "--host", "0.0.0.0", "--port", "8000", "--proxy-headers"]

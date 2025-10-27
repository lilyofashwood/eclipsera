FROM python:3.11-slim

ARG DEBIAN_FRONTEND=noninteractive
# System tools used by analyzers (binwalk, exiftool, foremost, steghide, outguess, zsteg) + deps
RUN apt-get update && apt-get install -y --no-install-recommends \
    file \
    binwalk \
    exiftool \
    foremost \
    steghide \
    outguess \
    ruby-full \
    build-essential \
    p7zip-full \
    unrar-free \
    ca-certificates \
    git \
 && gem install --no-document zsteg \
 && rm -rf /var/lib/apt/lists/*

WORKDIR /app

# Python deps
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# App source
COPY . .

# Ensure required vendor stub exists before integrity check
RUN mkdir -p vendor/decoder && [ -f vendor/decoder/.env ] || touch vendor/decoder/.env

ENV PYTHONPATH=/app
ENV PORT=8501

# Keep this strict; it should pass now that .env exists and tools are present
RUN scripts/check_vendor_integrity.py

EXPOSE 8501

# Streamlit entry
CMD ["sh","-c","streamlit run app/main.py --server.port=${PORT:-8501} --server.address=0.0.0.0"]

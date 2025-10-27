FROM python:3.11-slim

ENV PYTHONUNBUFFERED=1 \
    PIP_NO_CACHE_DIR=1 \
    PYTHONPATH=/app \
    PORT=8501 \
    STREAMLIT_SERVER_HEADLESS=true \
    STREAMLIT_BROWSER_GATHER_USAGE_STATS=false

WORKDIR /app

COPY requirements-system.txt ./
RUN apt-get update \
    && xargs -r -a requirements-system.txt apt-get install -y --no-install-recommends \
    && gem install zsteg \
    && apt-get clean \
    && rm -rf /var/lib/apt/lists/*

COPY requirements.txt ./
RUN pip install --no-cache-dir -r requirements.txt

COPY . .

RUN scripts/check_vendor_integrity.py

EXPOSE 8501
CMD ["/bin/sh","-c","streamlit run app/main.py --server.port ${PORT:-8501} --server.address 0.0.0.0"]

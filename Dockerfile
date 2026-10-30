# Painel de automações Playwright num container (servidor da empresa). Ver README, seção "No servidor (Docker)".
# A versão da imagem é a mesma do playwright no requirements.txt.
FROM mcr.microsoft.com/playwright/python:v1.61.0-noble

ENV DEBIAN_FRONTEND=noninteractive \
    PYTHONUNBUFFERED=1 \
    PYTHONDONTWRITEBYTECODE=1 \
    TZ=America/Sao_Paulo \
    HEADLESS=1

WORKDIR /app
COPY requirements.txt .
RUN pip install --no-cache-dir --break-system-packages -r requirements.txt

# Google Chrome (o painel usa channel="chrome"; a imagem só traz o Chromium) e fusos horários (TZ)
RUN apt-get update \
    && apt-get install -y --no-install-recommends tzdata \
    && playwright install --with-deps chrome \
    && rm -rf /var/lib/apt/lists/*

COPY . .

EXPOSE 8082
# Um processo só: as execuções ficam na memória dele (com mais de um, o /status não acharia a execução).
CMD ["waitress-serve", "--host=0.0.0.0", "--port=8082", "--threads=16", "app:app"]

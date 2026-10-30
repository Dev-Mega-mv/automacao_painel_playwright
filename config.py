"""Configuração do painel Playwright: porta, portal, navegador e pastas.

Os valores podem ser trocados por variáveis de ambiente, sem mexer no código.
Exemplo no PowerShell:  $env:PORTA = "8090"; python app.py
"""
import os
import secrets
from pathlib import Path

BASE_DIR = Path(__file__).resolve().parent

PASTA_PERFIS = BASE_DIR / "perfis"          # perfis do Chrome (guardam o login entre execuções)
PASTA_LOGS = BASE_DIR / "logs"              # um log por execução + capturas de erro + traces
PASTA_RELATORIOS = BASE_DIR / "relatorios"  # planilhas geradas

# Painel
HOST = os.getenv("HOST", "0.0.0.0")
PORTA = int(os.getenv("PORTA", "8082"))
DEBUG = os.getenv("FLASK_DEBUG", "0") == "1"  # com debug o Flask reinicia ao salvar um .py e derruba a automação em andamento
SECRET_KEY = os.getenv("SECRET_KEY") or secrets.token_hex(16)

# Portal Infox
URL_PORTAL = os.getenv("URL_PORTAL", "https://online.fwcard.com.br/fwcard/")
URL_LOGIN = URL_PORTAL + "f?p=380:100:"

# Painel administrativo da Megavale (criação de acesso dos credenciados)
URL_MEGAVALE = os.getenv("URL_MEGAVALE", "https://app.megavalecard.com.br/")

# Navegador (Playwright)
HEADLESS = os.getenv("HEADLESS", "0") == "1"
# Largura,altura da janela do Chrome. Vazio = maximizada; sem janela (servidor) não há tela para maximizar.
TAMANHO_JANELA = os.getenv("TAMANHO_JANELA", "1600,1000" if HEADLESS else "")
TIMEOUT_PADRAO_MS = int(os.getenv("TIMEOUT_PADRAO_MS", "15000"))
ESPERA_CAPTCHA_S = int(os.getenv("ESPERA_CAPTCHA_S", "120"))
SALVAR_TRACE = os.getenv("SALVAR_TRACE", "erro")  # "sempre" | "erro" | "nunca"

# Execuções
EXECUCOES_SIMULTANEAS = int(os.getenv("EXECUCOES_SIMULTANEAS", "3"))  # cada Chrome usa de 300 a 500 MB de memória

for _pasta in (PASTA_PERFIS, PASTA_LOGS, PASTA_RELATORIOS):
    _pasta.mkdir(exist_ok=True)

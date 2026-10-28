"""Painel de automações Playwright (porta 8082).

Só tem as telas já migradas. As demais continuam no painel Selenium (automacao_painel, porta 8081).
"""
from flask import Flask

import config
from rotas import registrar_rotas


def criar_app() -> Flask:
    app = Flask(__name__)
    app.secret_key = config.SECRET_KEY
    registrar_rotas(app)
    return app


app = criar_app()

if __name__ == "__main__":
    print(f"Painel Playwright em http://localhost:{config.PORTA}")
    app.run(host=config.HOST, port=config.PORTA, debug=config.DEBUG)


"""Rotas do painel, uma blueprint por funcionalidade.

Para migrar uma nova tela: crie rotas/<funcionalidade>.py com uma blueprint,
registre-a em BLUEPRINTS e acrescente o link no menu (templates/_menu.html) e o cartão na tela inicial.
"""
from flask import Flask

from .acesso import bp as acesso_bp
from .coleta import bp as coleta_bp
from .conciliacao import bp as conciliacao_bp
from .execucao import bp as execucao_bp
from .extrator import bp as extrator_bp
from .habilitacao import bp as habilitacao_bp
from .inicio import bp as inicio_bp
from .taxa import bp as taxa_bp

BLUEPRINTS = (inicio_bp, habilitacao_bp, extrator_bp, coleta_bp, conciliacao_bp, taxa_bp, acesso_bp, execucao_bp)


def registrar_rotas(app: Flask):
    for blueprint in BLUEPRINTS:
        app.register_blueprint(blueprint)

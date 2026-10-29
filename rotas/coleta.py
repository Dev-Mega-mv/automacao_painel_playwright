"""Tela da coleta de código de estabelecimento: de um credenciado ou de uma planilha."""
import io

from flask import Blueprint, flash, redirect, render_template, request, send_file, url_for

from automacoes.coleta import ColetaEstabelecimento, gerar_modelo
from automacoes.core.planilha import ler_codigos
from automacoes.core.texto import normalizar_codigo_pesquisa

from .execucao import iniciar_e_acompanhar
from .upload import origem_da_planilha, planilha_enviada

bp = Blueprint("coleta", __name__)

ENTRADAS = ("unico", "planilha")   # de onde vêm os credenciados: o campo da tela ou uma planilha
ORIGEM_PADRAO = "CARDSE"


def _entrada(valor) -> str:
    return valor if valor in ENTRADAS else ENTRADAS[0]


def _voltar(entrada: str):
    return redirect(url_for("coleta.coleta", entrada=entrada))


@bp.route("/coleta-codigo-estabelecimento")
def endereco_antigo():
    """Endereço da tela no painel Selenium, que só aceitava planilha."""
    return _voltar("planilha")


@bp.route("/coleta/modelo-planilha")
def modelo_planilha():
    """Planilha em branco com a coluna COD, para o usuário só preencher."""
    return send_file(
        io.BytesIO(gerar_modelo()),
        as_attachment=True,
        download_name="modelo_coleta.xlsx",
        mimetype="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
    )


@bp.route("/coleta", methods=["GET", "POST"])
def coleta():
    if request.method == "GET":
        return render_template("coleta.html", entrada=_entrada(request.args.get("entrada")), origem=ORIGEM_PADRAO)

    form = request.form
    entrada = _entrada(form.get("entrada"))
    login = form.get("login_infox", "").strip()
    senha = form.get("senha_infox", "").strip()
    tipo_pesquisa = form.get("tipo_pesquisa", "COD").strip().upper()
    cod_cnpj = form.get("cod_cnpj", "").strip()
    origem = form.get("origem_transacao", "").strip()

    if entrada == "unico" and not cod_cnpj:
        flash("Informe o código ou CNPJ.")
        return _voltar(entrada)
    if not login or not senha:
        flash("Login e senha são obrigatórios.")
        return _voltar(entrada)
    if not origem:
        flash("Informe a origem da transação que deseja coletar (ex.: CARDSE).")
        return _voltar(entrada)

    try:
        if entrada == "planilha":
            conteudo, nome = planilha_enviada(request.files.get("file"))
            leitura = ler_codigos(conteudo, tipo_pesquisa)
            codigos = leitura.codigos
            origem_itens = origem_da_planilha(nome, len(codigos), leitura.linhas_sem_codigo)
        else:
            codigos, origem_itens = [normalizar_codigo_pesquisa(cod_cnpj, tipo_pesquisa)], None
    except ValueError as erro:  # inclui PlanilhaInvalida
        flash(str(erro))
        return _voltar(entrada)

    def criar_automacao(status):
        if origem_itens:
            status.log(origem_itens)
        return ColetaEstabelecimento({"login_infox": login, "senha_infox": senha}, codigos, status,
                                     origem=origem, tipo_pesquisa=tipo_pesquisa)

    return iniciar_e_acompanhar("coleta", criar_automacao)

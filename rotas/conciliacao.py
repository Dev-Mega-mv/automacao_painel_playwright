"""Tela da alteração de conciliação EDI: de um credenciado ou de uma planilha."""
import io

from flask import Blueprint, flash, redirect, render_template, request, send_file, url_for

from automacoes.conciliacao import CONCILIACOES, Conciliacao, gerar_modelo
from automacoes.core import execucao
from automacoes.core.planilha import ler_codigos
from automacoes.core.texto import normalizar_codigo_pesquisa

from .upload import origem_da_planilha, planilha_enviada

bp = Blueprint("conciliacao", __name__)

ENTRADAS = ("unico", "planilha")   # de onde vêm os credenciados: o campo da tela ou uma planilha


def _entrada(valor) -> str:
    return valor if valor in ENTRADAS else ENTRADAS[0]


def _voltar(entrada: str):
    return redirect(url_for("conciliacao.conciliacao", entrada=entrada))


@bp.route("/alt-conciliacao")
def endereco_antigo():
    """Endereço da tela no painel Selenium, que só aceitava planilha."""
    return _voltar("planilha")


@bp.route("/conciliacao/modelo-planilha")
def modelo_planilha():
    """Planilha em branco com a coluna COD, para o usuário só preencher."""
    return send_file(
        io.BytesIO(gerar_modelo()),
        as_attachment=True,
        download_name="modelo_conciliacao.xlsx",
        mimetype="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
    )


@bp.route("/conciliacao", methods=["GET", "POST"])
def conciliacao():
    if request.method == "GET":
        return render_template("conciliacao.html", entrada=_entrada(request.args.get("entrada")),
                               conciliacoes=CONCILIACOES)

    form = request.form
    entrada = _entrada(form.get("entrada"))
    login = form.get("login_infox", "").strip()
    senha = form.get("senha_infox", "").strip()
    tipo_pesquisa = form.get("tipo_pesquisa", "COD").strip().upper()
    cod_cnpj = form.get("cod_cnpj", "").strip()
    nome_conciliacao = form.get("nome_conciliacao", "").strip()

    if entrada == "unico" and not cod_cnpj:
        flash("Informe o código ou CNPJ.")
        return _voltar(entrada)
    if not login or not senha:
        flash("Login e senha são obrigatórios.")
        return _voltar(entrada)
    if nome_conciliacao not in CONCILIACOES:
        flash("Escolha a conciliação na lista.")
        return _voltar(entrada)

    try:
        if entrada == "planilha":
            conteudo, nome = planilha_enviada(request.files.get("file"))
            leitura = ler_codigos(conteudo, tipo_pesquisa)
            codigos = leitura.codigos
            origem = origem_da_planilha(nome, len(codigos), leitura.linhas_sem_codigo)
        else:
            codigos, origem = [normalizar_codigo_pesquisa(cod_cnpj, tipo_pesquisa)], None
    except ValueError as erro:  # inclui PlanilhaInvalida
        flash(str(erro))
        return _voltar(entrada)

    def criar_automacao(status):
        if origem:
            status.log(origem)
        return Conciliacao({"login_infox": login, "senha_infox": senha}, codigos, status,
                           conciliacao=nome_conciliacao, tipo_pesquisa=tipo_pesquisa)

    if execucao.iniciar("conciliacao", criar_automacao) is None:
        flash("Já existe uma automação em execução. Aguarde finalizar ou peça para parar antes de iniciar outra.")
    return redirect(url_for("execucao.status"))

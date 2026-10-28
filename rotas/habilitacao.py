"""Tela do ativador CIELO/CARDSE: um credenciado digitado ou vários por planilha, com ativação ou só verificação."""
import io

from flask import Blueprint, flash, redirect, render_template, request, send_file, url_for

from automacoes.core import execucao
from automacoes.core.texto import normalizar_codigo_pesquisa
from automacoes.habilitacao import Habilitacao, ItemHabilitacao, gerar_modelo, ler_itens

from .upload import origem_da_planilha, planilha_enviada

bp = Blueprint("habilitacao", __name__)

ENTRADAS = ("unico", "planilha")  # de onde vêm os credenciados: o campo da tela ou uma planilha


def _inteiro(valor, padrao: int) -> int:
    try:
        return int(str(valor).strip())
    except (TypeError, ValueError):
        return padrao


def _acao(valor) -> str:
    valor = str(valor or "").strip().upper()
    return valor if valor in ("ATIVAR", "DESATIVAR") else "ATIVAR"


def _entrada(valor) -> str:
    return valor if valor in ENTRADAS else "unico"


def _voltar(entrada: str):
    return redirect(url_for("habilitacao.ativador", entrada=entrada))


def _itens_da_planilha(arquivo, tipo_pesquisa: str, padrao: dict) -> tuple[list[ItemHabilitacao], str]:
    """Lê a planilha enviada. Devolve os itens e a linha de log que diz de onde eles vieram."""
    conteudo, nome = planilha_enviada(arquivo)
    leitura = ler_itens(conteudo, tipo_pesquisa, padrao)
    return leitura.itens, origem_da_planilha(nome, len(leitura.itens), leitura.linhas_sem_codigo)


@bp.route("/individual")
@bp.route("/lote")
def endereco_antigo():
    """Individual e Lote viraram uma tela só; os endereços antigos abrem a tela nova."""
    return _voltar("planilha" if request.path == "/lote" else "unico")


@bp.route("/ativador/modelo-planilha")
def modelo_planilha():
    """Planilha em branco, com as colunas e as listas de valores, para o usuário só preencher."""
    return send_file(
        io.BytesIO(gerar_modelo()),
        as_attachment=True,
        download_name="modelo_ativador.xlsx",
        mimetype="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
    )


@bp.route("/ativador", methods=["GET", "POST"])
def ativador():
    if request.method == "GET":
        return render_template("ativador.html", entrada=_entrada(request.args.get("entrada")))

    form = request.form
    entrada = _entrada(form.get("entrada"))
    login = form.get("login_infox", "").strip()
    senha = form.get("senha_infox", "").strip()
    tipo_pesquisa = form.get("tipo_pesquisa", "COD").strip().upper()
    cod_cnpj = form.get("cod_cnpj", "").strip()
    # Com planilha, estes valores só valem para as linhas que deixarem a coluna vazia.
    padrao = {
        "tecnologia": form.get("tecnologia", "CIELO").strip().upper(),
        "acao_cielo": _acao(form.get("acao_cielo")),
        "acao_cardse": _acao(form.get("acao_cardse")),
        "produto_unico": form.get("produto_unico", "").strip(),
    }

    if entrada == "unico" and not cod_cnpj:
        flash("Informe o código ou CNPJ.")
        return _voltar(entrada)
    if not login or not senha:
        flash("Login e senha são obrigatórios.")
        return _voltar(entrada)

    try:
        if entrada == "planilha":
            itens, origem = _itens_da_planilha(request.files.get("file"), tipo_pesquisa, padrao)
        else:
            itens = [ItemHabilitacao(codigo=normalizar_codigo_pesquisa(cod_cnpj, tipo_pesquisa), **padrao)]
            origem = None
    except ValueError as erro:  # inclui PlanilhaInvalida
        flash(str(erro))
        return _voltar(entrada)

    def criar_automacao(status):
        if origem:
            status.log(origem)
        return Habilitacao(
            {"login_infox": login, "senha_infox": senha}, itens, status,
            tipo_pesquisa=tipo_pesquisa,
            modo_verificacao=form.get("modo_verificacao") == "1",
            produto_inicio=_inteiro(form.get("produto_inicio"), 1),
            cardse_statuses=form.getlist("cardse_statuses"),
        )

    if execucao.iniciar("habilitacao", criar_automacao) is None:
        flash("Já existe uma automação em execução. Aguarde finalizar ou peça para parar antes de iniciar outra.")
    return redirect(url_for("execucao.status"))

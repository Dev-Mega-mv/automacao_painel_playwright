"""Tela da alteração de taxas (plano de compra dos contratos): de um credenciado ou de uma planilha."""
import io

from flask import Blueprint, flash, redirect, render_template, request, send_file, url_for

from automacoes.core.texto import normalizar_codigo_pesquisa
from automacoes.taxa import (BANCARIZAR, DIAS_SEMANA, LIMITE_ERROS_SEGUIDOS, PERIODICIDADES, TIPOS_DIA,
                             AlteracaoTaxa, ItemTaxa, gerar_modelo, ler_itens)

from .execucao import iniciar_e_acompanhar
from .upload import origem_da_planilha, planilha_enviada

bp = Blueprint("taxa", __name__)

ENTRADAS = ("unico", "planilha")   # de onde vêm os credenciados: o campo da tela ou uma planilha


def _entrada(valor) -> str:
    return valor if valor in ENTRADAS else ENTRADAS[0]


def _voltar(entrada: str):
    return redirect(url_for("taxa.taxas", entrada=entrada))


def _plano_da_tela(form) -> dict:
    """Plano pedido na tela. Com planilha, vale para as células vazias."""
    return {
        "taxa": form.get("taxa", "").strip(),
        "periodicidade": form.get("periodicidade", "MENSAL").strip(),
        "pag_dias": form.get("pag_dias", "").strip(),
        "dia1": form.get("dia1", "").strip(),
        "dia2": form.get("dia2", "").strip(),
        "dias_semana": form.getlist("dias_semana"),
        "bancarizar": form.get("bancarizar", "NÃO").strip(),
        "tipo_dia": form.get("tipo_dia", "INDIFERENTE").strip(),
    }


@bp.route("/alt-taxa")
def endereco_antigo():
    """Endereço da tela no painel Selenium."""
    return _voltar("unico")


@bp.route("/taxas/modelo-planilha")
def modelo_planilha():
    """Planilha em branco, com as colunas e as listas de valores, para o usuário só preencher."""
    return send_file(
        io.BytesIO(gerar_modelo()),
        as_attachment=True,
        download_name="modelo_taxas.xlsx",
        mimetype="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
    )


@bp.route("/taxas", methods=["GET", "POST"])
def taxas():
    if request.method == "GET":
        return render_template(
            "taxas.html", entrada=_entrada(request.args.get("entrada")), periodicidades=PERIODICIDADES,
            dias_semana=DIAS_SEMANA, tipos_dia=TIPOS_DIA, bancarizar=BANCARIZAR, limite_erros=LIMITE_ERROS_SEGUIDOS,
        )

    form = request.form
    entrada = _entrada(form.get("entrada"))
    login = form.get("login_infox", "").strip()
    senha = form.get("senha_infox", "").strip()
    tipo_pesquisa = form.get("tipo_pesquisa", "COD").strip().upper()
    cod_cnpj = form.get("cod_cnpj", "").strip()
    padrao = _plano_da_tela(form)

    if entrada == "unico" and not cod_cnpj:
        flash("Informe o código ou CNPJ.")
        return _voltar(entrada)
    if not login or not senha:
        flash("Login e senha são obrigatórios.")
        return _voltar(entrada)

    try:
        ItemTaxa(codigo="tela", **padrao)  # confere os valores da tela antes de ler a planilha
        if entrada == "planilha":
            conteudo, nome = planilha_enviada(request.files.get("file"))
            leitura = ler_itens(conteudo, tipo_pesquisa, padrao)
            itens = leitura.itens
            origem = origem_da_planilha(nome, len(itens), leitura.linhas_sem_codigo)
        else:
            itens, origem = [ItemTaxa(codigo=normalizar_codigo_pesquisa(cod_cnpj, tipo_pesquisa), **padrao)], None
    except ValueError as erro:  # inclui PlanilhaInvalida
        flash(str(erro))
        return _voltar(entrada)

    def criar_automacao(status):
        if origem:
            status.log(origem)
        return AlteracaoTaxa({"login_infox": login, "senha_infox": senha}, itens, status, tipo_pesquisa=tipo_pesquisa)

    return iniciar_e_acompanhar("taxa", criar_automacao)

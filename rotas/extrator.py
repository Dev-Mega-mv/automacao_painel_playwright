"""Tela do extrator de dados: cadastro dos credenciados ou consulta de transações, de um credenciado ou de uma planilha."""
import io
from datetime import date

from flask import Blueprint, flash, redirect, render_template, request, send_file, url_for

from automacoes.core import execucao
from automacoes.core.planilha import ler_codigos
from automacoes.core.texto import normalizar_codigo_pesquisa
from automacoes.extrator import FUNCIONALIDADES, ExtratorCadastro, ExtratorTransacoes, gerar_modelo

from .upload import origem_da_planilha, planilha_enviada

bp = Blueprint("extrator", __name__)

ENTRADAS = ("unico", "planilha")     # de onde vêm os credenciados: o campo da tela ou uma planilha
MODOS = ("cadastro", "transacoes")   # o que extrair


def _escolha(valor, opcoes: tuple[str, ...]) -> str:
    return valor if valor in opcoes else opcoes[0]


def _voltar(entrada: str, modo: str):
    return redirect(url_for("extrator.extrator", entrada=entrada, modo=modo))


def _periodo(form) -> tuple[str, str]:
    """Datas do formulário (AAAA-MM-DD, do campo de data do navegador) no formato do portal (DD/MM/AAAA)."""
    datas = []
    for campo, nome in (("data_inicial", "data inicial"), ("data_final", "data final")):
        try:
            datas.append(date.fromisoformat(form.get(campo, "").strip()))
        except ValueError:
            raise ValueError(f"Informe a {nome} da consulta de transações.")
    inicial, final = datas
    if inicial > final:
        raise ValueError("A data inicial é depois da data final.")
    return f"{inicial:%d/%m/%Y}", f"{final:%d/%m/%Y}"


@bp.route("/extrator/modelo-planilha")
def modelo_planilha():
    """Planilha em branco com a coluna COD, para o usuário só preencher."""
    return send_file(
        io.BytesIO(gerar_modelo()),
        as_attachment=True,
        download_name="modelo_extrator.xlsx",
        mimetype="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
    )


@bp.route("/extrator", methods=["GET", "POST"])
def extrator():
    if request.method == "GET":
        return render_template(
            "extrator.html",
            entrada=_escolha(request.args.get("entrada"), ENTRADAS),
            modo=_escolha(request.args.get("modo"), MODOS),
        )

    form = request.form
    entrada = _escolha(form.get("entrada"), ENTRADAS)
    modo = _escolha(form.get("modo"), MODOS)
    login = form.get("login_infox", "").strip()
    senha = form.get("senha_infox", "").strip()
    tipo_pesquisa = form.get("tipo_pesquisa", "COD").strip().upper()
    cod_cnpj = form.get("cod_cnpj", "").strip()
    funcionalidade = form.get("funcionalidade_transacao", "valor_venda_total")

    if entrada == "unico" and not cod_cnpj:
        flash("Informe o código ou CNPJ.")
        return _voltar(entrada, modo)
    if not login or not senha:
        flash("Login e senha são obrigatórios.")
        return _voltar(entrada, modo)

    data_inicial = data_final = ""
    try:
        if modo == "transacoes":
            if funcionalidade not in FUNCIONALIDADES:
                raise ValueError("Escolha o que consultar nas transações.")
            data_inicial, data_final = _periodo(form)
        if entrada == "planilha":
            conteudo, nome = planilha_enviada(request.files.get("file"))
            leitura = ler_codigos(conteudo, tipo_pesquisa)
            codigos = leitura.codigos
            origem = origem_da_planilha(nome, len(codigos), leitura.linhas_sem_codigo)
        else:
            codigos, origem = [normalizar_codigo_pesquisa(cod_cnpj, tipo_pesquisa)], None
    except ValueError as erro:  # inclui PlanilhaInvalida
        flash(str(erro))
        return _voltar(entrada, modo)

    def criar_automacao(status):
        if origem:
            status.log(origem)
        credenciais = {"login_infox": login, "senha_infox": senha}
        if modo == "transacoes":
            return ExtratorTransacoes(
                credenciais, codigos, status, funcionalidade=funcionalidade,
                data_inicial=data_inicial, data_final=data_final, tipo_pesquisa=tipo_pesquisa,
            )
        return ExtratorCadastro(credenciais, codigos, status, tipo_pesquisa=tipo_pesquisa)

    if execucao.iniciar("extrator", criar_automacao) is None:
        flash("Já existe uma automação em execução. Aguarde finalizar ou peça para parar antes de iniciar outra.")
    return redirect(url_for("execucao.status"))

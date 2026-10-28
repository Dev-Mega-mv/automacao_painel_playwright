"""Tela da criação de acesso: credenciados da Infox cadastrados no painel Megavale (ou só conferidos)."""
import io

from flask import Blueprint, flash, redirect, render_template, request, send_file, url_for

from automacoes.acesso import CriacaoAcesso, gerar_modelo
from automacoes.core import execucao
from automacoes.core.planilha import ler_codigos
from automacoes.core.texto import normalizar_codigo_pesquisa

from .upload import origem_da_planilha, planilha_enviada

bp = Blueprint("acesso", __name__)

ENTRADAS = ("unico", "planilha")   # de onde vêm os credenciados: o campo da tela ou uma planilha
MODOS = ("criar", "verificar")     # criar o que faltar no painel, ou só conferir


def _escolha(valor, opcoes: tuple[str, ...]) -> str:
    return valor if valor in opcoes else opcoes[0]


def _voltar(entrada: str, modo: str):
    return redirect(url_for("acesso.acessos", entrada=entrada, modo=modo))


@bp.route("/acessos/modelo-planilha")
def modelo_planilha():
    """Planilha em branco com a coluna COD, para o usuário só preencher."""
    return send_file(
        io.BytesIO(gerar_modelo()),
        as_attachment=True,
        download_name="modelo_criacao_acesso.xlsx",
        mimetype="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
    )


@bp.route("/acessos", methods=["GET", "POST"])
def acessos():
    if request.method == "GET":
        return render_template(
            "acessos.html",
            entrada=_escolha(request.args.get("entrada"), ENTRADAS),
            modo=_escolha(request.args.get("modo"), MODOS),
        )

    form = request.form
    entrada = _escolha(form.get("entrada"), ENTRADAS)
    modo = _escolha(form.get("modo"), MODOS)
    credenciais = {campo: form.get(campo, "").strip()
                   for campo in ("login_infox", "senha_infox", "login_megavale", "senha_megavale")}
    tipo_pesquisa = form.get("tipo_pesquisa", "COD").strip().upper()
    cod_cnpj = form.get("cod_cnpj", "").strip()

    if entrada == "unico" and not cod_cnpj:
        flash("Informe o código ou CNPJ.")
        return _voltar(entrada, modo)
    if not credenciais["login_infox"] or not credenciais["senha_infox"]:
        flash("Login e senha da Infox são obrigatórios.")
        return _voltar(entrada, modo)
    if not credenciais["login_megavale"] or not credenciais["senha_megavale"]:
        flash("Login e senha do painel Megavale são obrigatórios.")
        return _voltar(entrada, modo)

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
        return _voltar(entrada, modo)

    def criar_automacao(status):
        if origem:
            status.log(origem)
        return CriacaoAcesso(credenciais, codigos, status, tipo_pesquisa=tipo_pesquisa,
                             somente_verificar=modo == "verificar")

    if execucao.iniciar("criacao_acesso", criar_automacao) is None:
        flash("Já existe uma automação em execução. Aguarde finalizar ou peça para parar antes de iniciar outra.")
    return redirect(url_for("execucao.status"))

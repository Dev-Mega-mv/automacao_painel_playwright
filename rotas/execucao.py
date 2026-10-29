"""Acompanhamento das execuções: a lista, o status de cada uma, parar e baixar o relatório."""
import os

from flask import Blueprint, flash, jsonify, redirect, render_template, send_file, url_for

import config
from automacoes.core import execucao
from automacoes.core.status_execucao import StatusExecucao

bp = Blueprint("execucao", __name__)


def iniciar_e_acompanhar(nome: str, criar_automacao):
    """Começa a automação e abre o status dela. As telas chamam isto depois de validar o formulário."""
    status = execucao.iniciar(nome, criar_automacao)
    if status is None:
        flash(
            f"Já há {config.EXECUCOES_SIMULTANEAS} automações em execução, o limite do painel. "
            "Aguarde uma terminar ou peça para parar antes de iniciar outra."
        )
        return redirect(url_for("execucao.status"))
    return redirect(url_for("execucao.detalhe", id_execucao=status.id))


def _progresso(st: dict) -> int:
    total = max(1, st["total"])
    return int(min(st["processed"], total) / total * 100)


def _relatorio_existente(status: dict) -> str | None:
    caminho = status.get("relatorio_path")
    if caminho and os.path.isfile(caminho):
        return os.path.abspath(caminho)
    return None


def _resumo(status: StatusExecucao) -> dict:
    """Uma linha da lista de execuções."""
    st = status.como_dict()
    return {
        "id": status.id,
        "titulo": status.titulo,
        "inicio": f"{st['start_time']:%d/%m %H:%M:%S}" if st["start_time"] else "",
        "duracao": status.duracao(),
        "running": st["running"],
        "request_stop": st["request_stop"],
        "total": st["total"],
        "processed": st["processed"],
        "progress": _progresso(st),
        "current_item": st["current_item"],
        "tem_relatorio": _relatorio_existente(st) is not None,
        "url": url_for("execucao.detalhe", id_execucao=status.id),
    }


@bp.route("/status")
def status():
    """Todas as execuções desde que o painel abriu (as encerradas mais antigas vão saindo da lista)."""
    return render_template("execucoes.html", limite=config.EXECUCOES_SIMULTANEAS)


@bp.route("/status/<id_execucao>")
def detalhe(id_execucao):
    status = execucao.buscar(id_execucao)
    if status is None:
        flash("Execução não encontrada. Se o painel foi reiniciado, o log dela continua na pasta logs/.")
        return redirect(url_for("execucao.status"))
    return render_template("status.html", execucao=_resumo(status))


@bp.route("/api/status")
def api_status():
    """Resumo de todas as execuções, da mais recente para a mais antiga (lista de execuções e tela inicial)."""
    execucoes = [_resumo(status) for status in execucao.todas()]
    return jsonify({
        "em_execucao": sum(item["running"] for item in execucoes),
        "limite": config.EXECUCOES_SIMULTANEAS,
        "execucoes": execucoes,
    })


@bp.route("/api/status/<id_execucao>")
def api_status_execucao(id_execucao):
    """Formato consumido por templates/status.html (o mesmo do painel Selenium, mais o título)."""
    status = execucao.buscar(id_execucao)
    if status is None:
        return jsonify({"erro": "Execução não encontrada."}), 404
    st = status.como_dict()
    return jsonify({
        "running": st["running"],
        "total": st["total"],
        "processed": st["processed"],
        "current_item": st["current_item"],
        "logs": st["logs"],
        "progress": _progresso(st),
        "tem_relatorio": _relatorio_existente(st) is not None,
        "automacao": status.nome,
        "titulo": status.titulo,
    })


@bp.route("/download_relatorio/<id_execucao>")
def download_relatorio(id_execucao):
    status = execucao.buscar(id_execucao)
    if status is None:
        flash("Execução não encontrada. Se o painel foi reiniciado, o relatório continua na pasta relatorios/.")
        return redirect(url_for("execucao.status"))
    caminho = _relatorio_existente(status.como_dict())
    if not caminho:
        flash("Nenhum relatório disponível.")
        return redirect(url_for("execucao.detalhe", id_execucao=id_execucao))
    return send_file(
        caminho,
        as_attachment=True,
        download_name=os.path.basename(caminho),
        mimetype="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
        conditional=False,
    )


@bp.route("/stop/<id_execucao>")
def stop(id_execucao):
    status = execucao.buscar(id_execucao)
    if status is None:
        flash("Execução não encontrada.")
        return redirect(url_for("execucao.status"))
    if status.running:
        status.solicitar_parada()
        flash("Interrupção solicitada.")
    else:
        flash("Esta automação já terminou.")
    return redirect(url_for("execucao.detalhe", id_execucao=id_execucao))

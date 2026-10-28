"""Acompanhamento da execução atual: status, parar e baixar o relatório."""
import os

from flask import Blueprint, flash, jsonify, redirect, render_template, send_file, url_for

from automacoes.core import execucao

bp = Blueprint("execucao", __name__)

_SEM_EXECUCAO = {
    "running": False, "total": 0, "processed": 0, "current_item": None, "logs": [],
    "start_time": None, "end_time": None, "request_stop": False, "relatorio_path": None,
}


def status_atual() -> dict:
    atual = execucao.atual()
    return atual.como_dict() if atual else dict(_SEM_EXECUCAO)


def _relatorio_existente(status: dict) -> str | None:
    caminho = status.get("relatorio_path")
    if caminho and os.path.isfile(caminho):
        return os.path.abspath(caminho)
    return None


@bp.route("/status")
def status():
    return render_template("status.html", status=status_atual())


@bp.route("/api/status")
def api_status():
    """Formato consumido por templates/status.html (o mesmo do painel Selenium)."""
    st = status_atual()
    total = max(1, st["total"])
    atual = execucao.atual()
    return jsonify({
        "running": st["running"],
        "total": st["total"],
        "processed": st["processed"],
        "current_item": st["current_item"],
        "logs": st["logs"],
        "progress": int(min(st["processed"], total) / total * 100),
        "tem_relatorio": _relatorio_existente(st) is not None,
        "automacao": atual.nome if atual else "nenhuma",
    })


@bp.route("/download_relatorio")
def download_relatorio():
    caminho = _relatorio_existente(status_atual())
    if not caminho:
        flash("Nenhum relatório disponível.")
        return redirect(url_for("execucao.status"))
    return send_file(
        caminho,
        as_attachment=True,
        download_name=os.path.basename(caminho),
        mimetype="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
        conditional=False,
    )


@bp.route("/stop")
def stop():
    if execucao.em_execucao():
        execucao.atual().solicitar_parada()
        flash("Interrupção solicitada.")
    else:
        flash("Nenhuma automação em execução.")
    return redirect(url_for("execucao.status"))

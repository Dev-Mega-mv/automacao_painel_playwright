"""Registro da execução atual: garante uma automação Playwright por vez."""
import threading
import traceback
from datetime import datetime

import config

from .status_execucao import StatusExecucao

_trava = threading.Lock()
_atual: StatusExecucao | None = None


def atual() -> StatusExecucao | None:
    return _atual


def em_execucao() -> bool:
    return bool(_atual and _atual.running)


def iniciar(nome: str, criar_automacao) -> StatusExecucao | None:
    """Cria o status, marca como em execução e roda a automação numa thread.

    `criar_automacao` recebe o StatusExecucao e devolve a automação (com método executar()).
    Retorna None se já houver uma execução em andamento.
    """
    global _atual
    with _trava:
        if em_execucao():
            return None
        arquivo_log = config.PASTA_LOGS / f"{nome}_{datetime.now():%Y%m%d_%H%M%S}.txt"
        status = StatusExecucao(nome, arquivo_log=arquivo_log)
        status.reservar()
        _atual = status

    threading.Thread(
        target=_rodar, args=(criar_automacao, status), name=f"automacao-{nome}", daemon=True
    ).start()
    return status


def _rodar(criar_automacao, status: StatusExecucao):
    try:
        criar_automacao(status).executar()
    except Exception as erro:  # rede de segurança: executar() já trata os erros esperados
        status.log(f"Erro inesperado: {erro}", "ERROR")
        status.detalhe(traceback.format_exc())
    finally:
        if status.running:
            status.finalizar()

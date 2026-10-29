"""Registro das execuções: várias automações ao mesmo tempo, até config.EXECUCOES_SIMULTANEAS."""
import threading
import traceback
from datetime import datetime

import config

from .status_execucao import StatusExecucao

GUARDAR_ENCERRADAS = 20  # execuções já terminadas que continuam na tela de status (as mais recentes)

_trava = threading.Lock()
_execucoes: dict[str, StatusExecucao] = {}  # id -> status, na ordem em que começaram


def buscar(id_execucao: str) -> StatusExecucao | None:
    return _execucoes.get(id_execucao)


def todas() -> list[StatusExecucao]:
    """Da mais recente para a mais antiga."""
    with _trava:
        return list(reversed(_execucoes.values()))


def iniciar(nome: str, criar_automacao) -> StatusExecucao | None:
    """Cria o status, marca como em execução e roda a automação numa thread.

    `criar_automacao` recebe o StatusExecucao e devolve a automação (com método executar()).
    Retorna None se já houver config.EXECUCOES_SIMULTANEAS execuções em andamento.
    """
    with _trava:
        if sum(status.running for status in _execucoes.values()) >= config.EXECUCOES_SIMULTANEAS:
            return None
        carimbo = _novo_carimbo(nome)
        status = StatusExecucao(nome, arquivo_log=config.PASTA_LOGS / f"{nome}_{carimbo}.txt", carimbo=carimbo)
        status.reservar()
        _execucoes[status.id] = status
        _descartar_encerradas()

    threading.Thread(
        target=_rodar, args=(criar_automacao, status), name=f"automacao-{status.id}", daemon=True
    ).start()
    return status


def _novo_carimbo(nome: str) -> str:
    """Data e hora do início; com _2, _3... se outra do mesmo tipo começou no mesmo segundo.

    Vai no ID da execução e no nome do log, do relatório e das capturas, então não pode repetir.
    """
    base = f"{datetime.now():%Y%m%d_%H%M%S}"
    carimbo, numero = base, 1
    while f"{nome}_{carimbo}" in _execucoes:
        numero += 1
        carimbo = f"{base}_{numero}"
    return carimbo


def _descartar_encerradas():
    encerradas = [id_execucao for id_execucao, status in _execucoes.items() if not status.running]
    for id_execucao in encerradas[:-GUARDAR_ENCERRADAS]:
        del _execucoes[id_execucao]


def _rodar(criar_automacao, status: StatusExecucao):
    try:
        criar_automacao(status).executar()
    except Exception as erro:  # rede de segurança: executar() já trata os erros esperados
        status.log(f"Erro inesperado: {erro}", "ERROR")
        status.detalhe(traceback.format_exc())
    finally:
        if status.running:
            status.finalizar()

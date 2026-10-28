"""Erros esperados das automações.

A mensagem de cada um é mostrada como está na tela de status, então deve
explicar o que aconteceu e o que fazer.
"""
from playwright.sync_api import TimeoutError as PlaywrightTimeout


def resumo_do_erro(erro: Exception) -> str:
    """Uma linha legível para a tela de status (o traceback completo vai para o arquivo de log)."""
    texto = str(erro).strip() or erro.__class__.__name__
    primeira = texto.splitlines()[0][:200]
    if isinstance(erro, PlaywrightTimeout):
        return f"Tempo de espera excedido ({primeira})"
    return primeira


class ErroAutomacao(Exception):
    """Erro previsto, com mensagem pronta para o usuário."""


class LoginFalhou(ErroAutomacao):
    pass


class CredenciadoNaoEncontrado(ErroAutomacao):
    pass


class NavegadorFechado(ErroAutomacao):
    pass


class ExecucaoInterrompida(ErroAutomacao):
    pass

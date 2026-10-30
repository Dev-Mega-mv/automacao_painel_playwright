import threading
from pathlib import Path

from playwright.sync_api import sync_playwright

import config

_trava_perfis = threading.Lock()
_perfis_em_uso: set[str] = set()  # pastas de perfis/ abertas por um Chrome deste painel agora


class Navegador:
    """Chrome instalado na máquina, com perfil persistente por automação.

    Se outra execução da mesma automação já estiver com o perfil aberto (o Chrome não abre a
    mesma pasta duas vezes), usa perfis/<automação>_2, _3...

    Uso:
        with Navegador("habilitacao", status, prefixo="habilitacao_20261027_101500") as nav:
            nav.page.goto(...)

    Ao sair do bloco, salva o trace (conforme config.SALVAR_TRACE) e fecha o Chrome.
    """

    def __init__(self, perfil: str, status, prefixo: str):
        self.perfil = perfil
        self.status = status
        self.prefixo = prefixo
        self.houve_erro = False
        self._pasta_perfil = None
        self._playwright = None
        self._contexto = None
        self._trace_ativo = False
        self.page = None

    def __enter__(self):
        self.status.log("Abrindo o Chrome...")
        self._playwright = sync_playwright().start()
        self._pasta_perfil = _reservar_perfil(self.perfil)
        if self._pasta_perfil != self.perfil:
            self.status.log(f"Outra execução está com o perfil {self.perfil} aberto; usando perfis/{self._pasta_perfil}.")
        try:
            self._contexto = self._playwright.chromium.launch_persistent_context(
                str(config.PASTA_PERFIS / self._pasta_perfil),
                channel="chrome",
                headless=config.HEADLESS,
                no_viewport=True,
                args=[f"--window-size={config.TAMANHO_JANELA}" if config.TAMANHO_JANELA else "--start-maximized",
                      "--disable-blink-features=AutomationControlled"],
                ignore_default_args=["--enable-automation"],
            )
        except Exception:
            self._playwright.stop()
            self._liberar_perfil()
            raise

        self._contexto.set_default_timeout(config.TIMEOUT_PADRAO_MS)
        if config.SALVAR_TRACE != "nunca":
            self._contexto.tracing.start(screenshots=True, snapshots=True)
            self._trace_ativo = True
        self.page = self._contexto.pages[0] if self._contexto.pages else self._contexto.new_page()
        return self

    def __exit__(self, tipo_erro, erro, tb):
        self.fechar(houve_erro=self.houve_erro or tipo_erro is not None)
        return False

    @property
    def aberto(self) -> bool:
        return self.page is not None and not self.page.is_closed()

    def nova_aba(self):
        """Outra aba no mesmo Chrome (mesmo perfil e mesmo trace), para automações que usam dois sistemas."""
        aba = self._contexto.new_page()
        aba.set_default_timeout(config.TIMEOUT_PADRAO_MS)
        return aba

    def capturar_tela(self, sufixo: str, page=None) -> Path | None:
        """Salva um screenshot em logs/ e devolve o caminho (None se o Chrome ou a aba já fechou).

        Sem `page`, captura a aba principal.
        """
        page = page or self.page
        if not self.aberto or page.is_closed():
            return None
        caminho = config.PASTA_LOGS / f"{self.prefixo}_{_nome_seguro(sufixo)}.png"
        try:
            page.screenshot(path=caminho, full_page=True)
            return caminho
        except Exception:
            return None

    def fechar(self, houve_erro: bool):
        if self._contexto is not None:
            self._parar_trace(houve_erro)
            try:
                self._contexto.close()
            except Exception:
                pass
            self._contexto = None
            self.status.log("Chrome fechado.")
        if self._playwright is not None:
            self._playwright.stop()
            self._playwright = None
        self._liberar_perfil()

    def _liberar_perfil(self):
        if self._pasta_perfil is not None:
            with _trava_perfis:
                _perfis_em_uso.discard(self._pasta_perfil)
            self._pasta_perfil = None

    def _parar_trace(self, houve_erro: bool):
        if not self._trace_ativo:
            return
        salvar = config.SALVAR_TRACE == "sempre" or (config.SALVAR_TRACE == "erro" and houve_erro)
        caminho = config.PASTA_LOGS / f"{self.prefixo}_trace.zip"
        try:
            if salvar:
                self._contexto.tracing.stop(path=caminho)
                self.status.log(f"Trace salvo em logs/{caminho.name} (abra com: python -m playwright show-trace)")
            else:
                self._contexto.tracing.stop()
        except Exception:
            pass
        self._trace_ativo = False


def _reservar_perfil(perfil: str) -> str:
    """A pasta do perfil, ou a primeira de perfil_2, perfil_3... que nenhuma execução esteja usando."""
    with _trava_perfis:
        pasta, numero = perfil, 1
        while pasta in _perfis_em_uso:
            numero += 1
            pasta = f"{perfil}_{numero}"
        _perfis_em_uso.add(pasta)
        return pasta


def _nome_seguro(texto: str) -> str:
    return "".join(ch if ch.isalnum() or ch in "-_" else "_" for ch in str(texto))[:60]

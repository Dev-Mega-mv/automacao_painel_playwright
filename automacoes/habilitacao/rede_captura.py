import re

from playwright.sync_api import Locator, Page, expect

from ..core import seletores as S
from ..core.apex import confirmar_messagebox
from ..core.erros import ErroAutomacao
from ..core.texto import sem_acento_maiusculo

_HABILITADO = re.compile(r"^\s*SIM\s*$", re.IGNORECASE)
_DESABILITADO = re.compile(r"^(?!\s*SIM\s*$)\s*\S", re.IGNORECASE)  # preenchido e diferente de SIM


class RedeCaptura:
    """Tabela "Rede de captura" do detalhe do contrato: lê e alterna CIELO e CARDSE.

    Cada rede é localizada pelo nome na coluna "Origem de Transação", não pela posição.
    Antes de clicar, confere se o link mostra a ação esperada ("Habilitar"/"Desabilitar").
    """

    TEMPO_CONFIRMACAO_MS = 8000

    def __init__(self, page: Page, log):
        self.page = page
        self.log = log

    # --- leitura ---------------------------------------------------------
    def situacao(self, rede: str) -> str:
        return self._texto(self._celula(rede, S.REDE_COL_SITUACAO))

    def habilitado(self, rede: str) -> str:
        """Texto da coluna "Habilitado" ('SIM', 'NÃO' ou vazio se a rede não existe no contrato)."""
        return self._texto(self._celula(rede, S.REDE_COL_HABILITADO))

    def tem_rede(self, rede: str) -> bool:
        """Se a rede aparece na tabela deste contrato."""
        return self._linha(rede).count() > 0

    def esta_habilitada(self, rede: str) -> bool:
        return self.habilitado(rede).upper() == "SIM"

    def resumo(self, rede: str) -> str:
        """Ex.: 'SIM (ENVIADO)'. Usado nos logs e no relatório."""
        situacao = self.situacao(rede)
        return f"{self.habilitado(rede) or '—'} ({situacao or 'sem situação'})"

    def _linha(self, rede: str) -> Locator:
        origem = self.page.locator(S.REDE_COL_ORIGEM, has_text=re.compile(rf"^\s*{re.escape(rede)}\s*$", re.I))
        return self.page.locator(S.REDE_LINHAS).filter(has=origem)

    def _celula(self, rede: str, seletor: str) -> Locator:
        return self._linha(rede).locator(seletor)

    @staticmethod
    def _texto(celula: Locator) -> str:
        if celula.count() == 0:
            return ""
        return celula.first.inner_text().strip()

    # --- ações -----------------------------------------------------------
    def habilitar(self, rede: str) -> bool:
        """Clica em "Habilitar" e espera o 'SIM'. Retorna False se não confirmou a tempo."""
        self._clicar_acao(rede, "Habilitar")
        if rede == "CIELO" and confirmar_messagebox(self.page, "OK"):
            self.log("Aviso da CIELO confirmado.")
        return self._aguardar(rede, habilitada=True)

    def desabilitar(self, rede: str) -> bool:
        """Clica em "Desabilitar", confirma o "Sim" e espera sair do 'SIM'."""
        self._clicar_acao(rede, "Desabilitar")
        if confirmar_messagebox(self.page, "Sim"):
            self.log("Confirmação de desabilitar aceita.")
        return self._aguardar(rede, habilitada=False)

    def _clicar_acao(self, rede: str, texto_esperado: str):
        link = self._celula(rede, S.REDE_LINK_ACAO)
        if link.count() == 0:
            raise ErroAutomacao(f"A rede {rede} não aparece na tabela \"Rede de captura\" deste contrato.")
        texto = link.first.inner_text().strip()
        if sem_acento_maiusculo(texto) != sem_acento_maiusculo(texto_esperado):
            raise ErroAutomacao(
                f"O link de {rede} mostra '{texto}', mas a ação esperada era '{texto_esperado}'. Nada foi clicado."
            )
        link.first.click()

    def _aguardar(self, rede: str, habilitada: bool) -> bool:
        celula = self._celula(rede, S.REDE_COL_HABILITADO)
        try:
            expect(celula).to_have_text(
                _HABILITADO if habilitada else _DESABILITADO, timeout=self.TEMPO_CONFIRMACAO_MS
            )
            return True
        except AssertionError:
            return False

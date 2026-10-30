import re
import time

from playwright.sync_api import Error as PlaywrightError, Locator, Page, expect

from ..core import seletores as S
from ..core.apex import confirmar_messagebox
from ..core.erros import ErroAutomacao
from ..core.texto import sem_acento_maiusculo

_HABILITADO = re.compile(r"^\s*SIM\s*$", re.IGNORECASE)
_DESABILITADO = re.compile(r"^(?!\s*SIM\s*$)\s*\S", re.IGNORECASE)  # preenchido e diferente de SIM


class RedeCaptura:
    """Tabela "Rede de captura" do detalhe do contrato: lê e alterna CIELO e CARDSE.

    Cada rede é localizada pelo nome na coluna "Origem de Transação", não pela posição.
    Antes de clicar, confere se o link mostra a ação esperada ("Habilitar"; "Desabilitar" ou "Desfazer").
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
        """Clica em "Desabilitar" (ou "Desfazer", que o portal mostra com a situação ENVIADO),
        confirma o "Sim" e espera a linha mudar. Retorna True se saiu do 'SIM'."""
        antes = self._estado(rede)
        texto = self._clicar_acao(rede, "Desabilitar", "Desfazer")
        if confirmar_messagebox(self.page, "Sim"):
            self.log(f"Confirmação de '{texto}' aceita.")
        self._aguardar_mudanca(rede, antes)
        return bool(_DESABILITADO.match(self.habilitado(rede)))

    def _clicar_acao(self, rede: str, *textos_esperados: str) -> str:
        """Clica no link da rede se ele mostrar um dos textos esperados. Devolve o texto clicado."""
        link = self._celula(rede, S.REDE_LINK_ACAO)
        if link.count() == 0:
            raise ErroAutomacao(f"A rede {rede} não aparece na tabela \"Rede de captura\" deste contrato.")
        texto = link.first.inner_text().strip()
        if sem_acento_maiusculo(texto) not in {sem_acento_maiusculo(t) for t in textos_esperados}:
            esperado = "' ou '".join(textos_esperados)
            raise ErroAutomacao(
                f"O link de {rede} mostra '{texto}', mas a ação esperada era '{esperado}'. Nada foi clicado."
            )
        link.first.click()
        return texto

    def _estado(self, rede: str) -> tuple | None:
        """(Habilitado, situação, texto do link) lidos de uma vez, ou None se a linha não está na tela."""
        linhas = self._linha(rede).evaluate_all(
            "(linhas, celulas) => linhas.map(tr => celulas.map(c => (tr.querySelector(c)?.innerText || '').trim()))",
            [S.REDE_COL_HABILITADO, S.REDE_COL_SITUACAO, S.REDE_LINK_ACAO],
        )
        return tuple(linhas[0]) if linhas else None

    def _aguardar_mudanca(self, rede: str, antes: tuple | None):
        """Espera a linha da rede mudar depois do clique, até TEMPO_CONFIRMACAO_MS.

        Não espera só o Habilitado sair do 'SIM': o "Desfazer" muda só a situação (ENVIADO -> ATIVADO,
        continua SIM), e a espera gastava o tempo todo em cada contrato.
        """
        limite = time.monotonic() + self.TEMPO_CONFIRMACAO_MS / 1000
        while time.monotonic() < limite:
            try:
                agora = self._estado(rede)
            except PlaywrightError:  # a página recarregou no meio da leitura
                agora = None
            if agora is not None and agora != antes:
                return
            self.page.wait_for_timeout(200)

    def _aguardar(self, rede: str, habilitada: bool) -> bool:
        celula = self._celula(rede, S.REDE_COL_HABILITADO)
        try:
            expect(celula).to_have_text(
                _HABILITADO if habilitada else _DESABILITADO, timeout=self.TEMPO_CONFIRMACAO_MS
            )
            return True
        except AssertionError:
            return False

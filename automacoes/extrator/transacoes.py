import time

from playwright.sync_api import Error as PlaywrightError

from ..core import seletores as S
from ..core.apex import aguardar_apex, apex_ocioso
from ..core.erros import ErroAutomacao
from .extrator_base import ExtratorBase

FUNCIONALIDADES = {
    "valor_venda_total": "valor total das vendas",
    "data_ultima_transacao": "data da última transação",
}
SEM_TRANSACOES = "Nao houve transacoes no periodo"  # mesmo texto da versão Selenium

_JS_SEM_DADOS = """
seletor => [...document.querySelectorAll(seletor)].some(el => {
  const visivel = !!(el.offsetWidth || el.offsetHeight || el.getClientRects().length);
  const texto = (el.innerText || el.textContent || '').trim().toLowerCase();
  return visivel && (texto.includes('nenhum') || texto.includes('no data'));
})
"""


class ExtratorTransacoes(ExtratorBase):
    """Consulta de transações (Produção > Consulta > Transação, página 5320) de cada código no período.

    - valor_venda_total: quantidade e valor total das transações.
    - data_ultima_transacao: ordena a lista pela data de lançamento (mais recente primeiro) e lê a primeira.
    """

    prefixo_relatorio = "extrator_transacoes"
    aba = "Transações"
    coluna_pesquisa = "CODIGO"

    def __init__(self, credenciais: dict, codigos: list[str], status, *, funcionalidade: str,
                 data_inicial: str, data_final: str, tipo_pesquisa: str = "COD"):
        super().__init__(credenciais, codigos, status, tipo_pesquisa=tipo_pesquisa)
        if funcionalidade not in FUNCIONALIDADES:
            raise ValueError(f"Funcionalidade de transação inválida: {funcionalidade}")
        self.ultima_transacao = funcionalidade == "data_ultima_transacao"
        self.data_inicial = data_inicial
        self.data_final = data_final
        self.titulo = f"Extrator de transações ({FUNCIONALIDADES[funcionalidade]}, {data_inicial} a {data_final})"
        resultado = ["DATA_ULTIMA_TRANSACAO"] if self.ultima_transacao else ["QTD_TRANSACOES", "VALOR_TOTAL_TRANSACOES"]
        self.colunas = ["CODIGO", "DATA_INICIAL", "DATA_FINAL", *resultado, "RESULTADO"]

    def processar_item(self, codigo: str):
        page = self.page
        self.portal.ir_para_consulta_transacoes()
        aguardar_apex(page)
        self._preencher(S.TRANS_DATA_INICIAL, self.data_inicial, "Data inicial")
        self._preencher(S.TRANS_DATA_FINAL, self.data_final, "Data final")
        self._preencher(S.TRANS_CREDENCIADO, codigo, "Credenciado")
        antes = (self.ler(S.TRANS_TOTAL_QTD), self.ler(S.TRANS_TOTAL_VALOR))
        page.locator(S.TRANS_PESQUISAR).click()

        linha = {"CODIGO": codigo, "DATA_INICIAL": self.data_inicial, "DATA_FINAL": self.data_final}
        if self.ultima_transacao:
            data = self._data_ultima_transacao()
            linha["DATA_ULTIMA_TRANSACAO"] = data
            linha["RESULTADO"] = "OK"
            self.status.log(f"{codigo}: última transação = {data}", "SUCCESS")
        else:
            qtd, valor = self._aguardar_totais(antes)
            sem_transacoes = not (qtd or valor)
            linha.update(QTD_TRANSACOES=qtd, VALOR_TOTAL_TRANSACOES=valor,
                         RESULTADO=SEM_TRANSACOES if sem_transacoes else "OK")
            self.status.log(f"{codigo}: " + (SEM_TRANSACOES if sem_transacoes else f"{qtd} transação(ões), total {valor}"),
                            "SUCCESS")
        self.registrar(linha)

    def _preencher(self, seletor: str, valor: str, nome: str, tentativas: int = 3):
        """Digita e confere se o campo ficou com o valor (o APEX às vezes reformata ou perde o que foi digitado)."""
        campo = self.page.locator(seletor)
        for tentativa in range(1, tentativas + 1):
            campo.click()
            campo.fill("")
            campo.press_sequentially(valor, delay=40)
            if campo.input_value().strip() == valor:
                return
            self.status.log(f"O campo {nome} não ficou com '{valor}' (tentativa {tentativa}).", "WARNING")
        raise ErroAutomacao(f"O campo {nome} da consulta de transações não aceitou '{valor}'.")

    def _sem_transacoes(self) -> bool:
        try:
            return bool(self.page.evaluate(_JS_SEM_DADOS, S.TRANS_SEM_DADOS))
        except PlaywrightError:
            return False

    def _aguardar_totais(self, antes: tuple[str, str], limite_s: int = 90) -> tuple[str, str]:
        """Espera os totais ficarem iguais em 3 leituras seguidas (1 s entre elas), com a tela ociosa.

        Leituras durante o carregamento não contam. Valores iguais aos de antes da pesquisa só valem depois
        de o portal mostrar que processou ou de 5 s, para não devolver o total que já estava na tela.
        Sem totais e com "nenhum dado" na lista, devolve vazios.
        """
        inicio = time.monotonic()
        processou = False
        anterior, iguais = None, 0
        while time.monotonic() - inicio < limite_s:
            if not apex_ocioso(self.page):
                processou, anterior, iguais = True, None, 0
                self.page.wait_for_timeout(1000)
                continue
            atual = (self.ler(S.TRANS_TOTAL_QTD), self.ler(S.TRANS_TOTAL_VALOR))
            if not any(atual) and self._sem_transacoes():
                atual = ("", "")
            elif not all(atual):
                atual = None
            if atual is not None and (processou or atual != antes or time.monotonic() - inicio >= 5):
                iguais = iguais + 1 if atual == anterior else 1
                anterior = atual
                if iguais >= 3:
                    return atual
            self.page.wait_for_timeout(1000)
        raise ErroAutomacao(f"Os totais da consulta de transações não carregaram em {limite_s} s.")

    def _data_ultima_transacao(self) -> str:
        self._aguardar_lista()
        if self._sem_transacoes():
            return SEM_TRANSACOES
        self.status.log("Ordenando pela data de lançamento, da mais recente para a mais antiga...")
        self.page.locator(S.TRANS_CAB_DATA).click()
        self.page.locator(S.TRANS_ORDEM_DESC).click()
        aguardar_apex(self.page, 60_000)
        for seletor in (S.TRANS_CELULA_DATA, S.TRANS_CELULA_DATA_ALTERNATIVA):
            celula = self.page.locator(seletor).first
            if celula.count() and celula.inner_text().strip():
                return celula.inner_text().strip()
        raise ErroAutomacao("Não encontrei a data de lançamento na lista de transações depois de ordenar.")

    def _aguardar_lista(self, limite_s: int = 90):
        """Espera a lista de transações carregar: com linhas ou com a mensagem de "nenhum dado"."""
        inicio = time.monotonic()
        processou = False
        while time.monotonic() - inicio < limite_s:
            ocioso = apex_ocioso(self.page)
            processou = processou or not ocioso
            if ocioso and (processou or time.monotonic() - inicio >= 3):
                if self._sem_transacoes() or self._tem_linhas():
                    return
            self.page.wait_for_timeout(500)
        raise ErroAutomacao(f"A lista de transações não carregou em {limite_s} s.")

    def _tem_linhas(self) -> bool:
        seletores = (S.TRANS_CELULA_DATA, S.TRANS_CELULA_DATA_ALTERNATIVA, S.TRANS_CAB_DATA)
        return any(self.page.locator(seletor).count() for seletor in seletores)

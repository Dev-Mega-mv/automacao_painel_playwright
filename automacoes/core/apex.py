"""Comportamentos do Oracle APEX que afetam a automação: carregamento, itens e popups."""
from playwright.sync_api import Error as PlaywrightError
from playwright.sync_api import Locator, Page
from playwright.sync_api import TimeoutError as PlaywrightTimeout

from . import seletores as S

_JS_APEX_OCIOSO = """
() => {
  const visivel = el => !!(el.offsetWidth || el.offsetHeight || el.getClientRects().length);
  const spinners = ['.u-Processing', '.t-Processing', '.a-Spinner', '.apex_loading_indicator', '#apex_wait_overlay'];
  if (spinners.some(s => [...document.querySelectorAll(s)].some(visivel))) return false;
  const jq = window.apex && apex.jQuery;
  return !(jq && jq.active > 0);
}
"""

_JS_LER_VALOR = """
el => {
  if (el.tagName === 'SELECT') {
    const opcao = el.selectedOptions[0];  // opção de valor vazio = nada escolhido (ex.: "- Selecione -")
    return opcao && opcao.value !== '' ? opcao.text.trim() : '';
  }
  const valor = (el.value ?? '').toString().trim();
  return valor || (el.textContent || '').trim();
}
"""


def aguardar_apex(page: Page, timeout_ms: int = 30_000):
    """Espera o APEX terminar spinners e requisições AJAX.

    Se a página recarregar no meio da espera, espera a nova página carregar e tenta de novo.
    """
    for _ in range(3):
        try:
            page.wait_for_load_state("domcontentloaded")
            page.wait_for_function(_JS_APEX_OCIOSO, timeout=timeout_ms)
            return
        except PlaywrightTimeout:
            raise
        except PlaywrightError as erro:
            if "context was destroyed" not in str(erro) and "navigation" not in str(erro).lower():
                raise
    page.wait_for_load_state("domcontentloaded")


def apex_ocioso(page: Page) -> bool:
    """Retrato do momento, sem esperar: False enquanto houver spinner ou AJAX (ou a página estiver recarregando)."""
    try:
        return bool(page.evaluate(_JS_APEX_OCIOSO))
    except PlaywrightError:
        return False


def ler_valor(locator: Locator) -> str:
    """Valor exibido de um item APEX: input usa value, select usa a opção marcada, o resto usa o texto."""
    return locator.evaluate(_JS_LER_VALOR)


def confirmar_messagebox(page: Page, texto: str, timeout_ms: int = 2000) -> bool:
    """Clica no botão `texto` ('Sim', 'OK') do popup ExtJS.

    Retorna False se nenhum popup apareceu dentro de `timeout_ms`.
    """
    caixas = page.locator(S.MESSAGEBOX)
    try:
        caixas.first.wait_for(state="visible", timeout=timeout_ms)
    except PlaywrightTimeout:
        return False

    # O ExtJS cria vários divs com "messagebox" no id; .first evita ambiguidade.
    botao = caixas.get_by_text(texto, exact=True).first
    try:
        botao.click(timeout=2000)
    except PlaywrightTimeout:
        page.keyboard.press("Enter")  # o botão padrão do popup recebe o Enter
    return True

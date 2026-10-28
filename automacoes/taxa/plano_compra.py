import re

from playwright.sync_api import Page
from playwright.sync_api import TimeoutError as PlaywrightTimeout

from ..core import seletores as S
from ..core.apex import aguardar_apex
from ..core.erros import ErroAutomacao
from ..core.texto import sem_acento_maiusculo, somente_digitos
from .item_taxa import ItemTaxa

_JS_OPCOES = "el => [...el.options].map(o => [o.value, o.text.trim()])"
_JS_VALOR = "el => el.tagName === 'SELECT' ? el.value : (el.value ?? '').toString().trim()"
_BOTAO_DE_SALVAR = re.compile(r"^\s*(salvar|gravar|alterar|aplicar(\s+altera\S+)?|ok)\s*$", re.IGNORECASE)
_NAO_E_SALVAR = ("EXCLUIR", "APAGAR", "DELETAR", "REMOVER", "CANCELAR", "VOLTAR")


def escolher_opcao(opcoes: list[tuple[str, str]], valor: str) -> str | None:
    """Valor (value) da opção pedida: pelo value, pelo texto sem acento, pelo número ou pelo começo do texto.

    Ex.: 'TERCA' acha 'TERÇA'; '5' acha '05'; 'SEGUNDA' acha 'SEGUNDA-FEIRA'.
    """
    procurado = sem_acento_maiusculo(valor)
    validas = [(v, sem_acento_maiusculo(t)) for v, t in opcoes if v != ""]
    for regra in (
        lambda v, t: v == valor,
        lambda v, t: t == procurado,
        lambda v, t: procurado.isdigit() and somente_digitos(t) != "" and int(somente_digitos(t)) == int(procurado),
        lambda v, t: t.startswith(procurado),
    ):
        achadas = [v for v, t in validas if regra(v, t)]
        if achadas:
            return achadas[0]
    return None


def mesmo_valor(lido: str, esperado: str) -> bool:
    """Compara textos sem acento; números pelo valor ('1,50' = '1,5'; '05' = '5')."""
    if sem_acento_maiusculo(lido) == sem_acento_maiusculo(esperado):
        return True
    try:
        return _numero(lido) == _numero(esperado)
    except ValueError:
        return False


def _numero(texto: str) -> float:
    texto = str(texto).strip().replace(" ", "")
    if "," in texto:
        texto = texto.replace(".", "").replace(",", ".")
    return float(texto)


class PlanoCompra:
    """Tela do plano de compra (página 2114): preenche os campos pedidos e salva.

    Cada campo é escolhido ou digitado, a tela espera o APEX (os campos de dia dependem da periodicidade)
    e o valor é conferido. Se não ficar, tenta apex.item().setValue(); se ainda assim não ficar, é erro
    e nada é salvo. Antes de salvar, todos os campos preenchidos são conferidos de novo.
    """

    def __init__(self, page: Page, log):
        self.page = page
        self.log = log
        self._definidos: dict[str, tuple[str, str, str]] = {}   # seletor -> (valor pedido, valor no campo, nome)

    def aguardar(self):
        self.page.locator(f"{S.PLANO_PERIODICIDADE}, {S.PLANO_TIPO}").first.wait_for(state="visible")
        aguardar_apex(self.page)

    def escolher_a_vista(self):
        """Plano novo: tipo "A VISTA" (a versão Selenium escolhia a 2ª opção da lista, que é essa)."""
        combo = self.page.locator(S.PLANO_TIPO)
        opcoes = combo.evaluate(_JS_OPCOES)
        valor = escolher_opcao(opcoes, "A VISTA")
        if valor is None:
            if len(opcoes) < 2:
                raise ErroAutomacao("A lista de tipo de plano de compra está vazia. Nada foi salvo.")
            valor, texto = opcoes[1]
            self.log(f"  Não achei a opção 'A VISTA'; usando a 2ª da lista, como a versão Selenium: '{texto}'.",
                     "WARNING")
        combo.select_option(value=valor)
        aguardar_apex(self.page)
        self.page.locator(S.PLANO_PERIODICIDADE).wait_for(state="visible")

    def preencher(self, item: ItemTaxa, novo: bool) -> list[str]:
        """Preenche na ordem da versão Selenium e devolve observações para o relatório."""
        observacoes = []
        if item.pag_dias:
            if novo:
                observacoes.append("plano novo sem dias para pagamento, como na versão Selenium")
            else:
                self.definir(S.PLANO_PAGTO_APOS, item.pag_dias, "Dias para pagamento")
        self.definir(S.PLANO_PERIODICIDADE, item.periodicidade, "Periodicidade")
        if item.semanal:
            if item.dias_semana:
                for numero, dia in enumerate(item.dias_semana, start=1):
                    self.definir(S.PLANO_DIA_SEMANA.format(n=numero), dia, f"Dia da semana {numero}")
                self.definir(S.PLANO_TIPO_DIA, item.tipo_dia, "Tipo de dia")
            else:
                observacoes.append("nenhum dia da semana informado; ficaram os do plano")
        else:
            for seletor, dia, nome in ((S.PLANO_DIA_1, item.dia1, "Dia 1"), (S.PLANO_DIA_2, item.dia2, "Dia 2")):
                if dia:
                    self.definir(seletor, dia, nome)
        if item.taxa:
            self.definir(S.PLANO_TAXA, item.taxa, "Taxa de reembolso")
        else:
            observacoes.append("taxa mantida")
        self.definir(S.PLANO_BANCARIZACAO, item.bancarizar, "Bancarizar")
        return observacoes

    def definir(self, seletor: str, valor: str, nome: str):
        page = self.page
        campo = page.locator(seletor)
        try:
            campo.wait_for(state="visible", timeout=10_000)
        except PlaywrightTimeout:
            raise ErroAutomacao(f"O campo {nome} não apareceu na tela do plano de compra. Nada foi salvo.")

        if campo.evaluate("el => el.tagName") == "SELECT":
            opcoes = campo.evaluate(_JS_OPCOES)
            alvo = escolher_opcao(opcoes, valor)
            if alvo is None:
                disponiveis = ", ".join(texto for v, texto in opcoes if v != "")
                raise ErroAutomacao(f"{nome}: '{valor}' não está entre as opções do portal ({disponiveis}). "
                                    "Nada foi salvo.")
            campo.select_option(value=alvo)
        else:
            alvo = valor
            campo.fill(valor)
            campo.blur()  # sair do campo dispara o "change" nativo, como quando a pessoa digita e passa adiante
        aguardar_apex(page)

        if not self._confere(campo, alvo):
            item_id = seletor.lstrip("#")
            self.log(f"  {nome} não ficou com '{valor}'; tentando pelo apex.item().", "WARNING")
            page.evaluate("([id, v]) => apex.item(id).setValue(v)", [item_id, alvo])
            aguardar_apex(page)
            if not self._confere(campo, alvo):
                raise ErroAutomacao(f"O campo {nome} não ficou com '{valor}' (está '{campo.evaluate(_JS_VALOR)}'). "
                                    "Nada foi salvo.")
        self._definidos[seletor] = (valor, alvo, nome)

    @staticmethod
    def _confere(campo, alvo: str) -> bool:
        return mesmo_valor(campo.evaluate(_JS_VALOR), alvo)

    def _conferir_antes_de_salvar(self):
        """Um campo em cascata pode ter apagado outro já preenchido: confere todos de novo antes de salvar."""
        for seletor, (valor, alvo, nome) in self._definidos.items():
            campo = self.page.locator(seletor)
            if not campo.count() or not self._confere(campo, alvo):
                atual = campo.evaluate(_JS_VALOR) if campo.count() else "campo sumiu"
                raise ErroAutomacao(f"O campo {nome} perdeu o valor '{valor}' antes de salvar (está '{atual}'). "
                                    "Nada foi salvo.")

    # --- salvar ----------------------------------------------------------
    def salvar_existente(self):
        """1º botão do cabeçalho da região, como a versão Selenium, conferindo que é mesmo um botão de salvar."""
        self._conferir_antes_de_salvar()
        botao = self.page.locator(S.PLANO_SALVAR_EXISTENTE)
        if not botao.count():
            botao = self.page.get_by_role("button", name=_BOTAO_DE_SALVAR)
            if not botao.count():
                raise ErroAutomacao("Não achei o botão de salvar do plano de compra. Nada foi salvo.")
        texto = botao.first.inner_text().strip()
        if any(proibido in sem_acento_maiusculo(texto) for proibido in _NAO_E_SALVAR):
            raise ErroAutomacao(f"O botão onde o plano é salvo mostra '{texto}', que não é de salvar. Nada foi salvo.")
        self.log(f"  Salvando o plano (botão '{texto}')...")
        botao.first.click()

    def salvar_novo(self):
        self._conferir_antes_de_salvar()
        self.log("  Criando o plano (OK)...")
        self.page.locator(S.BOTAO_OK).click()

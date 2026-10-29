from playwright.sync_api import TimeoutError as PlaywrightTimeout

from ..core import seletores as S
from ..core.apex import aguardar_apex, ler_valor
from ..core.automacao_base import AutomacaoPorItem
from ..core.erros import ErroAutomacao
from ..core.texto import sem_acento_maiusculo

JA_ESTAVA = "OK (já estava com a conciliação pedida; nada foi salvo)"

_JS_OPCOES = "el => [...el.options].map(o => [o.value, o.text.trim()])"


def mesma_conciliacao(a: str, b: str) -> bool:
    return bool(a) and sem_acento_maiusculo(a) == sem_acento_maiusculo(b)


class Conciliacao(AutomacaoPorItem):
    """Troca a conciliação de vendas EDI de cada credenciado (botão "Alterar configuração EDI", página 2310).

    Como na versão Selenium (alt_conciliacao.py): pesquisa, abre a configuração EDI, escolhe a
    conciliação e salva com OK. A conciliação é digitada na tela (o Selenium tinha quatro opções fixas). Além dela:
      - o credenciado é conferido antes (lista de resultados ou outro credenciado = erro, nada é alterado);
      - a opção é escolhida pelo texto, sem diferença de acento ou maiúscula; se não existir, nada é alterado;
      - se já estiver com a conciliação pedida, não salva;
      - depois de salvar, confere a conciliação mostrada na tela do credenciado.
    """

    nome = "conciliacao"
    titulo = "Alteração de conciliação"
    prefixo_relatorio = "conciliacao"
    aba = "Conciliação"
    colunas = ["PESQUISADO", "CODIGO", "NOME_FANTASIA", "CONCILIACAO_ANTES", "CONCILIACAO_DEPOIS", "RESULTADO"]

    def __init__(self, credenciais: dict, codigos: list[str], status, *, conciliacao: str, tipo_pesquisa: str = "COD"):
        super().__init__(credenciais, codigos, status)
        self.conciliacao = conciliacao.strip()
        self.tipo_pesquisa = tipo_pesquisa.upper()
        self.titulo = f"Alteração de conciliação para '{self.conciliacao}'"
        self._linha: dict | None = None  # linha do item em andamento, para o erro sair com o que já foi lido

    def processar_item(self, codigo: str):
        page, log = self.page, self.status.log
        linha = self._linha = {"PESQUISADO": codigo}
        self.portal.ir_para_pesquisa_credenciado()
        self.portal.abrir_credenciado(codigo, self.tipo_pesquisa)
        aguardar_apex(page)
        linha.update(CODIGO=self.ler(S.DET_CODIGO), NOME_FANTASIA=self.ler(S.DET_FANTASIA),
                     CONCILIACAO_ANTES=self.ler(S.DET_CONCILIACAO))

        page.locator(S.DET_BTN_ALTERAR_EDI).click()
        combo = page.locator(S.EDI_CONCILIACAO)
        combo.wait_for(state="visible")
        aguardar_apex(page)
        valor, texto = self._opcao_pedida(combo)
        atual = ler_valor(combo)
        linha["CONCILIACAO_ANTES"] = atual
        log(f"Conciliação atual: {atual or '(vazia)'}")

        if mesma_conciliacao(atual, texto):
            linha.update(CONCILIACAO_DEPOIS=atual, RESULTADO=JA_ESTAVA)
            log(f"{codigo}: já estava com '{texto}'; nada foi salvo.", "SUCCESS")
            self._sair_sem_salvar()
        else:
            combo.select_option(value=valor)
            aguardar_apex(page)
            if not mesma_conciliacao(ler_valor(combo), texto):
                raise ErroAutomacao(f"A lista de conciliação não ficou com '{texto}'. Nada foi salvo.")
            page.locator(S.BOTAO_OK).click()
            linha["CONCILIACAO_DEPOIS"], linha["RESULTADO"] = self._conferir_depois_de_salvar(texto)
            aviso = linha["RESULTADO"].startswith("AVISO")
            log(f"{codigo}: " + (linha["RESULTADO"] if aviso else
                                 f"conciliação alterada de '{atual or '(vazia)'}' para '{texto}'."),
                "WARNING" if aviso else "SUCCESS")

        self._linha = None
        self.registrar(linha)

    def _opcao_pedida(self, combo) -> tuple[str, str]:
        """(valor, texto) da opção com o nome pedido. Se não existir, o item vira erro e nada é alterado."""
        opcoes = [(valor, texto) for valor, texto in combo.evaluate(_JS_OPCOES) if valor != ""]
        for valor, texto in opcoes:
            if mesma_conciliacao(texto, self.conciliacao):
                return valor, texto
        disponiveis = "; ".join(texto for _, texto in opcoes) or "nenhuma"
        raise ErroAutomacao(f"A conciliação '{self.conciliacao}' não está na lista do portal (opções: {disponiveis}). "
                            "Nada foi alterado.")

    def _conferir_depois_de_salvar(self, texto: str) -> tuple[str, str]:
        """Depois do OK: (conciliação mostrada, resultado). Levanta ErroAutomacao se não salvou.

        O esperado é o portal voltar para a tela do credenciado. Como a versão Selenium não conferia nada
        depois do OK, também são tratados: mensagem de erro do portal e a tela de configuração EDI continuar aberta.
        """
        page = self.page
        try:
            page.locator(f"{S.DETALHE_CREDENCIADO}, {S.MENSAGEM_ERRO}").first.wait_for(state="attached")
        except PlaywrightTimeout:
            pass
        aguardar_apex(page)

        if page.locator(S.DETALHE_CREDENCIADO).count():
            depois = self.ler(S.DET_CONCILIACAO)
            if not depois:
                return "", "AVISO: salvo, mas não consegui ler a conciliação na tela do credenciado para conferir"
            if not mesma_conciliacao(depois, texto):
                raise ErroAutomacao(f"Depois de salvar, o credenciado mostra a conciliação '{depois}', e não '{texto}'.")
            return depois, "OK (alterada)"

        erro = self.portal.mensagem_de_erro()
        if erro:
            raise ErroAutomacao(f"O portal não salvou a conciliação: {erro}")
        combo = page.locator(S.EDI_CONCILIACAO)
        if combo.count() and mesma_conciliacao(ler_valor(combo), texto):
            return texto, ("AVISO: depois do OK a tela de configuração EDI continuou aberta, com a conciliação "
                           "pedida; confira no portal se foi salva")
        raise ErroAutomacao("Cliquei em OK, mas o portal não voltou para a tela do credenciado. "
                            "Confira no portal se a conciliação foi alterada.")

    def _sair_sem_salvar(self):
        """Sai da configuração EDI sem salvar, se houver um botão para isso; senão, o próximo item volta pelo menu."""
        botao = self.page.locator(S.EDI_SAIR_SEM_SALVAR).filter(visible=True).first
        if not botao.count():
            return
        botao.click()
        try:
            self.page.locator(S.EDI_CONCILIACAO).wait_for(state="detached", timeout=10_000)
        except PlaywrightTimeout:
            self.status.log("A configuração EDI não fechou; o próximo item recomeça pelo menu.", "WARNING")

    def registrar_falha(self, codigo: str, mensagem: str):
        """A linha do erro leva o que já foi lido (ex.: a conciliação de antes)."""
        linha = self._linha if self._linha and self._linha.get("PESQUISADO") == codigo else {"PESQUISADO": codigo}
        self._linha = None
        linha["RESULTADO"] = f"ERRO: {mensagem}"
        self.registrar(linha)

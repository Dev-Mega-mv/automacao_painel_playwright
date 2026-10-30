import re
import time
from urllib.parse import urljoin

from playwright.sync_api import Error as PlaywrightError
from playwright.sync_api import Locator, Page, expect
from playwright.sync_api import TimeoutError as PlaywrightTimeout

import config

from . import seletores as S
from .apex import aguardar_apex, ler_valor
from .erros import (
    CredenciadoNaoEncontrado,
    ErroAutomacao,
    ExecucaoInterrompida,
    LoginFalhou,
    NavegadorFechado,
)
from .texto import mesmo_documento, pesquisa_por_documento


class PortalInfox:
    """Ações no portal Infox que todas as automações usam: login, menu, pesquisa e contratos."""

    ATRASO_DIGITACAO_MS = 60

    def __init__(self, page: Page, status):
        self.page = page
        self.status = status

    def log(self, mensagem: str, nivel: str = "INFO"):
        self.status.log(mensagem, nivel)

    # --- login -----------------------------------------------------------
    def entrar(self, usuario: str, senha: str):
        page = self.page
        self.log("Abrindo o portal Infox...")
        page.goto(config.URL_LOGIN, wait_until="domcontentloaded")

        try:
            self._digitar(S.LOGIN_USUARIO, usuario)
            self._digitar(S.LOGIN_SENHA, senha)
        except PlaywrightTimeout:
            raise LoginFalhou("A tela de login do Infox não carregou. Confira a conexão com o portal.")

        self._clicar_captcha_se_existir()
        page.locator(S.LOGIN_BOTAO).click()
        self._aguardar_resultado_do_login()
        self.log("Login realizado.")

        time.sleep(3)

    def _digitar(self, seletor: str, texto: str):
        campo = self.page.locator(seletor)
        campo.fill("")
        campo.press_sequentially(texto, delay=self.ATRASO_DIGITACAO_MS)

    def _clicar_captcha_se_existir(self):
        captcha = self.page.locator(S.LOGIN_CAPTCHA)
        try:
            captcha.wait_for(state="visible", timeout=4000)
        except PlaywrightTimeout:
            return
        captcha.click()

    def _aguardar_resultado_do_login(self, espera_automatica_s: int = 15):
        """Espera o menu aparecer. Falha na hora se o portal mostrar erro de login.

        Depois de `espera_automatica_s` sem resultado, avisa na tela de status e dá
        mais config.ESPERA_CAPTCHA_S segundos para alguém resolver o captcha no Chrome.
        Sem janela (HEADLESS=1, como no servidor) ninguém consegue resolver, então não espera.
        """
        menu = self.page.locator(S.MENU_RAIZ)
        espera_captcha_s = 0 if config.HEADLESS else config.ESPERA_CAPTCHA_S
        inicio = time.monotonic()
        limite = inicio + espera_automatica_s + espera_captcha_s
        avisou = False
        while time.monotonic() < limite:
            if self.status.parada_solicitada:
                raise ExecucaoInterrompida("Execução interrompida durante o login.")
            try:
                menu.wait_for(state="visible", timeout=1500)
                return
            except PlaywrightTimeout:
                pass
            except PlaywrightError:
                if self.page.is_closed():
                    raise NavegadorFechado("O Chrome foi fechado durante o login.")
                raise

            erro = self.mensagem_de_erro()
            if erro:
                raise LoginFalhou(f"O portal recusou o login: {erro}")

            if not avisou and espera_captcha_s and time.monotonic() - inicio > espera_automatica_s:
                self.log(
                    "O login não concluiu sozinho. Se houver captcha, resolva na janela do Chrome. "
                    f"Aguardando até {espera_captcha_s} segundos.",
                    "WARNING",
                )
                avisou = True
        if config.HEADLESS:
            raise LoginFalhou(
                f"O login não foi concluído em {espera_automatica_s} segundos. Confira usuário e senha. Se o portal "
                "pediu captcha, ele não pode ser resolvido aqui (Chrome sem janela); tente de novo."
            )
        raise LoginFalhou(
            "O login não foi concluído. Confira usuário e senha ou resolva o captcha na janela do Chrome."
        )

    def mensagem_de_erro(self) -> str:
        """Texto da mensagem de erro do APEX visível na tela, ou vazio se não houver."""
        erro = self.page.locator(S.MENSAGEM_ERRO).first
        try:
            return erro.inner_text(timeout=1000).strip() if erro.count() else ""
        except PlaywrightError:
            return ""

    # --- pesquisa de credenciado ------------------------------------------
    def ir_para_pesquisa_credenciado(self):
        for seletor in S.MENU_PESQUISA_CREDENCIADO:
            self.page.locator(seletor).click()
        self.page.locator(S.PESQ_CODIGO).wait_for(state="visible")

    def pesquisar_credenciado(self, valor: str, tipo_pesquisa: str) -> int:
        """Pesquisa por código, CPF ou CNPJ.

        Devolve 0 se o portal abriu direto a tela do credenciado, ou quantos resultados a lista mostrou.
        Sem resultado, levanta CredenciadoNaoEncontrado.
        CPF e CNPJ vão no mesmo campo do portal (P2100_CNPJ), como na versão Selenium.
        """
        page = self.page
        tipo = tipo_pesquisa.upper()
        por_documento = pesquisa_por_documento(tipo)
        self.log(f"Pesquisando {valor} por {tipo if por_documento else 'código'}...")

        page.locator(S.PESQ_CODIGO).fill("")
        page.locator(S.PESQ_CNPJ).fill("")
        page.locator(S.PESQ_CNPJ if por_documento else S.PESQ_CODIGO).fill(valor)
        page.locator(S.PESQ_BOTAO).click()

        try:
            page.locator(S.DETALHE_CREDENCIADO).first.wait_for(state="attached")
            return 0
        except PlaywrightTimeout:
            if page.locator(S.PESQ_SEM_DADOS).is_visible():
                raise CredenciadoNaoEncontrado(f"Nenhum credenciado encontrado para {valor}.")
            resultados = page.locator(S.PESQ_LINKS_RESULTADO).count()
            if resultados:
                return resultados
            raise ErroAutomacao(f"A pesquisa por {valor} não abriu a tela do credenciado.")

    def abrir_credenciado(self, valor: str, tipo_pesquisa: str):
        """Pesquisa e confirma que abriu o credenciado certo. Uma lista de resultados é recusada (ambígua)."""
        if self.pesquisar_credenciado(valor, tipo_pesquisa):
            raise ErroAutomacao(
                f"A pesquisa por {valor} retornou uma lista em vez de abrir o credenciado. "
                "Pesquise pelo código para evitar ambiguidade."
            )
        self.conferir_credenciado(valor, tipo_pesquisa, "Nada foi alterado.")

    def abrir_resultado(self, indice: int = 0):
        """Abre um credenciado da lista de resultados da pesquisa.

        Como a versão Selenium, segue o endereço do link (relativo, "f?p=...") em vez de clicar.
        """
        link = self.page.locator(S.PESQ_LINKS_RESULTADO).nth(indice)
        endereco = (link.get_attribute("href") or "").strip()
        if endereco and not endereco.lower().startswith("javascript:"):
            self.page.goto(urljoin(self.page.url, endereco), wait_until="domcontentloaded")
        else:
            link.click()
        self.page.locator(S.DETALHE_CREDENCIADO).first.wait_for(state="attached")

    def conferir_credenciado(self, valor: str, tipo_pesquisa: str, consequencia: str):
        """Confirma que a tela aberta é do credenciado pesquisado, antes de usar o que está nela.

        `consequencia` completa a mensagem de erro (ex.: "Nada foi alterado.").
        """
        tipo = tipo_pesquisa.upper()
        campo = self.page.locator(S.DET_CNPJ if pesquisa_por_documento(tipo) else S.DET_CODIGO)
        lido = ler_valor(campo) if campo.count() else ""
        if not lido:
            self.log("Não foi possível ler o código/CNPJ na tela do credenciado para conferir.", "WARNING")
            return
        if not mesmo_documento(lido, valor):
            raise ErroAutomacao(f"O portal abriu o credenciado {lido}, mas a pesquisa foi por {valor}. {consequencia}")
        self.log(f"Credenciado {lido} aberto.")

    # --- consulta de transações ------------------------------------------------
    def ir_para_consulta_transacoes(self):
        """Abre Produção > Consulta > Transação (página 5320).

        Na versão Selenium, esse caminho pelo menu falhou na maioria das execuções registradas.
        Se o menu não abrir a tela, tenta o endereço da página na sessão atual do APEX.
        """
        page = self.page
        try:
            for seletores in S.MENU_CONSULTA_TRANSACOES:
                self._clicar_item_de_menu(seletores)
            page.locator(S.TRANS_CREDENCIADO).wait_for(state="visible")
            return
        except PlaywrightTimeout:
            pass

        sessao = self.sessao_apex()
        if not sessao:
            raise ErroAutomacao("O menu não abriu a consulta de transações e não encontrei a sessão do portal.")
        self.log("O menu não abriu a consulta de transações; abrindo a página pelo endereço.", "WARNING")
        page.goto(f"{config.URL_PORTAL}f?p=380:{S.PAGINA_CONSULTA_TRANSACOES}:{sessao}", wait_until="domcontentloaded")
        try:
            page.locator(S.TRANS_CREDENCIADO).wait_for(state="visible")
        except PlaywrightTimeout:
            raise ErroAutomacao("A tela de consulta de transações não abriu nem pelo menu nem pelo endereço.")
        self.log("Consulta de transações aberta pelo endereço da página.")

    def _clicar_item_de_menu(self, seletores: tuple[str, ...]):
        """Clica no primeiro seletor que existir na tela (rótulo do item ou o próprio item)."""
        self.page.locator(", ".join(seletores)).first.wait_for(state="attached")
        for seletor in seletores:
            item = self.page.locator(seletor)
            if item.count():
                item.first.click()
                return

    def sessao_apex(self) -> str:
        """Número da sessão do APEX: do objeto apex, do campo p_instance ou da URL (f?p=380:pagina:sessao)."""
        try:
            sessao = self.page.evaluate(
                "() => (window.apex && apex.env && apex.env.APP_SESSION)"
                " || (document.getElementById('pInstance') || {}).value || ''"
            )
        except PlaywrightError:
            sessao = ""
        if not sessao:
            achado = re.search(r"f\?p=\d+:[^:]*:(\d+)", self.page.url)
            sessao = achado.group(1) if achado else ""
        return str(sessao)

    # --- contratos ---------------------------------------------------------
    def abrir_contratos(self) -> Locator:
        """Abre "Visualizar contratos" e devolve o locator das linhas da lista."""
        self.page.locator(S.DET_BTN_CONTRATOS).click()
        self.page.locator(S.CONTRATOS_CAB_NUMERO).wait_for(state="visible")
        aguardar_apex(self.page)
        return self.page.locator(S.CONTRATOS_LINHAS)

    def garantir_ordem_crescente(self, linhas: Locator, tentativas: int = 4):
        """Clica no cabeçalho "Número" até a lista começar pelo contrato 1."""
        for tentativa in range(1, tentativas + 1):
            if linhas.count() == 0:
                return
            primeiro = self.numero_contrato(linhas.first)
            if primeiro == 1:
                return
            self.log(f"Lista começa no contrato {primeiro}; ordenando pelo número (tentativa {tentativa})...")
            self.page.locator(S.CONTRATOS_CAB_NUMERO).click()
            try:
                expect(linhas.first.locator(S.CONTRATO_LINK_NUMERO)).not_to_have_text(
                    str(primeiro), timeout=5000
                )
            except AssertionError:
                pass
            aguardar_apex(self.page)
        self.log("Não foi possível confirmar a ordem crescente dos contratos; seguindo assim mesmo.", "WARNING")

    def numero_contrato(self, linha: Locator) -> int | None:
        texto = linha.locator(S.CONTRATO_LINK_NUMERO).inner_text().strip()
        try:
            return int(texto)
        except ValueError:
            return None

    def produto_contrato(self, linha: Locator) -> str:
        return linha.locator(S.CONTRATO_LINK_PRODUTO).inner_text().strip()

    def abrir_contrato(self, linha: Locator):
        linha.locator(S.CONTRATO_LINK_NUMERO).click()
        self.page.locator(S.CONTRATO_REDE_CAPTURA).wait_for(state="attached")

    def estado_contrato(self) -> str | None:
        """Estado do contrato aberto (APROVADO, DEFINIÇÃO, BLOQUEADO...), ou None se o campo não estiver na tela."""
        for seletor in (S.CONTRATO_ESTADO, S.CONTRATO_ESTADO_ALTERNATIVO):
            campo = self.page.locator(seletor)
            if campo.count():
                return ler_valor(campo.first)
        return None

    def aprovar_contrato(self, observacao: str = ""):
        """Opções > Aprovar no contrato aberto e confirma com OK; volta para o detalhe do contrato.

        A observação só é preenchida se for informada e o campo aparecer.
        """
        page = self.page
        page.locator(S.CONTRATO_MENU_OPCOES).click()
        page.locator(S.CONTRATO_MENU_APROVAR).click()
        campo_obs = page.locator(S.CONTRATO_OBS)
        try:
            campo_obs.wait_for(state="visible", timeout=5000)
            if observacao:
                campo_obs.fill(observacao)
        except PlaywrightTimeout:
            campo_obs = None
        page.locator(S.BOTAO_OK).click()
        if campo_obs is not None:
            campo_obs.wait_for(state="hidden")
        page.locator(S.CONTRATO_REDE_CAPTURA).wait_for(state="attached")
        aguardar_apex(page)

    def voltar_para_lista_de_contratos(self):
        """Volta do detalhe do contrato para a lista. Não faz nada se já estiver na lista."""
        page = self.page
        if page.locator(S.CONTRATO_REDE_CAPTURA).count() == 0 and page.locator(S.CONTRATOS_LINHAS).count() > 0:
            return
        page.locator(S.BOTAO_VOLTAR).click()
        page.locator(S.CONTRATO_REDE_CAPTURA).wait_for(state="detached")
        page.locator(S.CONTRATOS_LINHAS).first.wait_for(state="visible")

    def voltar_para_credenciado(self):
        self.page.locator(S.CONTRATOS_VOLTAR).click()
        self.page.locator(S.DET_BTN_CONTRATOS).wait_for(state="visible")

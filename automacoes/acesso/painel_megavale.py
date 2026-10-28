"""Painel administrativo da Megavale: login e cadastro de estabelecimento e de gerente.

Fluxo e seletores vindos da automação original (automacao_criacao_acesso/megavale.py), com duas
conferências a mais: depois de salvar, o cadastro precisa aparecer na lista filtrada; e o
estabelecimento do gerente é escolhido pela opção que mostra o código, não pela primeira da lista.
"""
import re

from playwright.sync_api import Page
from playwright.sync_api import TimeoutError as PlaywrightTimeout

import config

from ..core.erros import ErroAutomacao, LoginFalhou
from ..core.texto import sem_acento_maiusculo, somente_digitos
from .dados_infox import DadosCredenciado

PAGINA_LOGIN = "admin"
PAGINA_ESTABELECIMENTOS = "admin_home.php?item=estabelecimento&modulare=0"

LOGIN_USUARIO = "#formlogin"
LOGIN_SENHA = "#formsenha"
LOGIN_BOTAO = ".btn-success"

# Listas (estabelecimentos e gerentes)
BOTAO_FILTRO = "i.mdi.mdi-filter.noti-icon"
FILTRO_CODIGO_INFOX = r"#filter_valor_estabelecimento\.codigo_infox"
FILTRO_EMAIL = r"#filter_valor_pessoa\.email"
BOTAO_FILTRAR = "input[name='enviar'][value='Filtrar']"
LISTA = "tbody#sortable"
LINHAS_LISTA = "tbody#sortable tr[id^='rowid_']"
BOTAO_NOVO = ".icon-colored1"
MENU_LATERAL = "#side-menu"

# Formulários
BOTAO_SALVAR = "#save"
MODAL_ERRO = ".bootbox.modal"
MODAL_ERRO_TEXTO = ".bootbox-body"
ESTADO = "#estado"
CIDADE = "#cidade"
SELECAO_ESTABELECIMENTO = "input.vs__search"
OPCOES_ESTABELECIMENTO = ".vs__dropdown-option"


class PainelMegavale:
    def __init__(self, page: Page, status):
        self.page = page
        self.status = status

    def log(self, mensagem: str, nivel: str = "INFO"):
        self.status.log(mensagem, nivel)

    # --- login -------------------------------------------------------------
    def entrar(self, usuario: str, senha: str):
        page = self.page
        self.log("Abrindo o painel Megavale...")
        page.goto(config.URL_MEGAVALE + PAGINA_LOGIN, wait_until="domcontentloaded")
        campo = page.locator(LOGIN_USUARIO)
        try:
            campo.wait_for(state="visible", timeout=5000)
        except PlaywrightTimeout:
            self.log("O painel Megavale já estava logado neste perfil do Chrome.")
            return
        campo.fill(usuario)
        page.locator(LOGIN_SENHA).fill(senha)
        page.locator(LOGIN_BOTAO).first.click()
        page.wait_for_load_state("domcontentloaded")
        try:
            campo.wait_for(state="hidden", timeout=10_000)
        except PlaywrightTimeout:
            raise LoginFalhou("O painel Megavale não aceitou o login. Confira o usuário e a senha do painel.")
        self.log("Login no painel Megavale realizado.")

    # --- listas e filtros ------------------------------------------------------
    def _ir_para_estabelecimentos(self):
        self.page.goto(config.URL_MEGAVALE + PAGINA_ESTABELECIMENTOS, wait_until="domcontentloaded")
        self.page.locator(BOTAO_FILTRO).first.wait_for(state="visible")

    def _ir_para_gerentes(self):
        """Menu "Gerentes" (dentro de "Cadastrar", se estiver recolhido), a partir de uma página do painel."""
        page = self.page
        self._ir_para_estabelecimentos()
        gerentes = page.get_by_role("link", name="Gerentes").first
        if not gerentes.is_visible():
            cadastrar = page.get_by_role("link", name="Cadastrar").first
            if cadastrar.is_visible():
                cadastrar.click()
        try:
            gerentes.click(timeout=5000)
        except PlaywrightTimeout:
            page.locator(MENU_LATERAL).get_by_role("link", name="Gerentes").first.click()
        page.wait_for_load_state("domcontentloaded")
        page.locator(BOTAO_FILTRO).first.wait_for(state="visible")

    def _filtrar(self, campo: str, valor: str) -> int:
        """Aplica o filtro da lista e devolve quantas linhas sobraram."""
        page = self.page
        page.locator(BOTAO_FILTRO).first.click()
        page.locator(campo).fill(valor)
        page.locator(BOTAO_FILTRAR).first.click()
        page.wait_for_load_state("domcontentloaded")
        try:
            page.wait_for_load_state("networkidle", timeout=5000)
        except PlaywrightTimeout:
            pass
        page.locator(LISTA).wait_for(state="attached")
        return page.locator(LINHAS_LISTA).count()

    def estabelecimento_existe(self, codigo_infox: str) -> bool:
        self._ir_para_estabelecimentos()
        return self._filtrar(FILTRO_CODIGO_INFOX, codigo_infox) > 0

    def gerente_existe(self, email: str) -> bool:
        if not email:
            raise ErroAutomacao("Sem e-mail não dá para procurar o gerente (o filtro vazio lista todos).")
        self._ir_para_gerentes()
        return self._filtrar(FILTRO_EMAIL, email) > 0

    # --- cadastros ---------------------------------------------------------------
    def cadastrar_estabelecimento(self, dados: DadosCredenciado) -> list[str]:
        """Preenche e salva o estabelecimento. Devolve avisos (ex.: cidade não encontrada na lista do painel)."""
        page = self.page
        avisos: list[str] = []
        self._ir_para_estabelecimentos()
        page.locator(BOTAO_NOVO).first.click()

        page.locator("#razao_social").fill(dados.razao_social)
        page.locator("#nome").fill(dados.nome_fantasia)
        page.locator("#cnpj").fill(dados.cnpj)
        self._preencher_cep(dados.cep)
        # O CEP pode preencher logradouro e bairro sozinho; só completa o que ficou vazio
        for seletor, valor in (("#logradouro", dados.logradouro), ("#bairro", dados.bairro)):
            campo = page.locator(seletor)
            if valor and campo.count() and not campo.input_value().strip():
                campo.fill(valor)
        if dados.numero and page.locator("#numero").count():
            page.locator("#numero").fill(dados.numero)
        avisos += self._selecionar_estado_e_cidade(dados.estado, dados.cidade)

        page.locator("#codigo_infox").fill(dados.codigo)
        page.locator("#cpf").fill(dados.cpf_proprietario)
        page.locator("#email").fill(dados.email)
        for seletor, valor in (("#ddd_celular", dados.ddd_celular), ("#nro_celular", dados.celular),
                               ("#ddd_telefone", dados.ddd_telefone), ("#nro_telefone", dados.telefone)):
            if valor:
                page.locator(seletor).fill(valor)
        page.locator('input[name="apenas_delivery"][value="0"]').check()

        self._salvar("estabelecimento")
        if not self.estabelecimento_existe(dados.codigo):
            raise ErroAutomacao("Salvei o estabelecimento, mas ele não aparece na lista filtrada pelo código. "
                                "Confira no painel antes de rodar de novo.")
        self.log(f"Estabelecimento {dados.codigo} criado no painel.", "SUCCESS")
        return avisos

    def cadastrar_gerente(self, dados: DadosCredenciado) -> list[str]:
        """Gerente com login = e-mail e senha = código do credenciado, ligado ao estabelecimento."""
        page = self.page
        avisos: list[str] = []
        self._ir_para_gerentes()
        page.locator(BOTAO_NOVO).first.click()

        page.locator("#pes_nome").fill(dados.nome_fantasia or dados.razao_social)
        page.locator("#pes_login").fill(dados.email)
        page.locator("#email").fill(dados.email)
        page.locator("#pes_senha").fill(dados.codigo)
        page.locator("#pes_senha2").fill(dados.codigo)
        celular = somente_digitos(dados.ddd_celular + dados.celular)
        if celular:
            page.locator("#telefone").click()
            page.locator("#telefone").press_sequentially(celular, delay=50)
        else:
            avisos.append("gerente sem celular (a Infox não tem)")
        self._escolher_estabelecimento(dados.codigo)

        self._salvar("gerente")
        if not self.gerente_existe(dados.email):
            raise ErroAutomacao("Salvei o gerente, mas ele não aparece na lista filtrada pelo e-mail. "
                                "Confira no painel antes de rodar de novo.")
        self.log(f"Gerente {dados.email} criado no painel.", "SUCCESS")
        return avisos

    # --- partes do formulário -------------------------------------------------------
    def _preencher_cep(self, cep: str):
        """Digita o CEP como uma pessoa, para a página buscar o endereço, e espera a busca."""
        if not cep:
            return
        campo = self.page.locator("#cep")
        campo.click()
        campo.press("Control+A")
        campo.press("Backspace")
        campo.press_sequentially(cep, delay=50)
        campo.dispatch_event("change")
        campo.blur()
        self.page.wait_for_timeout(1500)

    def _opcoes(self, seletor: str) -> list[dict]:
        return self.page.locator(f"{seletor} option").evaluate_all(
            "ops => ops.map(o => ({valor: o.value, texto: o.textContent}))")

    def _selecionar_estado_e_cidade(self, estado: str, cidade: str) -> list[str]:
        """Escolhe a UF e, depois que a lista de cidades carregar, a cidade (igual, ou que contenha o nome).

        select_option já dispara o evento change. A original disparava outro, que fazia o painel recarregar
        a lista de cidades duas vezes e podia apagar a cidade já escolhida.
        """
        page = self.page
        if estado:
            alvo = sem_acento_maiusculo(estado)
            valor = next((o["valor"] for o in self._opcoes(ESTADO)
                          if sem_acento_maiusculo(o["texto"]) == alvo or o["valor"] == estado), None)
            if valor is None:
                return [f"UF '{estado}' não encontrada no painel"]
            page.locator(ESTADO).select_option(value=valor)
        if not cidade:
            return []

        try:
            page.wait_for_function(f"document.querySelectorAll('{CIDADE} option').length > 1", timeout=5000)
        except PlaywrightTimeout:
            return [f"a lista de cidades de {estado} não carregou"]
        opcoes = [o for o in self._opcoes(CIDADE) if o["valor"] != "-1"]
        alvo = sem_acento_maiusculo(cidade)
        valor = next((o["valor"] for o in opcoes if sem_acento_maiusculo(o["texto"]) == alvo), None)
        if valor is None:
            valor = next((o["valor"] for o in opcoes
                          if alvo in sem_acento_maiusculo(o["texto"]) or sem_acento_maiusculo(o["texto"]) in alvo), None)
        if valor is None:
            return [f"cidade '{cidade}' não encontrada no painel"]
        for _ in range(2):  # se a lista ainda recarregar depois da escolha, escolhe de novo
            page.locator(CIDADE).select_option(value=valor)
            page.wait_for_timeout(700)
            if page.locator(CIDADE).input_value() == valor:
                return []
        return [f"a cidade '{cidade}' não ficou escolhida no painel"]

    def _escolher_estabelecimento(self, codigo: str):
        """No campo de busca do gerente, escolhe a opção que mostra o código do credenciado.

        Se nenhuma mostrar o código, só aceita quando há uma única opção (a original pegava sempre a primeira).
        """
        page = self.page
        busca = page.locator(SELECAO_ESTABELECIMENTO).first
        busca.click()
        busca.fill(codigo)
        opcoes = page.locator(OPCOES_ESTABELECIMENTO)
        try:
            opcoes.first.wait_for(state="visible")
        except PlaywrightTimeout:
            raise ErroAutomacao(f"O campo Estabelecimento do gerente não mostrou nenhuma opção para {codigo}.")
        page.wait_for_timeout(500)  # a lista pode ainda estar filtrando
        textos = opcoes.all_inner_texts()
        codigo_exato = re.compile(rf"(?<!\d){re.escape(codigo)}(?!\d)")
        indice = next((i for i, texto in enumerate(textos) if codigo_exato.search(texto)), None)
        if indice is None and len(textos) == 1:
            indice = 0
            self.log(f"A opção do estabelecimento não mostra o código; usando a única: {textos[0].strip()}", "WARNING")
        if indice is None:
            raise ErroAutomacao(f"O campo Estabelecimento do gerente mostrou {len(textos)} opções e nenhuma "
                                f"com o código {codigo}. Ligue o gerente manualmente.")
        opcoes.nth(indice).click()

    def _salvar(self, o_que: str):
        """Clica em Salvar e transforma o alerta de erro do painel (bootbox) em erro do item."""
        page = self.page
        page.locator(BOTAO_SALVAR).first.click()
        page.wait_for_load_state("domcontentloaded")
        modal = page.locator(MODAL_ERRO).first
        try:
            modal.wait_for(state="visible", timeout=1500)
        except PlaywrightTimeout:
            return
        texto = page.locator(MODAL_ERRO_TEXTO).first.inner_text()
        texto = " | ".join(linha.strip() for linha in texto.splitlines() if linha.strip())
        raise ErroAutomacao(f"O painel não salvou o {o_que}: {texto}")

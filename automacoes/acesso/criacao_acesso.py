from ..core.apex import aguardar_apex
from ..core.automacao_base import AutomacaoPorItem
from ..core.erros import ErroAutomacao
from .dados_infox import ler_dados_credenciado
from .painel_megavale import PainelMegavale


class CriacaoAcesso(AutomacaoPorItem):
    """Cria o acesso do credenciado no painel Megavale com os dados da Infox (automacao_criacao_acesso).

    Para cada credenciado: lê a tela da Infox (aba 1), confere no painel (aba 2) se o estabelecimento
    (pelo código Infox) e o gerente (pelo e-mail) já existem, e cria o que faltar. O gerente entra
    com login = e-mail e senha = código do credenciado, como na automação original.

    No modo "somente verificar", só lê e confere; nada é criado no painel.
    """

    nome = "criacao_acesso"
    prefixo_relatorio = "criacao_acesso"
    aba = "Criação de acesso"
    colunas = ["PESQUISADO", "CODIGO", "RAZAO_SOCIAL", "NOME_FANTASIA", "CNPJ", "EMAIL", "CEP", "CIDADE_UF",
               "ESTABELECIMENTO", "GERENTE", "RESULTADO"]

    def __init__(self, credenciais: dict, codigos: list[str], status, *, tipo_pesquisa: str = "COD",
                 somente_verificar: bool = False):
        super().__init__(credenciais, codigos, status)
        self.tipo_pesquisa = tipo_pesquisa.upper()
        self.somente_verificar = somente_verificar
        self.titulo = "Verificação de acessos" if somente_verificar else "Criação de acesso"
        self.aba_megavale = None
        self.painel: PainelMegavale | None = None
        self._linha: dict | None = None  # linha do item em andamento, para o erro sair com o que já foi feito

    def preparar(self):
        self.aba_megavale = self.navegador.nova_aba()
        self.painel = PainelMegavale(self.aba_megavale, self.status)
        self.painel.entrar(self.credenciais["login_megavale"], self.credenciais["senha_megavale"])
        if self.somente_verificar:
            self.status.log("Modo verificação: nada será criado no painel Megavale.")

    def processar_item(self, codigo: str):
        linha = self._linha = {"PESQUISADO": codigo}
        self.portal.ir_para_pesquisa_credenciado()
        self.portal.abrir_credenciado(codigo, self.tipo_pesquisa)
        aguardar_apex(self.page)
        dados = ler_dados_credenciado(self.ler)
        linha.update(CODIGO=dados.codigo, RAZAO_SOCIAL=dados.razao_social, NOME_FANTASIA=dados.nome_fantasia,
                     CNPJ=dados.cnpj, EMAIL=dados.email, CEP=dados.cep, CIDADE_UF=dados.cidade_uf)
        if not dados.codigo:
            raise ErroAutomacao("Não consegui ler o código do credenciado na tela da Infox.")
        faltando = dados.faltando()
        if faltando:
            self.status.log(f"Vazio na Infox: {', '.join(faltando)}.", "WARNING")

        if self.somente_verificar:
            self._verificar(linha, dados, faltando)
        else:
            self._criar(linha, dados)
        self._linha = None
        self.registrar(linha)

    def _verificar(self, linha: dict, dados, faltando: list[str]):
        linha["ESTABELECIMENTO"] = "Já existe" if self.painel.estabelecimento_existe(dados.codigo) else "Não existe"
        if dados.email:
            linha["GERENTE"] = "Já existe" if self.painel.gerente_existe(dados.email) else "Não existe"
        else:
            linha["GERENTE"] = "Sem e-mail na Infox"
        linha["RESULTADO"] = f"AVISO: vazio na Infox: {', '.join(faltando)}" if faltando else "OK"
        self.status.log(f"{dados.codigo}: estabelecimento {linha['ESTABELECIMENTO'].lower()}, "
                        f"gerente {linha['GERENTE'].lower()}.", "WARNING" if faltando else "SUCCESS")

    def _criar(self, linha: dict, dados):
        if not dados.email:
            raise ErroAutomacao("O credenciado não tem e-mail na Infox, e o e-mail é o login do gerente. "
                                "Nada foi criado; faça este manualmente.")
        estabelecimento_existe = self.painel.estabelecimento_existe(dados.codigo)
        gerente_existe = self.painel.gerente_existe(dados.email)
        if estabelecimento_existe and gerente_existe:
            linha.update(ESTABELECIMENTO="Já existia", GERENTE="Já existia", RESULTADO="OK (nada a fazer)")
            self.status.log(f"{dados.codigo}: estabelecimento e gerente já existiam no painel.")
            return

        avisos = []
        if estabelecimento_existe:
            linha["ESTABELECIMENTO"] = "Já existia"
        else:
            linha["ESTABELECIMENTO"] = "Erro ao criar"
            avisos += self.painel.cadastrar_estabelecimento(dados)
            linha["ESTABELECIMENTO"] = "Criado"
        if gerente_existe:
            linha["GERENTE"] = "Já existia"
        else:
            linha["GERENTE"] = "Erro ao criar"
            avisos += self.painel.cadastrar_gerente(dados)
            linha["GERENTE"] = "Criado"
        linha["RESULTADO"] = f"AVISO: {'; '.join(avisos)}" if avisos else "OK"
        self.status.log(f"{dados.codigo}: estabelecimento {linha['ESTABELECIMENTO'].lower()}, "
                        f"gerente {linha['GERENTE'].lower()}.", "WARNING" if avisos else "SUCCESS")

    def registrar_falha(self, codigo: str, mensagem: str):
        """A linha do erro leva o que já foi lido e feito (ex.: estabelecimento criado, gerente com erro)."""
        linha = self._linha if self._linha and self._linha.get("PESQUISADO") == codigo else {"PESQUISADO": codigo}
        self._linha = None
        linha["RESULTADO"] = f"ERRO: {mensagem}"
        self.registrar(linha)

    def capturar_erro(self, descricao: str):
        capturas = super().capturar_erro(descricao)
        if self.aba_megavale is not None:
            captura = self.navegador.capturar_tela(f"{descricao}_megavale", self.aba_megavale)
            if captura:
                capturas.append(captura)
        return capturas

import traceback
from pathlib import Path

from playwright.sync_api import Error as PlaywrightError

import config

from .apex import ler_valor
from .erros import ErroAutomacao, NavegadorFechado, resumo_do_erro
from .navegador import Navegador
from .portal_infox import PortalInfox
from .relatorio import salvar_tabela


class AutomacaoBase:
    """Ciclo de vida comum: abre o Chrome, entra no Infox, percorre os itens e gera o relatório.

    Cada automação herda desta classe e implementa:
      - processar_item(item): o trabalho de um item (credenciado);
      - preparar(): opcional, roda depois do login na Infox e antes do primeiro item;
      - registrar_falha(item, mensagem): opcional, para o item com erro aparecer no relatório;
      - gerar_relatorio(): opcional, devolve o caminho do .xlsx gerado.

    Um erro em um item é registrado e a execução segue para o próximo.
    Só param tudo: login que falha, Chrome fechado ou botão "parar".
    """

    nome = "automacao"   # perfil do Chrome e prefixo de logs/relatórios
    titulo = "Automação"

    def __init__(self, credenciais: dict, itens: list, status):
        self.credenciais = credenciais
        self.itens = itens
        self.status = status
        self.carimbo = status.carimbo  # o mesmo do ID da execução, que não repete entre execuções simultâneas
        self.navegador: Navegador | None = None
        self.portal: PortalInfox | None = None
        self.page = None
        self.motivo_parada = ""  # a automação pode parar sozinha (status.solicitar_parada()) e dizer o porquê aqui

    # --- pontos de extensão --------------------------------------------
    def processar_item(self, item):
        raise NotImplementedError

    def preparar(self):
        pass

    def descrever_item(self, item) -> str:
        return str(item)

    def capturar_erro(self, descricao: str) -> list[Path]:
        """Capturas de tela de um item com erro (por padrão, só a aba da Infox)."""
        captura = self.navegador.capturar_tela(descricao) if self.navegador else None
        return [captura] if captura else []

    def registrar_falha(self, item, mensagem: str):
        pass

    def gerar_relatorio(self) -> Path | None:
        return None

    # --- ciclo de vida -------------------------------------------------
    def executar(self):
        status = self.status
        status.iniciar(total=len(self.itens), titulo=self.titulo)
        status.log(f"{self.titulo} iniciada com {len(self.itens)} item(ns). Motor: Playwright.")
        try:
            with Navegador(self.nome, status, prefixo=f"{self.nome}_{self.carimbo}") as navegador:
                self.navegador = navegador
                self.page = navegador.page
                self.portal = PortalInfox(navegador.page, status)
                try:
                    self._entrar_e_percorrer(navegador)
                except Exception as erro:
                    navegador.houve_erro = True
                    self._registrar_erro_geral(erro)  # antes de fechar o Chrome, para a ordem dos logs
        except Exception as erro:  # falha ao abrir ou fechar o Chrome
            self._registrar_erro_geral(erro)
        finally:
            self._salvar_relatorio()
            status.finalizar()
            status.log(f"Concluído. Processados: {status.processados}/{status.total} | Tempo: {status.duracao()}")

    def _entrar_e_percorrer(self, navegador: Navegador):
        status = self.status
        self.portal.entrar(self.credenciais["login_infox"], self.credenciais["senha_infox"])
        self.preparar()
        for posicao, item in enumerate(self.itens, start=1):
            if status.parada_solicitada:
                if self.motivo_parada:
                    status.log(self.motivo_parada, "ERROR")
                else:
                    status.log("Interrupção solicitada pelo usuário.", "WARNING")
                break
            if not self._executar_item(posicao, item):
                navegador.houve_erro = True
            if not navegador.aberto:
                raise NavegadorFechado("O Chrome foi fechado durante a execução.")

    def _registrar_erro_geral(self, erro: Exception):
        if isinstance(erro, ErroAutomacao):
            self.status.log(str(erro), "ERROR")
        else:
            self.status.log(f"Erro crítico: {resumo_do_erro(erro)}", "ERROR")
            self.status.detalhe(traceback.format_exc())

    def _executar_item(self, posicao: int, item) -> bool:
        status = self.status
        descricao = self.descrever_item(item)
        status.definir_item_atual(descricao)
        status.log("─" * 40)
        status.log(f"[{posicao}/{len(self.itens)}] {descricao}")
        try:
            self.processar_item(item)
            return True
        except ErroAutomacao as erro:
            mensagem = str(erro)
        except Exception as erro:
            mensagem = resumo_do_erro(erro)
            status.detalhe(traceback.format_exc())
        finally:
            status.avancar()

        status.log(f"{descricao}: {mensagem}", "ERROR")
        for captura in self.capturar_erro(descricao):
            status.log(f"Captura da tela salva em logs/{captura.name}")
        self.registrar_falha(item, mensagem)
        return False

    def _salvar_relatorio(self):
        try:
            caminho = self.gerar_relatorio()
        except Exception as erro:
            self.status.log(f"Erro ao gerar o relatório: {resumo_do_erro(erro)}", "ERROR")
            self.status.detalhe(traceback.format_exc())
            return
        if caminho:
            self.status.definir_relatorio(caminho)
            self.status.log(f"Relatório gerado: {Path(caminho).name}", "SUCCESS")


class AutomacaoPorItem(AutomacaoBase):
    """Automação com uma linha de relatório por item, inclusive os que deram erro.

    O relatório é regravado em relatorios/ a cada item, para não perder o que foi feito se o portal
    cair (ou o painel for reiniciado) no meio de uma planilha grande. A coluna RESULTADO fica
    vermelha quando começa com ERRO ou AVISO.
    """

    prefixo_relatorio = "automacao"
    aba = "Relatório"
    colunas: list[str] = []
    coluna_pesquisa = "PESQUISADO"  # onde vai o código/CNPJ pesquisado nas linhas de erro

    def __init__(self, credenciais: dict, itens: list, status):
        super().__init__(credenciais, itens, status)
        self._linhas: list[dict] = []
        self._caminho = config.PASTA_RELATORIOS / f"{self.prefixo_relatorio}_{self.carimbo}.xlsx"

    def registrar(self, linha: dict):
        self._linhas.append(linha)
        try:
            self._gravar()
            self.status.definir_relatorio(self._caminho)
        except Exception as erro:
            self.status.log(f"Não consegui atualizar o relatório parcial: {resumo_do_erro(erro)}", "WARNING")

    def registrar_falha(self, item, mensagem: str):
        self.registrar({self.coluna_pesquisa: item, "RESULTADO": f"ERRO: {mensagem}"})

    def gerar_relatorio(self) -> Path | None:
        if not self._linhas:
            return None
        self._gravar()
        return self._caminho

    def _gravar(self):
        salvar_tabela(self._caminho, self.aba, self.colunas, self._linhas, coluna_resultado="RESULTADO")

    def ler(self, seletor: str, page=None) -> str:
        """Valor exibido de um campo da tela (aba principal, se `page` não for dada), ou vazio se não existir."""
        campo = (page or self.page).locator(seletor).first
        try:
            return ler_valor(campo) if campo.count() else ""
        except PlaywrightError:
            return ""

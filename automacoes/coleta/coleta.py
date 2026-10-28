import re
import traceback
from collections import defaultdict
from datetime import datetime
from typing import NamedTuple

from playwright.sync_api import TimeoutError as PlaywrightTimeout

from ..core import seletores as S
from ..core.apex import aguardar_apex
from ..core.automacao_base import AutomacaoPorItem
from ..core.erros import ErroAutomacao, resumo_do_erro
from ..core.texto import sem_acento_maiusculo
from ..habilitacao.rede_captura import RedeCaptura
from .relatorio_coleta import COLUNAS, gravar_relatorio_coleta

_ITEM_CODIGO_ESTABELECIMENTO = re.compile(r"c[oóOÓ]digo\s+(de\s+)?estabelecimento", re.IGNORECASE)

# Lê cada linha da tabela de Código Estabelecimento: o texto de cada célula (o do link, se houver)
_JS_LINHAS = """
tabela => [...tabela.querySelectorAll('tr')].map(tr =>
  [...tr.children].filter(c => c.tagName === 'TD').map(td => {
    const link = td.querySelector('a');
    const texto = link && link.innerText.trim() ? link.innerText : td.innerText;
    return (texto || '').trim();
  }))
"""

# Ordem das situações no resumo dos contratos, quando há empate na quantidade (a mesma da versão Selenium)
ORDEM_SITUACOES = [
    "APROVADO", "APROVADOS", "ATIVADO", "ATIVADOS", "ENVIADO", "ENVIADOS",
    "CANCELADO", "CANCELADOS", "CANCELADO NA ADM", "CANCELADO NA REDE",
    "DEFINICAO", "DEFINIÇÃO", "INATIVO", "INATIVOS", "DESATIVADO", "VAZIOS",
]
SITUACOES_INATIVAS = ("INATIVO", "INATIVOS")
ERRO_NA_LEITURA = "ERRO NA LEITURA"


class CodigoEstabelecimento(NamedTuple):
    origem: str = ""
    codigo: str = ""
    data_cadastro: str = ""
    data_alteracao: str = ""
    situacao: str = ""


class ResumoContratos(NamedTuple):
    total: int
    resumo: str
    detalhes: str


CONTRATOS_NAO_LIDOS = ResumoContratos(
    0, "Contratos não coletados - código inativo",
    "Contratos não foram acessados porque o código estabelecimento está inativo.",
)


def resumir_contratos(grupos: dict[str, list]) -> ResumoContratos:
    """{'ATIVADO': [1, 2, 4], 'CANCELADO NA REDE': [3]} -> 'ATIVADO: 3 | CANCELADO NA REDE: 1' e o detalhe por situação."""
    grupos = {situacao: numeros for situacao, numeros in grupos.items() if numeros}
    total = sum(len(numeros) for numeros in grupos.values())
    if not total:
        return ResumoContratos(0, "Nenhum contrato encontrado", "Nenhum contrato encontrado")

    ordenados = sorted(grupos.items(), key=lambda par: (-len(par[1]), _posicao_situacao(par[0])))
    resumo = " | ".join(f"{situacao}: {len(numeros)}" for situacao, numeros in ordenados)
    if len(ordenados) == 1:
        situacao, numeros = ordenados[0]
        if situacao in ("VAZIOS", "DESATIVADO"):
            return ResumoContratos(total, resumo, f"Todos os {len(numeros)} contratos ficaram desativados.")
        return ResumoContratos(total, resumo, f"Todos os {len(numeros)} contratos estão em {situacao}.")
    detalhes = "\n".join(f"{situacao} ({len(numeros)}): {', '.join(map(str, numeros))}" for situacao, numeros in ordenados)
    return ResumoContratos(total, resumo, detalhes)


def _posicao_situacao(situacao: str) -> tuple[int, str]:
    try:
        return ORDEM_SITUACOES.index(situacao), situacao
    except ValueError:
        return len(ORDEM_SITUACOES), situacao


class ColetaEstabelecimento(AutomacaoPorItem):
    """Para cada credenciado, lê o código de estabelecimento de uma origem de transação (ex.: CARDSE) e
    agrupa os contratos pela situação dessa rede na tabela "Rede de captura".

    Só lê, nunca altera nada no portal. Como na versão Selenium (cielo_cardse.py, modo coleta):
      - Opções > Cadastro > Código Estabelecimento: a linha da origem, com código, datas e situação;
      - código INATIVO: os contratos não são abertos;
      - senão, abre cada contrato e lê a situação do arquivo da rede.
    """

    nome = "coleta"
    titulo = "Coleta de código de estabelecimento"
    prefixo_relatorio = "coleta_codigo_estabelecimento"
    colunas = COLUNAS
    coluna_pesquisa = "Codigo Infox/CNPJ"

    def __init__(self, credenciais: dict, codigos: list[str], status, *, origem: str, tipo_pesquisa: str = "COD"):
        super().__init__(credenciais, codigos, status)
        self.origem = origem.strip()
        self.tipo_pesquisa = tipo_pesquisa.upper()
        self.titulo = f"Coleta de código de estabelecimento (origem {self.origem})"
        self._ocorrencias: list[str] = []
        self._ultima_parada = ""

    def processar_item(self, codigo: str):
        log = self.status.log
        self._ultima_parada = f"Em processamento: {codigo}"
        observacoes = []

        self.portal.ir_para_pesquisa_credenciado()
        resultados = self.portal.pesquisar_credenciado(codigo, self.tipo_pesquisa)
        if resultados:
            log(f"A pesquisa retornou {resultados} credenciado(s); abrindo o primeiro.",
                "WARNING" if resultados > 1 else "INFO")
            self.portal.abrir_resultado(0)
            if resultados > 1:
                observacoes.append(f"A pesquisa retornou {resultados} credenciados; coletado o primeiro da lista.")
        self.portal.conferir_credenciado(codigo, self.tipo_pesquisa, "Nada foi coletado.")
        aguardar_apex(self.page)

        estabelecimento = self._ler_codigo_estabelecimento(observacoes)
        if sem_acento_maiusculo(estabelecimento.situacao) in SITUACOES_INATIVAS:
            log("Código estabelecimento inativo; os contratos não serão abertos.")
            contratos = CONTRATOS_NAO_LIDOS
        else:
            contratos = self._ler_contratos(self.origem.upper(), observacoes)

        self.registrar({
            "Codigo Infox/CNPJ": codigo,
            "Origem de Transacao": estabelecimento.origem,
            "Codigo Estabelecimento": estabelecimento.codigo,
            "Data Cadastro": estabelecimento.data_cadastro,
            "Data Alteracao": estabelecimento.data_alteracao,
            "Situacao": estabelecimento.situacao,
            "Contratos Totais": contratos.total,
            "Resumo Contratos": contratos.resumo,
            "Detalhes Contratos": contratos.detalhes,
            "Observacao": " | ".join(observacoes),
        })
        self._ultima_parada = f"Concluído: {codigo}"
        log(f"{codigo}: {estabelecimento.origem or self.origem} = {estabelecimento.codigo or '—'} "
            f"({estabelecimento.situacao or 'sem situação'}) | contratos: {contratos.resumo}",
            "WARNING" if observacoes else "SUCCESS")

    # --- Código Estabelecimento (página 2118) --------------------------------
    def _ler_codigo_estabelecimento(self, observacoes: list[str]) -> CodigoEstabelecimento:
        self._abrir_codigo_estabelecimento()
        linhas = [celulas for celulas in self.page.locator(S.CODEST_TABELA).first.evaluate(_JS_LINHAS)
                  if len(celulas) >= 6]
        encontradas = self._linhas_da_origem(linhas)
        self._voltar_do_codigo_estabelecimento()

        if not encontradas:
            aviso = f"Origem '{self.origem}' não encontrada."
            self.status.log(f"{aviso} ({len(linhas)} linha(s) na tabela de Código Estabelecimento)", "WARNING")
            observacoes.append(aviso)
            return CodigoEstabelecimento()
        if len(encontradas) > 1:
            aviso = f"{len(encontradas)} linhas com a origem '{self.origem}'; coletada a primeira."
            self.status.log(aviso, "WARNING")
            observacoes.append(aviso)
        return encontradas[0]

    def _abrir_codigo_estabelecimento(self):
        """Opções > Cadastro > Código Estabelecimento."""
        page = self.page
        page.locator(S.DET_MENU_OPCOES).click()
        cadastro = page.locator(S.DET_MENU_CADASTRO)
        cadastro.click()
        item = page.locator(S.DET_MENU_LISTA).get_by_text(_ITEM_CODIGO_ESTABELECIMENTO).filter(visible=True).first
        try:
            item.wait_for(state="visible", timeout=5000)
        except PlaywrightTimeout:
            cadastro.hover()  # alguns menus do APEX abrem o submenu só com o mouse em cima
            try:
                item.wait_for(state="visible", timeout=5000)
            except PlaywrightTimeout:
                raise ErroAutomacao("O item \"Código Estabelecimento\" não apareceu no menu Opções > Cadastro.")
        item.click()
        page.locator(S.CODEST_TABELA).first.wait_for(state="attached")
        aguardar_apex(page)

    def _linhas_da_origem(self, linhas: list[list[str]]) -> list[CodigoEstabelecimento]:
        """Linhas cuja primeira célula com a origem é seguida de código, datas e situação.

        Como na versão Selenium, a origem vale se for igual ao texto procurado ou o contiver
        ("CARDSE" acha "CARDSE PRE"); as iguais vêm antes das que só contêm.
        """
        alvo = sem_acento_maiusculo(self.origem)
        iguais, contem = [], []
        for celulas in linhas:
            textos = [sem_acento_maiusculo(texto) for texto in celulas]
            posicao = next((i for i, texto in enumerate(textos) if texto and alvo in texto), None)
            if posicao is None:
                continue
            if posicao + 4 >= len(celulas):
                self.status.log(f"Linha ignorada, formato inesperado: {celulas}", "WARNING")
                continue
            linha = CodigoEstabelecimento(*celulas[posicao:posicao + 5])
            (iguais if textos[posicao] == alvo else contem).append(linha)
        return iguais + contem

    def _voltar_do_codigo_estabelecimento(self):
        page = self.page
        voltar = page.locator(S.CODEST_VOLTAR).or_(page.get_by_role("button", name="Voltar", exact=True))
        voltar.first.click()
        page.locator(S.DET_BTN_CONTRATOS).wait_for(state="visible")
        aguardar_apex(page)

    # --- contratos -------------------------------------------------------
    def _ler_contratos(self, rede: str, observacoes: list[str]) -> ResumoContratos:
        """Abre cada contrato e agrupa os números pela situação da rede (vazia = DESATIVADO).

        A rede é a origem digitada na tela, procurada pelo nome exato na tabela "Rede de captura"
        (a versão Selenium lia sempre a linha do CARDSE). Contrato sem essa rede entra como "SEM <rede>".
        """
        log = self.status.log
        linhas = self.portal.abrir_contratos()
        self.portal.garantir_ordem_crescente(linhas)
        total = linhas.count()
        log(f"{total} contrato(s) na lista; lendo a situação de {rede} em cada um...")

        leitor = RedeCaptura(self.page, log)
        grupos = defaultdict(list)
        for indice in range(total):
            if self.status.parada_solicitada:
                observacoes.append(f"Interrompido pelo usuário: {indice} de {total} contratos lidos.")
                log("Interrupção solicitada; parando antes do próximo contrato.", "WARNING")
                break
            linha = linhas.nth(indice)
            numero = self.portal.numero_contrato(linha) or indice + 1
            try:
                self.portal.abrir_contrato(linha)
                situacao = self._situacao(leitor, rede)
            except Exception as erro:
                if not self.navegador.aberto:
                    raise
                situacao = ERRO_NA_LEITURA
                self._registrar_erro_contrato(numero, erro, observacoes)
            grupos[situacao].append(numero)
            log(f"  Contrato {numero}: {situacao}")
            self.portal.voltar_para_lista_de_contratos()

        try:
            self.portal.voltar_para_credenciado()
        except PlaywrightTimeout:
            log("Não consegui voltar para a tela do credenciado (o próximo item recomeça pelo menu).", "WARNING")
        return resumir_contratos(grupos)

    @staticmethod
    def _situacao(leitor: RedeCaptura, rede: str) -> str:
        if not leitor.tem_rede(rede):
            return f"SEM {rede}"
        return leitor.situacao(rede).strip().upper() or "DESATIVADO"

    def _registrar_erro_contrato(self, numero, erro: Exception, observacoes: list[str]):
        mensagem = resumo_do_erro(erro)
        self.status.log(f"Contrato {numero}: {mensagem}", "ERROR")
        self.status.detalhe(traceback.format_exc())
        self.navegador.houve_erro = True
        captura = self.navegador.capturar_tela(f"contrato_{numero}")
        if captura:
            self.status.log(f"Captura da tela salva em logs/{captura.name}")
        observacoes.append(f"Contrato {numero} não foi lido: {mensagem}")

    # --- relatório ---------------------------------------------------------
    def registrar_falha(self, codigo: str, mensagem: str):
        self._ocorrencias.append(f"{codigo}: {mensagem}")
        self._ultima_parada = f"Erro em: {codigo}"
        self.registrar({"Codigo Infox/CNPJ": codigo, "Origem de Transacao": self.origem,
                        "Contratos Totais": 0, "Observacao": f"ERRO: {mensagem}"})

    def _gravar(self):
        parada = self._ultima_parada
        if self.status.parada_solicitada and len(self._linhas) < len(self.itens):
            parada = f"Interrompido pelo usuário. {parada}"
        resumo = [
            ("Gerado em", f"{datetime.now():%d/%m/%Y %H:%M:%S}"),
            ("Origem alvo", self.origem),
            ("Tipo de pesquisa", self.tipo_pesquisa),
            ("Processados", len(self._linhas)),
            ("Total previsto", len(self.itens)),
            ("Ultimo credenciado", self._linhas[-1]["Codigo Infox/CNPJ"] if self._linhas else ""),
            ("Ultimo ponto de parada", parada),
        ]
        gravar_relatorio_coleta(self._caminho, self._linhas, resumo, self._ocorrencias)

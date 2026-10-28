from playwright.sync_api import TimeoutError as PlaywrightTimeout

from ..core import seletores as S
from ..core.apex import aguardar_apex
from ..core.automacao_base import AutomacaoPorItem
from ..core.erros import ErroAutomacao
from ..core.texto import sem_acento_maiusculo
from .item_taxa import ItemTaxa
from .plano_compra import PlanoCompra

LIMITE_ERROS_SEGUIDOS = 3


class AlteracaoTaxa(AutomacaoPorItem):
    """Ajusta o plano de compra (taxa de reembolso, periodicidade, dias, bancarização) de todos os contratos
    de cada credenciado.

    Regras da versão Selenium (alt_taxa.py):
      - contrato BLOQUEADO é pulado;
      - com plano de compra, altera o primeiro da lista; sem plano, cria um "A VISTA";
      - depois de salvar, contrato em DEFINIÇÃO é aprovado (Opções > Aprovar). Se continuar APROVADO,
        o plano não mudou e não precisa aprovar.
    Diferenças:
      - o credenciado é conferido antes (lista de resultados ou outro credenciado = erro, nada é alterado);
      - um erro num contrato encerra aquele credenciado (os contratos seguintes não são mexidos) e a execução
        segue para o próximo. O Selenium parava a planilha inteira. Aqui, só depois de LIMITE_ERROS_SEGUIDOS
        credenciados seguidos com erro depois de abertos, que indica um problema geral;
      - cada campo do plano é conferido antes de salvar, e o estado é conferido depois de aprovar;
      - relatório com uma linha por contrato, regravado a cada contrato.
    """

    nome = "taxa"
    titulo = "Alteração de taxas"
    prefixo_relatorio = "taxa"
    aba = "Taxas"
    colunas = ["CREDENCIADO", "FANTASIA", "CONTRATO", "PRODUTO", "ESTADO_ANTES", "PLANO", "APROVADO_PELO_ROBO",
               "PEDIDO", "RESULTADO"]
    coluna_pesquisa = "CREDENCIADO"

    def __init__(self, credenciais: dict, itens: list[ItemTaxa], status, *, tipo_pesquisa: str = "COD"):
        super().__init__(credenciais, itens, status)
        self.tipo_pesquisa = tipo_pesquisa.upper()
        self._contrato: dict | None = None    # linha do contrato em andamento, para o erro sair nela
        self._restantes = 0                   # contratos que ficaram sem processar se o atual der erro
        self._abriu_credenciado = False
        self._erros_seguidos = 0

    def descrever_item(self, item: ItemTaxa) -> str:
        return item.codigo

    # --- credenciado -----------------------------------------------------
    def processar_item(self, item: ItemTaxa):
        log = self.status.log
        self._abriu_credenciado = False
        self._contrato = None
        log(f"Pedido: {item.resumo()}")
        self.portal.ir_para_pesquisa_credenciado()
        self.portal.abrir_credenciado(item.codigo, self.tipo_pesquisa)
        self._abriu_credenciado = True
        aguardar_apex(self.page)
        fantasia = self.ler(S.DET_FANTASIA)

        linhas = self.portal.abrir_contratos()
        self.portal.garantir_ordem_crescente(linhas)
        total = linhas.count()
        log(f"{total} contrato(s) na lista.")
        contagem = {"OK": 0, "AVISO": 0, "Pulado": 0}
        for indice in range(total):
            if self.status.parada_solicitada:
                log("Interrupção solicitada; parando antes do próximo contrato.", "WARNING")
                break
            linha = linhas.nth(indice)
            numero = self.portal.numero_contrato(linha) or indice + 1
            produto = self.portal.produto_contrato(linha)
            self._restantes = total - indice - 1
            self._contrato = {"CREDENCIADO": item.codigo, "FANTASIA": fantasia, "CONTRATO": numero,
                              "PRODUTO": produto, "PEDIDO": item.resumo()}
            log(f"Contrato #{numero}: {produto}")
            self.portal.abrir_contrato(linha)
            contagem[self._alterar_contrato(item, self._contrato)] += 1
            self.registrar(self._contrato)
            self._contrato = None
            self.portal.voltar_para_lista_de_contratos()

        try:
            self.portal.voltar_para_credenciado()
        except PlaywrightTimeout:
            log("Não consegui voltar para a tela do credenciado (o próximo item recomeça pelo menu).", "WARNING")
        self._erros_seguidos = 0
        if total == 0:
            self.registrar({"CREDENCIADO": item.codigo, "FANTASIA": fantasia, "PEDIDO": item.resumo(),
                            "RESULTADO": "AVISO: nenhum contrato na lista"})
        log(f"Credenciado {item.codigo} concluído: {contagem['OK']} contrato(s) alterado(s), {contagem['AVISO']} com aviso, "
            f"{contagem['Pulado']} pulado(s).", "WARNING" if contagem["AVISO"] or not total else "SUCCESS")

    # --- contrato --------------------------------------------------------
    def _alterar_contrato(self, item: ItemTaxa, linha: dict) -> str:
        """Altera (ou cria) o plano do contrato aberto, aprova se precisar e preenche o resultado na linha.

        Devolve 'OK', 'AVISO' ou 'Pulado'. Levanta ErroAutomacao se não conseguiu salvar.
        """
        log, page = self.status.log, self.page
        estado = self.portal.estado_contrato()
        if estado is None:
            raise ErroAutomacao("Não encontrei o estado do contrato na tela (P2111_ESTADO). Nada foi alterado nele.")
        linha["ESTADO_ANTES"] = estado
        if sem_acento_maiusculo(estado) == "BLOQUEADO":
            linha.update(PLANO="—", APROVADO_PELO_ROBO="Não", RESULTADO="Pulado: contrato BLOQUEADO")
            log("  Contrato BLOQUEADO; pulando sem alterar.", "WARNING")
            return "Pulado"

        observacoes = []
        try:
            page.locator(S.CONTRATO_PLANOS).first.wait_for(state="attached", timeout=5000)
        except PlaywrightTimeout:
            raise ErroAutomacao("A tabela de planos de compra não apareceu no contrato. Nada foi alterado nele.")
        planos = page.locator(S.CONTRATO_PLANO_LINKS)
        quantidade = planos.count()
        plano = PlanoCompra(page, log)
        if quantidade:
            if quantidade > 1:
                observacoes.append(f"o contrato tem {quantidade} planos; alterado o primeiro")
            log("  Alterando o plano de compra existente...")
            linha["PLANO"] = "Alteração não concluída"
            planos.first.click()
            plano.aguardar()
            observacoes += plano.preencher(item, novo=False)
            plano.salvar_existente()
            feito = "Alterado"
        else:
            log("  Contrato sem plano de compra; criando um A VISTA...")
            linha["PLANO"] = "Criação não concluída"
            page.locator(S.BOTAO_NOVO).click()
            plano.aguardar()
            plano.escolher_a_vista()
            observacoes += plano.preencher(item, novo=True)
            plano.salvar_novo()
            feito = "Criado"
        self._aguardar_volta_ao_contrato()
        linha["PLANO"] = feito

        depois = self.portal.estado_contrato() or ""
        aviso = ""
        if sem_acento_maiusculo(depois) == "DEFINICAO":
            log("  Contrato em DEFINIÇÃO; aprovando...")
            self.portal.aprovar_contrato()
            linha["APROVADO_PELO_ROBO"] = "Sim"
            final = self.portal.estado_contrato() or ""
            if sem_acento_maiusculo(final) != "APROVADO":
                aviso = f"depois de aprovar, o contrato ficou '{final or 'sem estado'}'"
        else:
            linha["APROVADO_PELO_ROBO"] = "Não"
            log(f"  Estado depois de salvar: {depois or '—'}; não precisa aprovar.")

        detalhe = f" ({'; '.join(observacoes)})" if observacoes else ""
        if aviso:
            linha["RESULTADO"] = f"AVISO: {aviso}{detalhe}"
            log(f"  {linha['RESULTADO']}", "WARNING")
            return "AVISO"
        linha["RESULTADO"] = f"OK{detalhe}"
        log(f"  Plano {feito.lower()}{detalhe}.", "SUCCESS")
        return "OK"

    def _aguardar_volta_ao_contrato(self):
        """Depois de salvar, o portal volta para o detalhe do contrato; se não voltar, traz a mensagem de erro."""
        try:
            self.page.locator(S.CONTRATO_REDE_CAPTURA).wait_for(state="attached")
        except PlaywrightTimeout:
            erro = self.portal.mensagem_de_erro()
            raise ErroAutomacao(f"O portal não salvou o plano de compra: {erro}" if erro else
                                "Depois de salvar o plano, o portal não voltou para o contrato. Confira o plano no portal.")
        aguardar_apex(self.page)

    # --- falhas ------------------------------------------------------------
    def registrar_falha(self, item: ItemTaxa, mensagem: str):
        """Erro num contrato sai na linha dele; os contratos seguintes do credenciado não foram mexidos."""
        if self._contrato is not None:
            linha, self._contrato = self._contrato, None
            if self._restantes:
                mensagem = (f"{mensagem.rstrip('.')}. Os {self._restantes} contrato(s) seguinte(s) deste credenciado "
                            "não foram alterados.")
        else:
            linha = {"CREDENCIADO": item.codigo, "PEDIDO": item.resumo()}
        linha["RESULTADO"] = f"ERRO: {mensagem}"
        self.registrar(linha)
        self._contar_erro_seguido()

    def _contar_erro_seguido(self):
        """Erros depois de abrir o credenciado, um atrás do outro, indicam problema geral: para a execução."""
        if not self._abriu_credenciado:
            return
        self._erros_seguidos += 1
        if self._erros_seguidos >= LIMITE_ERROS_SEGUIDOS and not self.status.parada_solicitada:
            self.motivo_parada = (
                f"{LIMITE_ERROS_SEGUIDOS} credenciados seguidos deram erro depois de abertos; a execução parou para "
                "não deixar mais planos pela metade. Confira o relatório e o portal antes de rodar o restante."
            )
            self.status.solicitar_parada()

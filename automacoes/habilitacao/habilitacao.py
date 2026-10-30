import traceback
from pathlib import Path
from typing import NamedTuple

from playwright.sync_api import TimeoutError as PlaywrightTimeout

import config

from ..core.automacao_base import AutomacaoBase
from ..core.erros import resumo_do_erro
from ..core.texto import sem_acento_maiusculo
from .item_habilitacao import ItemHabilitacao
from .rede_captura import RedeCaptura
from .relatorios import gerar_relatorio_habilitacao, gerar_relatorio_verificacao

OBSERVACAO_APROVACAO = "Ativação realizada por bot"


class ResultadoRede(NamedTuple):
    alterou: bool
    mensagem: str
    aviso: bool = False


class Habilitacao(AutomacaoBase):
    """Ativa/desativa CIELO e CARDSE nos contratos de cada credenciado, ou só lê (modo verificação).

    Regras (as da versão Selenium em automacoes/cielo_cardse.py, que filtrava a situação só no CARDSE):
      - Contrato em DEFINIÇÃO é aprovado antes (Opções > Aprovar).
      - ATIVAR com a rede já habilitada, ou DESATIVAR com ela já desabilitada: nada a fazer.
      - CIELO e CARDSE só são desativados se a situação estiver entre as marcadas na tela
        (situacoes_desativar). Com ENVIADO, o link é "Desfazer" em vez de "Desabilitar".
        Se depois do primeiro clique a rede continuar habilitada e a situação tiver mudado para
        outra também marcada, clica de novo (CARDSE ENVIADO -> ATIVADO). Se nada mudou, não repete.
      - produto_inicio pula contratos de número menor; produto_unico processa só aquele produto.
      - O modo verificação lê todos os contratos, sem filtros e sem alterar nada.
    """

    nome = "habilitacao"

    def __init__(self, credenciais: dict, itens: list[ItemHabilitacao], status, *,
                 tipo_pesquisa: str = "COD", modo_verificacao: bool = False,
                 produto_inicio: int = 1, situacoes_desativar=()):
        super().__init__(credenciais, itens, status)
        self.tipo_pesquisa = tipo_pesquisa.upper()
        self.modo_verificacao = modo_verificacao
        self.produto_inicio = max(1, int(produto_inicio or 1))
        self.situacoes_desativar = {sem_acento_maiusculo(s) for s in situacoes_desativar if str(s).strip()}
        self.titulo = "Verificação CIELO/CARDSE" if modo_verificacao else "Habilitação CIELO/CARDSE"
        self._linhas_relatorio: list[dict] = []   # ativação: uma linha por contrato
        self._verificacao: list[dict] = []        # verificação: um bloco por credenciado
        self._aviso_capturado = False             # só o primeiro aviso da execução gera captura de tela

    def descrever_item(self, item: ItemHabilitacao) -> str:
        return item.codigo

    # --- credenciado ---------------------------------------------------
    def processar_item(self, item: ItemHabilitacao):
        log = self.status.log
        if self.modo_verificacao:
            log("Modo verificação: nada será alterado.")
        else:
            log(f"Tecnologia: {item.tecnologia} | CIELO: {item.acao_cielo} | CARDSE: {item.acao_cardse}")
            if item.produto_unico:
                log(f"Somente o produto '{item.produto_unico}'.")
            if self.produto_inicio > 1:
                log(f"Pulando contratos com número menor que {self.produto_inicio}.")

        self.portal.ir_para_pesquisa_credenciado()
        self.portal.abrir_credenciado(item.codigo, self.tipo_pesquisa)
        linhas = self.portal.abrir_contratos()
        self.portal.garantir_ordem_crescente(linhas)
        total = linhas.count()
        log(f"{total} contrato(s) na lista.")

        rede = RedeCaptura(self.page, log)
        produtos_lidos = self._bloco_verificacao(item)["produtos"] if self.modo_verificacao else None
        contagem = {"alterado": 0, "aviso": 0, "sem_mudanca": 0}

        for indice in range(total):
            if self.status.parada_solicitada:
                log("Interrupção solicitada; parando antes do próximo contrato.", "WARNING")
                break
            linha = linhas.nth(indice)
            numero = self.portal.numero_contrato(linha) or indice + 1
            produto = self.portal.produto_contrato(linha)

            if not self.modo_verificacao and self._pular(item, numero, produto):
                continue

            try:
                self.portal.abrir_contrato(linha)
                if self.modo_verificacao:
                    produtos_lidos.append(self._ler_contrato(rede, numero, produto))
                else:
                    contagem[self._habilitar_contrato(rede, item, numero, produto)] += 1
            except Exception as erro:
                if not self.navegador.aberto:
                    raise
                self._registrar_erro_contrato(item, numero, produto, erro, produtos_lidos)
            self.portal.voltar_para_lista_de_contratos()

        try:
            self.portal.voltar_para_credenciado()
        except PlaywrightTimeout:
            log("Não consegui voltar para a tela do credenciado (o próximo item recomeça pelo menu).", "WARNING")

        if self.modo_verificacao:
            log(f"{len(produtos_lidos)} contrato(s) lidos de {item.codigo}.", "SUCCESS")
        else:
            log(
                f"Credenciado {item.codigo} concluído: {contagem['alterado']} alterado(s), "
                f"{contagem['aviso']} com aviso, {contagem['sem_mudanca']} sem mudança.",
                "WARNING" if contagem["aviso"] else "SUCCESS",
            )

    def _pular(self, item: ItemHabilitacao, numero: int, produto: str) -> bool:
        if numero < self.produto_inicio:
            self.status.log(f"  Pulando contrato #{numero} {produto} (início configurado: #{self.produto_inicio})")
            return True
        if item.produto_unico and produto.strip().upper() != item.produto_unico.strip().upper():
            self.status.log(f"  Pulando contrato #{numero} {produto} (não é '{item.produto_unico}')")
            return True
        return False

    # --- contrato: verificação -------------------------------------------
    def _ler_contrato(self, rede: RedeCaptura, numero: int, produto: str) -> dict:
        leitura = {
            "num": numero,
            "nome": produto,
            "cielo_sit": rede.situacao("CIELO") or "—",
            "cielo_hab": rede.habilitado("CIELO") or "—",
            "cardse_sit": rede.situacao("CARDSE") or "—",
            "cardse_hab": rede.habilitado("CARDSE") or "—",
            "obs": "",
        }
        self.status.log(
            f"  #{numero} {produto} | CIELO: {leitura['cielo_hab']} ({leitura['cielo_sit']}) "
            f"| CARDSE: {leitura['cardse_hab']} ({leitura['cardse_sit']})"
        )
        return leitura

    # --- contrato: ativação/desativação ------------------------------------
    def _habilitar_contrato(self, rede: RedeCaptura, item: ItemHabilitacao, numero: int, produto: str) -> str:
        """Aplica as regras no contrato aberto. Retorna 'alterado', 'aviso' ou 'sem_mudanca'."""
        self.status.log(f"Contrato #{numero}: {produto}")
        aprovado = self._aprovar_se_necessario()
        antes = {nome: rede.resumo(nome) for nome in ("CIELO", "CARDSE")}

        resultados = []
        if item.usa_cielo:
            resultados.append(self._aplicar(rede, "CIELO", item.acao_cielo))
        if item.usa_cardse:
            resultados.append(self._aplicar(rede, "CARDSE", item.acao_cardse))

        alterou = any(r.alterou for r in resultados)
        aviso = any(r.aviso for r in resultados)
        mensagem = "; ".join(r.mensagem for r in resultados)
        if aviso:
            mensagem = f"AVISO: {mensagem}"
            self.status.log(f"Contrato #{numero}: {mensagem}", "WARNING")
            self._capturar_primeiro_aviso(item, numero)
        elif alterou:
            self.status.log(f"Contrato #{numero} '{produto}': {mensagem}", "SUCCESS")
        else:
            self.status.log(f"Contrato #{numero}: {mensagem}")

        self._linhas_relatorio.append({
            "Credenciado": item.codigo,
            "Contrato": numero,
            "Produto": produto,
            "Aprovado pelo robô": "Sim" if aprovado else "Não",
            "CIELO antes": antes["CIELO"],
            "CIELO depois": rede.resumo("CIELO"),
            "CARDSE antes": antes["CARDSE"],
            "CARDSE depois": rede.resumo("CARDSE"),
            "Resultado": mensagem,
        })
        if aviso:
            return "aviso"
        return "alterado" if alterou else "sem_mudanca"

    def _capturar_primeiro_aviso(self, item: ItemHabilitacao, numero: int):
        if self._aviso_capturado:
            return
        self._aviso_capturado = True
        captura = self.navegador.capturar_tela(f"{item.codigo}_aviso_contrato_{numero}")
        if captura:
            self.status.log(f"Captura da tela do primeiro aviso salva em logs/{captura.name}")

    def _aplicar(self, rede: RedeCaptura, nome: str, acao: str) -> ResultadoRede:
        habilitada = rede.esta_habilitada(nome)
        self.status.log(f"  {nome}: {rede.resumo(nome)} | ação: {acao}")

        if acao == "ATIVAR":
            if habilitada:
                return ResultadoRede(False, f"{nome} já estava habilitado")
            if rede.habilitar(nome):
                return ResultadoRede(True, f"{nome} habilitado")
            return ResultadoRede(
                True,
                f"{nome}: cliquei em habilitar, mas o SIM não apareceu a tempo (agora: {rede.resumo(nome)})",
                aviso=True,
            )

        if not habilitada:
            return ResultadoRede(False, f"{nome} já estava desabilitado")
        return self._desabilitar(rede, nome)

    def _desabilitar(self, rede: RedeCaptura, nome: str) -> ResultadoRede:
        situacao = rede.situacao(nome)
        if not self._situacao_permitida(situacao):
            return ResultadoRede(
                False, f"{nome} mantido: situação '{situacao or 'vazia'}' não está marcada para desativar"
            )
        if rede.desabilitar(nome):
            return ResultadoRede(True, f"{nome} desabilitado")

        nova_situacao = rede.situacao(nome)
        if not rede.esta_habilitada(nome):
            return ResultadoRede(True, f"{nome} desabilitado")
        if nova_situacao == situacao:
            # Não repete: com ENVIADO o link é "Desfazer", e o portal avisa que desfazer invalida o arquivo enviado.
            return ResultadoRede(
                True, f"{nome}: cliquei e confirmei, mas a linha não mudou (agora: {rede.resumo(nome)})", aviso=True
            )
        if not self._situacao_permitida(nova_situacao):
            return ResultadoRede(
                True,
                f"{nome} continua habilitado; situação passou para '{nova_situacao}', que não está marcada",
                aviso=True,
            )

        self.status.log(f"  {nome} continua habilitado (situação agora: {nova_situacao}); desabilitando de novo.")
        if rede.desabilitar(nome):
            return ResultadoRede(True, f"{nome} desabilitado em 2 cliques (situação passou para {nova_situacao})")
        return ResultadoRede(
            True, f"{nome}: continuou SIM depois de 2 cliques em desabilitar (agora: {rede.resumo(nome)})", aviso=True
        )

    def _situacao_permitida(self, situacao: str) -> bool:
        situacao = sem_acento_maiusculo(situacao)
        return any(permitida in situacao for permitida in self.situacoes_desativar)

    def _aprovar_se_necessario(self) -> bool:
        estado = self.portal.estado_contrato()
        if estado is None:
            self.status.log("Estado do contrato não encontrado na tela; seguindo sem aprovar.", "WARNING")
            return False
        if sem_acento_maiusculo(estado) != "DEFINICAO":
            return False

        self.status.log("  Contrato em DEFINIÇÃO; aprovando...")
        self.portal.aprovar_contrato(OBSERVACAO_APROVACAO)
        self.status.log("  Contrato aprovado.", "SUCCESS")
        return True

    # --- falhas e relatório ------------------------------------------------
    def _bloco_verificacao(self, item: ItemHabilitacao) -> dict:
        if not self._verificacao or self._verificacao[-1]["cod"] != item.codigo:
            self._verificacao.append({"cod": item.codigo, "produtos": []})
        return self._verificacao[-1]

    def _registrar_erro_contrato(self, item, numero, produto, erro, produtos_lidos):
        mensagem = resumo_do_erro(erro)
        self.status.log(f"Contrato #{numero} '{produto}': {mensagem}", "ERROR")
        self.status.detalhe(traceback.format_exc())
        self.navegador.houve_erro = True
        captura = self.navegador.capturar_tela(f"{item.codigo}_contrato_{numero}")
        if captura:
            self.status.log(f"Captura da tela salva em logs/{captura.name}")

        if produtos_lidos is not None:
            produtos_lidos.append({"num": numero, "nome": produto, "obs": f"ERRO: {mensagem}"})
        else:
            self._linhas_relatorio.append({
                "Credenciado": item.codigo, "Contrato": numero, "Produto": produto,
                "Resultado": f"ERRO: {mensagem}",
            })

    def registrar_falha(self, item: ItemHabilitacao, mensagem: str):
        if self.modo_verificacao:
            self._bloco_verificacao(item)["produtos"].append(
                {"num": "—", "nome": "Erro no credenciado", "obs": f"ERRO: {mensagem}"}
            )
        else:
            self._linhas_relatorio.append({
                "Credenciado": item.codigo, "Contrato": "—", "Resultado": f"ERRO: {mensagem}",
            })

    def gerar_relatorio(self) -> Path | None:
        if self.modo_verificacao:
            if not self._verificacao:
                return None
            caminho = config.PASTA_RELATORIOS / f"verificacao_{self.carimbo}.xlsx"
            gerar_relatorio_verificacao(self._verificacao, caminho)
            return caminho
        if not self._linhas_relatorio:
            return None
        caminho = config.PASTA_RELATORIOS / f"habilitacao_{self.carimbo}.xlsx"
        gerar_relatorio_habilitacao(self._linhas_relatorio, caminho)
        return caminho

"""Planilha do ativador: uma linha por credenciado, com tecnologia, ações e produto opcionais."""
from typing import NamedTuple

from ..core.planilha import ColunaModelo, PlanilhaInvalida, coluna_codigo, ler_linhas, lista_de_opcoes, montar_modelo
from ..core.texto import normalizar_codigo_pesquisa, sem_acento_maiusculo
from .item_habilitacao import ACOES, TECNOLOGIAS, ItemHabilitacao

OPCOES = {"TECNOLOGIA": TECNOLOGIAS, "ACAO_CIELO": ACOES, "ACAO_CARDSE": ACOES}  # colunas com lista fechada
ERROS_NA_MENSAGEM = 5


class LeituraPlanilha(NamedTuple):
    itens: list[ItemHabilitacao]
    linhas_sem_codigo: int


def ler_itens(arquivo, tipo_pesquisa: str, padrao: dict) -> LeituraPlanilha:
    """Monta um ItemHabilitacao por linha da planilha.

    `padrao` tem tecnologia, acao_cielo, acao_cardse e produto_unico escolhidos na tela.
    Coluna ausente ou célula vazia usa esse padrão. Valor inválido (ex.: ACAO_CIELO = 'DESATIVA')
    recusa a planilha inteira com o número da linha, em vez de cair no padrão como na versão Selenium.
    """
    colunas, linhas = ler_linhas(arquivo)
    coluna = coluna_codigo(colunas)

    itens, erros, sem_codigo = [], [], 0
    for numero, linha in linhas:
        codigo = linha.get(coluna, "")
        if not codigo:
            sem_codigo += 1
            continue
        try:
            itens.append(ItemHabilitacao(
                codigo=normalizar_codigo_pesquisa(codigo, tipo_pesquisa),
                tecnologia=_opcao(linha, "TECNOLOGIA", padrao["tecnologia"]),
                acao_cielo=_opcao(linha, "ACAO_CIELO", padrao["acao_cielo"]),
                acao_cardse=_opcao(linha, "ACAO_CARDSE", padrao["acao_cardse"]),
                produto_unico=linha.get("PRODUTO") or padrao["produto_unico"],
            ))
        except ValueError as erro:
            erros.append(f"linha {numero}: {erro}")

    if erros:
        resumo = "; ".join(erros[:ERROS_NA_MENSAGEM])
        if len(erros) > ERROS_NA_MENSAGEM:
            resumo += f"; e mais {len(erros) - ERROS_NA_MENSAGEM} linha(s)"
        raise PlanilhaInvalida(f"A planilha não foi iniciada: {len(erros)} linha(s) com valor inválido ({resumo}).")
    if not itens:
        raise PlanilhaInvalida(f"Nenhum código preenchido na coluna {coluna}.")
    return LeituraPlanilha(itens, sem_codigo)


def _opcao(linha: dict, coluna: str, padrao: str) -> str:
    original = linha.get(coluna, "")
    valor = sem_acento_maiusculo(original)
    if not valor:
        return padrao
    if valor not in OPCOES[coluna]:
        raise ValueError(f"{coluna} '{original}' inválido, use {lista_de_opcoes(OPCOES[coluna])}")
    return valor


# --- planilha modelo -------------------------------------------------------------
COLUNAS_MODELO = [
    ColunaModelo("COD", 18, "Obrigatório. Código, CPF ou CNPJ do credenciado. O tipo de pesquisa é escolhido na "
                            "tela e vale para todas as linhas.", papel="obrigatoria"),
    ColunaModelo("PRODUTO", 28, "Opcional. Nome exato do produto: só esse contrato é alterado. Vazio = valor da tela."),
    ColunaModelo("TECNOLOGIA", 15, f"Opcional. {lista_de_opcoes(TECNOLOGIAS)}. Vazio = valor da tela.",
                 opcoes=TECNOLOGIAS),
    ColunaModelo("ACAO_CIELO", 15, f"Opcional. {lista_de_opcoes(ACOES)}. Vazio = valor da tela.", opcoes=ACOES),
    ColunaModelo("ACAO_CARDSE", 15, f"Opcional. {lista_de_opcoes(ACOES)}. Vazio = valor da tela.", opcoes=ACOES),
    ColunaModelo("FANTASIA", 28, "Opcional e ignorada pelo robô. Use para se organizar.", papel="ignorada"),
]

REGRAS = [
    ("COD", "Sim", "Código, CPF ou CNPJ", "A linha é pulada"),
    ("PRODUTO", "Não", "Nome exato do produto", "Usa o \"Produto único\" da tela (vazio = todos os contratos)"),
    ("TECNOLOGIA", "Não", lista_de_opcoes(TECNOLOGIAS), "Usa a tecnologia escolhida na tela"),
    ("ACAO_CIELO", "Não", lista_de_opcoes(ACOES), "Usa a ação de CIELO escolhida na tela"),
    ("ACAO_CARDSE", "Não", lista_de_opcoes(ACOES), "Usa a ação de CARDSE escolhida na tela"),
    ("FANTASIA", "Não", "Qualquer texto", "É ignorada pelo robô"),
]

EXEMPLO = [
    ("12345", "ALIMENTACAO PRIVADO", "CIELO", "ATIVAR", "", "LOJA ABC"),
    ("67890", "", "CARDSE", "", "DESATIVAR", "MERCADO XYZ"),
    ("11111", "BNDES", "AMBOS", "ATIVAR", "DESATIVAR", "PADARIA TAL"),
    ("22222", "", "", "", "", "SUPERMERCADO (tudo vazio = valores da tela)"),
]


def gerar_modelo() -> bytes:
    """Planilha do ativador pronta para preencher (colunas, listas de valores e instruções)."""
    return montar_modelo(
        COLUNAS_MODELO,
        titulo="Planilha do Ativador CIELO/CARDSE",
        avisos=["Um valor fora da lista recusa a planilha inteira, e a tela mostra a linha com problema. "
                "Nada é executado até corrigir."],
        regras=REGRAS,
        exemplo=EXEMPLO,
    )

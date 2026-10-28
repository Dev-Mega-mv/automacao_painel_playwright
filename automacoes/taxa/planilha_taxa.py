"""Planilha de taxas: uma linha por credenciado, com o plano de compra; célula vazia usa o valor da tela."""
from typing import NamedTuple

from ..core.planilha import ColunaModelo, PlanilhaInvalida, coluna_codigo, ler_linhas, lista_de_opcoes, montar_modelo, primeira_coluna
from ..core.texto import normalizar_codigo_pesquisa
from .item_taxa import BANCARIZAR, DIAS_SEMANA, PERIODICIDADES, TIPOS_DIA, ItemTaxa

# Campo do ItemTaxa -> colunas aceitas (as mesmas da versão Selenium; o cabeçalho já vem sem acento e com _)
COLUNAS = {
    "taxa": ("TAXA", "TAXA_REEMBOLSO", "TAXA_(%)", "TAXA_%"),
    "periodicidade": ("PERIODICIDADE",),
    "pag_dias": ("PAG", "PAG_DIAS", "DIAS_PAGAMENTO", "PAGAMENTO_DIAS"),
    "dia1": ("DIA1", "DIA_1"),
    "dia2": ("DIA2", "DIA_2"),
    "bancarizar": ("BANCARIZAR",),
    "tipo_dia": ("TIPO_DIA",),
}
COLUNAS_DIAS = ("DIAS_SEMANA",) + tuple(f"DIA_SEM{n}" for n in range(1, 8))
ERROS_NA_MENSAGEM = 5


class LeituraPlanilha(NamedTuple):
    itens: list[ItemTaxa]
    linhas_sem_codigo: int


def ler_itens(arquivo, tipo_pesquisa: str, padrao: dict) -> LeituraPlanilha:
    """Monta um ItemTaxa por linha. `padrao` tem os campos do plano escolhidos na tela.

    Coluna ausente ou célula vazia usa o padrão. Um valor inválido recusa a planilha inteira, com o número
    da linha, antes de abrir o Chrome. Dias da semana: DIAS_SEMANA ("SEGUNDA;QUARTA") ou DIA_SEM1 a DIA_SEM7.
    """
    colunas, linhas = ler_linhas(arquivo)
    coluna = coluna_codigo(colunas)
    nomes = {campo: primeira_coluna(colunas, apelidos) for campo, apelidos in COLUNAS.items()}

    itens, erros, sem_codigo = [], [], 0
    for numero, linha in linhas:
        codigo = linha.get(coluna, "")
        if not codigo:
            sem_codigo += 1
            continue
        valores = dict(padrao)
        valores.update({campo: linha[nome] for campo, nome in nomes.items() if nome and linha.get(nome)})
        dias = [linha.get(nome, "") for nome in COLUNAS_DIAS if linha.get(nome)]
        if dias:
            valores["dias_semana"] = ";".join(dias)
        try:
            itens.append(ItemTaxa(codigo=normalizar_codigo_pesquisa(codigo, tipo_pesquisa), **valores))
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


# --- planilha modelo -------------------------------------------------------------
VAZIO = "Vazio = valor da tela."
COLUNAS_MODELO = [
    ColunaModelo("COD", 18, "Obrigatório. Código, CPF ou CNPJ do credenciado. O tipo de pesquisa é escolhido na "
                            "tela e vale para todas as linhas.", papel="obrigatoria"),
    ColunaModelo("TAXA", 10, f"Opcional. Taxa de reembolso, ex.: 1,50 (digite como texto, sem %). {VAZIO} "
                             "Vazia aqui e na tela = mantém a taxa de cada contrato."),
    ColunaModelo("PERIODICIDADE", 15, f"Opcional. {lista_de_opcoes(PERIODICIDADES)}. {VAZIO}", opcoes=PERIODICIDADES),
    ColunaModelo("PAG", 8, f"Opcional. Dias para pagamento (0 a 365). Só vale para planos que já existem. {VAZIO}"),
    ColunaModelo("DIA1", 8, f"Opcional. Dia 1 do pagamento (1 a 31), quando não é SEMANAL. 0 = mantém. {VAZIO}"),
    ColunaModelo("DIA2", 8, f"Opcional. Dia 2 do pagamento (1 a 31), quando não é SEMANAL. 0 = mantém. {VAZIO}"),
    ColunaModelo("DIAS_SEMANA", 22, "Opcional, só para SEMANAL. Dias separados por ; (ex.: SEGUNDA;QUINTA). "
                                    f"{VAZIO}"),
    ColunaModelo("TIPO_DIA", 13, f"Opcional, só para SEMANAL. {lista_de_opcoes(TIPOS_DIA)}. {VAZIO}", opcoes=TIPOS_DIA),
    ColunaModelo("BANCARIZAR", 12, f"Opcional. {lista_de_opcoes(BANCARIZAR)}. {VAZIO}", opcoes=BANCARIZAR),
    ColunaModelo("FANTASIA", 26, "Opcional e ignorada pelo robô. Use para se organizar.", papel="ignorada"),
]

REGRAS = [
    ("COD", "Sim", "Código, CPF ou CNPJ", "A linha é pulada"),
    ("TAXA", "Não", "Número, ex.: 1,50", "Usa a taxa da tela; se a tela também estiver vazia, mantém a de cada contrato"),
    ("PERIODICIDADE", "Não", lista_de_opcoes(PERIODICIDADES), "Usa a periodicidade da tela"),
    ("PAG", "Não", "0 a 365", "Usa a da tela; vazia nas duas = mantém. Plano novo não recebe (como no Selenium)"),
    ("DIA1 / DIA2", "Não", "1 a 31 (0 = mantém)", "Usa o da tela; vazio nas duas = mantém"),
    ("DIAS_SEMANA", "Não", ", ".join(DIAS_SEMANA) + ", separados por ;", "Usa os da tela; vazio nas duas = mantém"),
    ("TIPO_DIA", "Não", lista_de_opcoes(TIPOS_DIA), "Usa o da tela"),
    ("BANCARIZAR", "Não", lista_de_opcoes(BANCARIZAR), "Usa o da tela"),
    ("FANTASIA", "Não", "Qualquer texto", "É ignorada pelo robô"),
]

EXEMPLO = [
    ("12345", "1,50", "MENSAL", "2", "5", "20", "", "", "NÃO", "LOJA ABC"),
    ("67890", "2,00", "SEMANAL", "", "", "", "SEGUNDA;QUINTA", "INDIFERENTE", "SIM", "MERCADO XYZ"),
    ("11111", "", "QUINZENAL", "", "1", "15", "", "", "", "PADARIA (taxa vazia = mantém)"),
]


def gerar_modelo() -> bytes:
    """Planilha de taxas pronta para preencher (colunas, listas de valores e instruções)."""
    return montar_modelo(
        COLUNAS_MODELO,
        titulo="Planilha de Alteração de taxas",
        avisos=["O robô altera o plano de compra de TODOS os contratos de cada credenciado (contratos BLOQUEADOS "
                "são pulados; sem plano, cria um A VISTA).",
                "Um valor inválido recusa a planilha inteira, e a tela mostra a linha com problema. "
                "Nada é executado até corrigir.",
                "As colunas da planilha do painel Selenium (COD, TAXA, PERIODICIDADE, PAG, DIA1, DIA2, BANCARIZAR, "
                "TIPO_DIA, DIA_SEM1 a DIA_SEM7) também são aceitas."],
        regras=REGRAS,
        exemplo=EXEMPLO,
    )

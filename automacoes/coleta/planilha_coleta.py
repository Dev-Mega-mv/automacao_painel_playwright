"""Planilha da coleta: só a coluna do código (CODIGO, CNPJ e CPF também valem como nome)."""
from ..core.planilha import ColunaModelo, montar_modelo

COLUNAS_MODELO = [
    ColunaModelo("COD", 22, "Obrigatório. Código, CPF ou CNPJ do credenciado. O tipo de pesquisa é escolhido na "
                            "tela e vale para todas as linhas.", papel="obrigatoria"),
    ColunaModelo("FANTASIA", 30, "Opcional e ignorada pelo robô. Use para se organizar.", papel="ignorada"),
]

REGRAS = [
    ("COD", "Sim", "Código, CPF ou CNPJ", "A linha é pulada"),
    ("FANTASIA", "Não", "Qualquer texto", "É ignorada pelo robô"),
]

EXEMPLO = [
    ("12345", "LOJA ABC"),
    ("67890", "MERCADO XYZ"),
]


def gerar_modelo() -> bytes:
    """Planilha da coleta pronta para preencher."""
    return montar_modelo(
        COLUNAS_MODELO,
        titulo="Planilha da Coleta de código de estabelecimento",
        avisos=["A origem da transação (ex.: CARDSE) é escolhida na tela e vale para todas as linhas.",
                "A coleta só precisa do código. Outras colunas são ignoradas."],
        regras=REGRAS,
        exemplo=EXEMPLO,
    )

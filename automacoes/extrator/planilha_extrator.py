"""Planilha do extrator: só a coluna do código (CODIGO, CNPJ e CPF também valem como nome)."""
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
    """Planilha do extrator pronta para preencher."""
    return montar_modelo(
        COLUNAS_MODELO,
        titulo="Planilha do Extrator de dados",
        avisos=["O extrator só precisa do código. Outras colunas são ignoradas."],
        regras=REGRAS,
        exemplo=EXEMPLO,
    )

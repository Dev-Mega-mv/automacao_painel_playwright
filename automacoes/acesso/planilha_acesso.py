"""Planilha da criação de acesso: só a coluna do código (a antiga tickets.xlsx, com CODIGO, também serve)."""
from ..core.planilha import ColunaModelo, montar_modelo

COLUNAS_MODELO = [
    ColunaModelo("COD", 22, "Obrigatório. Código, CPF ou CNPJ do credenciado na Infox. O tipo de pesquisa é "
                            "escolhido na tela e vale para todas as linhas.", papel="obrigatoria"),
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
    """Planilha da criação de acesso pronta para preencher."""
    return montar_modelo(
        COLUNAS_MODELO,
        titulo="Planilha da Criação de acesso",
        avisos=["Os dados do estabelecimento e do gerente vêm da Infox: a planilha só precisa do código.",
                "A planilha antiga (tickets.xlsx, coluna CODIGO) também é aceita."],
        regras=REGRAS,
        exemplo=EXEMPLO,
    )

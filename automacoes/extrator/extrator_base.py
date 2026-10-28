from ..core.automacao_base import AutomacaoPorItem


class ExtratorBase(AutomacaoPorItem):
    """Comum aos extratores: só leem o portal; uma linha de relatório por código pesquisado."""

    nome = "extrator"
    prefixo_relatorio = "extrator"
    aba = "Extrator"

    def __init__(self, credenciais: dict, codigos: list[str], status, *, tipo_pesquisa: str = "COD"):
        super().__init__(credenciais, codigos, status)
        self.tipo_pesquisa = tipo_pesquisa.upper()

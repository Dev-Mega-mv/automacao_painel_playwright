from dataclasses import dataclass

TECNOLOGIAS = ("CIELO", "CARDSE", "AMBOS")
ACOES = ("ATIVAR", "DESATIVAR")


@dataclass(frozen=True)
class ItemHabilitacao:
    """Um credenciado e o que fazer com as redes CIELO e CARDSE dos seus contratos."""

    codigo: str
    tecnologia: str = "CIELO"     # CIELO | CARDSE | AMBOS
    acao_cielo: str = "ATIVAR"    # ATIVAR | DESATIVAR
    acao_cardse: str = "ATIVAR"   # ATIVAR | DESATIVAR
    produto_unico: str = ""       # se informado, só o contrato com esse nome de produto

    def __post_init__(self):
        if not self.codigo:
            raise ValueError("Informe o código ou CNPJ do credenciado.")
        if self.tecnologia not in TECNOLOGIAS:
            raise ValueError(f"Tecnologia inválida: {self.tecnologia}. Use CIELO, CARDSE ou AMBOS.")
        for acao in (self.acao_cielo, self.acao_cardse):
            if acao not in ACOES:
                raise ValueError(f"Ação inválida: {acao}. Use ATIVAR ou DESATIVAR.")

    @property
    def usa_cielo(self) -> bool:
        return self.tecnologia in ("CIELO", "AMBOS")

    @property
    def usa_cardse(self) -> bool:
        return self.tecnologia in ("CARDSE", "AMBOS")

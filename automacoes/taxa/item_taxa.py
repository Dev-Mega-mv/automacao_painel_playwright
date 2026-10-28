"""Um credenciado e o plano de compra pedido, com a validação comum à tela e à planilha."""
import re
from dataclasses import dataclass

from ..core.texto import sem_acento_maiusculo

PERIODICIDADES = ("DIÁRIA", "SEMANAL", "MENSAL", "QUINZENAL")
DIAS_SEMANA = ("DOMINGO", "SEGUNDA", "TERCA", "QUARTA", "QUINTA", "SEXTA", "SABADO")   # como na versão Selenium
TIPOS_DIA = ("INDIFERENTE", "PAR", "ÍMPAR")
BANCARIZAR = ("SIM", "NÃO")


def _escolha(valor, opcoes: tuple[str, ...], nome: str) -> str:
    """Valor da lista, sem diferença de acento ou maiúscula ('diaria' -> 'DIÁRIA')."""
    procurado = sem_acento_maiusculo(valor)
    for opcao in opcoes:
        if sem_acento_maiusculo(opcao) == procurado:
            return opcao
    raise ValueError(f"{nome} '{valor}' inválido, use {', '.join(opcoes[:-1])} ou {opcoes[-1]}")


def periodicidade(valor) -> str:
    return _escolha(valor, PERIODICIDADES, "PERIODICIDADE")


def tipo_dia(valor) -> str:
    return _escolha(valor, TIPOS_DIA, "TIPO_DIA")


def bancarizar(valor) -> str:
    return _escolha(valor, BANCARIZAR, "BANCARIZAR")


def taxa(valor) -> str:
    """'1.5', '1,50' ou '1,5%' -> '1,5' (como a versão Selenium); vazio = manter a taxa atual."""
    texto = str(valor or "").strip().replace("%", "").replace(" ", "")
    if not texto:
        return ""
    try:
        numero = float(texto.replace(",", "."))
    except ValueError:
        raise ValueError(f"TAXA '{valor}' inválida, use um número como 1,50")
    if not 0 <= numero < 100:
        raise ValueError(f"TAXA '{valor}' fora do intervalo de 0 a 100")
    return str(numero).replace(".", ",")


def inteiro(valor, nome: str, maximo: int) -> str:
    """'5', '5.0' ou '05' -> '5'; vazio continua vazio."""
    texto = str(valor or "").strip()
    if not texto:
        return ""
    if not re.fullmatch(r"\d+(\.0+)?", texto) or int(float(texto)) > maximo:
        raise ValueError(f"{nome} '{valor}' inválido, use um número de 0 a {maximo}")
    return str(int(float(texto)))


def dia_do_mes(valor, nome: str) -> str:
    """Dia 1 a 31; vazio ou 0 = manter o dia que está no plano (a versão Selenium pulava os dois)."""
    dia = inteiro(valor, nome, 31)
    return "" if dia == "0" else dia


def dias_da_semana(valores) -> tuple[str, ...]:
    """['segunda', 'Quarta-feira'] ou 'SEGUNDA;QUARTA' -> ('SEGUNDA', 'QUARTA'), na ordem dada."""
    if isinstance(valores, str):
        valores = re.split(r"[;,/]", valores)
    dias = []
    for valor in valores:
        dia = re.sub(r"-?\s*FEIRA$", "", sem_acento_maiusculo(valor))
        if not dia:
            continue
        if dia not in DIAS_SEMANA:
            raise ValueError(f"dia da semana '{valor.strip()}' inválido, use {', '.join(DIAS_SEMANA)}")
        if dia not in dias:
            dias.append(dia)
    return tuple(dias)


@dataclass(frozen=True)
class ItemTaxa:
    """Um credenciado e como deve ficar o plano de compra de cada contrato dele.

    Campos vazios (taxa, pag_dias, dia1, dia2, dias_semana) mantêm o que já está no plano.
    Dia 1 e Dia 2 iguais a 0 também mantêm, como na versão Selenium.
    """

    codigo: str
    periodicidade: str = "MENSAL"
    taxa: str = ""
    pag_dias: str = ""
    dia1: str = ""
    dia2: str = ""
    dias_semana: tuple[str, ...] = ()
    bancarizar: str = "NÃO"
    tipo_dia: str = "INDIFERENTE"

    def __post_init__(self):
        if not self.codigo:
            raise ValueError("Informe o código ou CNPJ do credenciado.")
        valores = {
            "periodicidade": periodicidade(self.periodicidade),
            "taxa": taxa(self.taxa),
            "pag_dias": inteiro(self.pag_dias, "PAG (dias para pagamento)", 365),
            "dia1": dia_do_mes(self.dia1, "DIA1"),
            "dia2": dia_do_mes(self.dia2, "DIA2"),
            "dias_semana": dias_da_semana(self.dias_semana),
            "bancarizar": bancarizar(self.bancarizar),
            "tipo_dia": tipo_dia(self.tipo_dia),
        }
        for campo, valor in valores.items():
            object.__setattr__(self, campo, valor)

    @property
    def semanal(self) -> bool:
        return self.periodicidade == "SEMANAL"

    def resumo(self) -> str:
        """Ex.: 'taxa 1,5 | MENSAL, dias 5 e 20 | pagamento após 2 dias | bancarizar NÃO'."""
        partes = [f"taxa {self.taxa}" if self.taxa else "taxa atual"]
        if self.semanal:
            dias = "/".join(self.dias_semana) or "dias atuais"
            partes.append(f"SEMANAL, {dias}, tipo de dia {self.tipo_dia}")
        else:
            dias = " e ".join(d for d in (self.dia1, self.dia2) if d)
            partes.append(f"{self.periodicidade}, dias {dias}" if dias else self.periodicidade)
        if self.pag_dias:
            partes.append(f"pagamento após {self.pag_dias} dia(s)")
        partes.append(f"bancarizar {self.bancarizar}")
        return " | ".join(partes)

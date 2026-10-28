"""Dados do credenciado lidos na tela de detalhe da Infox (página 2101), no formato que o painel Megavale pede.

As regras de separação (telefone, endereço, cidade/UF) são as da automação original
(automacao_criacao_acesso/utils.py).
"""
import re
from dataclasses import dataclass

from ..core import seletores as S

# A automação original usa este CPF quando a Infox não tem o CPF do proprietário (o painel exige o campo)
CPF_SEM_PROPRIETARIO = "12345678910"


@dataclass
class DadosCredenciado:
    codigo: str
    razao_social: str
    nome_fantasia: str
    cnpj: str
    cpf_proprietario: str
    email: str
    cep: str
    logradouro: str
    numero: str
    bairro: str
    cidade: str
    estado: str
    ddd_celular: str
    celular: str
    ddd_telefone: str
    telefone: str

    @property
    def cidade_uf(self) -> str:
        return "/".join(parte for parte in (self.cidade, self.estado) if parte)

    def faltando(self) -> list[str]:
        """Campos que o cadastro no painel usa e vieram vazios da Infox."""
        nomes = {"razão social": self.razao_social, "CNPJ": self.cnpj, "e-mail": self.email, "CEP": self.cep,
                 "cidade/UF": self.cidade and self.estado}
        return [nome for nome, valor in nomes.items() if not valor]


def separar_telefone(texto: str) -> tuple[str, str]:
    """'(11) 99999-0000' -> ('11', '99999-0000'). Fora desse formato, devolve vazios."""
    achado = re.search(r"\((\d+)\)\s*([\d-]+)", texto or "")
    return (achado.group(1), achado.group(2)) if achado else ("", "")


def separar_endereco(texto: str) -> tuple[str, str]:
    """'RUA A, 100' -> ('RUA A', '100'). Sem vírgula, tudo é logradouro e o número fica vazio."""
    logradouro, _, numero = (texto or "").partition(",")
    return logradouro.strip(), numero.strip()


def separar_cidade_uf(texto: str) -> tuple[str, str]:
    """'SAO PAULO/SP' -> ('SAO PAULO', 'SP'). Sem barra, devolve vazios."""
    if "/" not in (texto or ""):
        return "", ""
    cidade, _, estado = texto.partition("/")
    return cidade.strip(), estado.strip()


def ler_dados_credenciado(ler) -> DadosCredenciado:
    """Monta os dados a partir da tela do credenciado aberta. `ler(seletor)` devolve o valor de um campo."""
    ddd_celular, celular = separar_telefone(ler(S.DET_CELULAR))
    ddd_telefone, telefone = separar_telefone(ler(S.DET_TELEFONE))
    logradouro, numero = separar_endereco(ler(S.DET_END_LOGRADOURO))
    cidade, estado = separar_cidade_uf(ler(S.DET_END_CIDADE))
    return DadosCredenciado(
        codigo=ler(S.DET_CODIGO),
        razao_social=ler(S.DET_RAZAO),
        nome_fantasia=ler(S.DET_FANTASIA),
        cnpj=ler(S.DET_CNPJ),
        cpf_proprietario=ler(S.DET_CPF_PROPRIETARIO) or CPF_SEM_PROPRIETARIO,
        email=ler(S.DET_EMAIL),
        cep=ler(S.DET_END_CEP),
        logradouro=logradouro,
        numero=numero,
        bairro=ler(S.DET_END_BAIRRO),
        cidade=cidade,
        estado=estado,
        ddd_celular=ddd_celular,
        celular=celular,
        ddd_telefone=ddd_telefone,
        telefone=telefone,
    )

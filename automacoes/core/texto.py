"""Normalização de textos, códigos e documentos usados nas pesquisas."""
import re
import unicodedata


def somente_digitos(valor) -> str:
    return re.sub(r"\D", "", str(valor or ""))


def sem_acento_maiusculo(valor) -> str:
    """'Definição ' -> 'DEFINICAO'. Usado para comparar textos vindos do portal."""
    texto = unicodedata.normalize("NFKD", str(valor or ""))
    texto = "".join(ch for ch in texto if not unicodedata.combining(ch))
    return re.sub(r"\s+", " ", texto).strip().upper()


TIPOS_DOCUMENTO = ("CNPJ", "CPF")  # pesquisados no campo de CNPJ do portal


def pesquisa_por_documento(tipo_pesquisa: str) -> bool:
    return tipo_pesquisa.upper() in TIPOS_DOCUMENTO


def normalizar_codigo_pesquisa(valor, tipo_pesquisa: str) -> str:
    """Prepara o valor digitado ou lido da planilha para o campo de pesquisa.

    - Código: remove o '.0' que o Excel acrescenta ('12345.0' -> '12345').
    - CNPJ/CPF: só dígitos; até 11 dígitos completa como CPF, 12 ou 13 completa como CNPJ.
    """
    texto = str(valor or "").strip()
    if re.fullmatch(r"\d+\.0+", texto):
        texto = texto.split(".")[0]

    if not pesquisa_por_documento(tipo_pesquisa):
        return texto

    digitos = somente_digitos(texto)
    if not digitos:
        return texto
    if len(digitos) <= 11:
        return digitos.zfill(11)
    if len(digitos) <= 13:
        return digitos.zfill(14)
    return digitos


def mesmo_documento(a, b) -> bool:
    """Compara códigos/CNPJs pelos dígitos, ignorando formatação e zeros à esquerda."""
    da, db = somente_digitos(a).lstrip("0"), somente_digitos(b).lstrip("0")
    return bool(da) and da == db

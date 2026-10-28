"""Planilha enviada pelo formulário: confere o arquivo e descreve de onde vieram os itens."""
import io
from pathlib import Path

from automacoes.core.planilha import PlanilhaInvalida, conferir_extensao


def planilha_enviada(arquivo) -> tuple[io.BytesIO, str]:
    """Conteúdo e nome da planilha enviada. Lida da memória, sem gravar em disco."""
    if arquivo is None or not arquivo.filename:
        raise PlanilhaInvalida("Selecione uma planilha.")
    nome = Path(arquivo.filename).name
    conferir_extensao(nome)
    return io.BytesIO(arquivo.read()), nome


def origem_da_planilha(nome: str, quantidade: int, linhas_sem_codigo: int) -> str:
    """Primeira linha do log da execução, para saber de onde vieram os itens."""
    origem = f"Planilha '{nome}': {quantidade} credenciado(s)."
    if linhas_sem_codigo:
        origem += f" {linhas_sem_codigo} linha(s) sem código ignorada(s)."
    return origem

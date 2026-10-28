from ..core import seletores as S
from ..core.apex import aguardar_apex
from .extrator_base import ExtratorBase

# Mesmas colunas e na mesma ordem da versão Selenium (automacoes/extrator.py)
CAMPOS = (
    ("CODIGO", S.DET_CODIGO),
    ("CNPJ", S.DET_CNPJ),
    ("NOME_FANTASIA", S.DET_FANTASIA),
    ("RAZAO_SOCIAL", S.DET_RAZAO),
    ("CIDADE", S.DET_END_CIDADE),
    ("ENDERECO", S.DET_END_LOGRADOURO),
    ("BAIRRO", S.DET_END_BAIRRO),
    ("CEP", S.DET_END_CEP),
    ("EMAIL", S.DET_EMAIL),
    ("CONCILIACAO", S.DET_CONCILIACAO),
    ("CELULAR", S.DET_CELULAR),
    ("TELEFONE", S.DET_TELEFONE),
    ("DATA_CADASTRO", S.DET_DATA_CADASTRO),
)
# Se nenhum destes vier preenchido, a tela abriu mas não carregou os dados
CAMPOS_PRINCIPAIS = ("CODIGO", "CNPJ", "RAZAO_SOCIAL", "NOME_FANTASIA", "EMAIL", "TELEFONE", "CELULAR")


class ExtratorCadastro(ExtratorBase):
    """Lê os dados cadastrais de cada credenciado (tela de detalhe, página 2101).

    Se a pesquisa devolver uma lista, abre o primeiro resultado, como a versão Selenium, mas só
    grava os dados se o credenciado aberto conferir com o código/CNPJ pesquisado.
    """

    titulo = "Extrator de cadastro"
    prefixo_relatorio = "extrator_cadastro"
    aba = "Cadastro"
    colunas = ["PESQUISADO", *(nome for nome, _ in CAMPOS), "RESULTADO"]

    def processar_item(self, codigo: str):
        log = self.status.log
        self.portal.ir_para_pesquisa_credenciado()
        resultados = self.portal.pesquisar_credenciado(codigo, self.tipo_pesquisa)
        if resultados:
            log(f"A pesquisa retornou {resultados} credenciado(s); abrindo o primeiro.",
                "WARNING" if resultados > 1 else "INFO")
            self.portal.abrir_resultado(0)
        self.portal.conferir_credenciado(codigo, self.tipo_pesquisa, "Nada foi extraído.")
        aguardar_apex(self.page)

        dados = {nome: self.ler(seletor) for nome, seletor in CAMPOS}
        if not any(dados[nome] for nome in CAMPOS_PRINCIPAIS):
            aviso = "a tela do credenciado abriu, mas os campos vieram vazios"
            resultado = f"AVISO: {aviso}"
            log(f"{codigo}: {aviso}.", "WARNING")
        else:
            resultado = "OK"
            if resultados > 1:
                resultado += f" (a pesquisa retornou {resultados} credenciados; este é o primeiro da lista)"
            nome = dados["NOME_FANTASIA"] or dados["RAZAO_SOCIAL"] or dados["CODIGO"]
            log(f"{codigo}: {nome} | CNPJ {dados['CNPJ'] or '—'} | {dados['CIDADE'] or 'sem cidade'}", "SUCCESS")
        self.registrar({"PESQUISADO": codigo, **dados, "RESULTADO": resultado})

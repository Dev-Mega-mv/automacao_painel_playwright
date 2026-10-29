import threading
from datetime import datetime
from pathlib import Path

_PREFIXOS = {"ERROR": "ERRO", "WARNING": "AVISO", "SUCCESS": "SUCESSO"}


class StatusExecucao:
    """Progresso e logs de uma execução, compartilhados entre a thread da automação e o Flask.

    `como_dict()` devolve o mesmo formato dos dicionários de status da versão Selenium,
    então /status, /api/status e /download_relatorio funcionam sem mudança.
    """

    def __init__(self, nome: str, arquivo_log: Path | None = None, carimbo: str | None = None):
        self.nome = nome
        self.carimbo = carimbo or f"{datetime.now():%Y%m%d_%H%M%S}"  # também no nome do relatório e das capturas
        self.id = f"{nome}_{self.carimbo}"
        self.titulo = nome  # a automação troca pelo título dela ao começar
        self.arquivo_log = arquivo_log
        self._trava = threading.Lock()
        self._running = False
        self._total = 0
        self._processados = 0
        self._item_atual = None
        self._logs: list[str] = []
        self._inicio = None
        self._fim = None
        self._parada_solicitada = False
        self._relatorio_path: str | None = None

    # --- ciclo de vida ---------------------------------------------------
    def reservar(self):
        """Marca como em execução antes de a thread começar (impede início duplo)."""
        with self._trava:
            self._running = True

    def iniciar(self, total: int, titulo: str | None = None):
        with self._trava:
            if titulo:
                self.titulo = titulo
            self._running = True
            self._total = total
            self._processados = 0
            self._inicio = datetime.now()

    def definir_item_atual(self, item):
        with self._trava:
            self._item_atual = item

    def avancar(self):
        with self._trava:
            self._processados += 1

    def finalizar(self):
        with self._trava:
            self._running = False
            self._fim = datetime.now()

    def solicitar_parada(self):
        with self._trava:
            self._parada_solicitada = True

    def definir_relatorio(self, caminho):
        with self._trava:
            self._relatorio_path = str(caminho) if caminho else None

    # --- consultas -------------------------------------------------------
    @property
    def running(self) -> bool:
        return self._running

    @property
    def parada_solicitada(self) -> bool:
        return self._parada_solicitada

    @property
    def total(self) -> int:
        return self._total

    @property
    def processados(self) -> int:
        return self._processados

    def duracao(self) -> str:
        if not self._inicio:
            return "N/A"
        return str((self._fim or datetime.now()) - self._inicio).split(".")[0]

    def como_dict(self) -> dict:
        with self._trava:
            return {
                "running": self._running,
                "total": self._total,
                "processed": self._processados,
                "current_item": self._item_atual,
                "logs": list(self._logs),
                "start_time": self._inicio,
                "end_time": self._fim,
                "request_stop": self._parada_solicitada,
                "relatorio_path": self._relatorio_path,
            }

    # --- logs ------------------------------------------------------------
    def log(self, mensagem: str, nivel: str = "INFO"):
        """Mensagem para a tela de status e para o arquivo de log da execução."""
        prefixo = _PREFIXOS.get(nivel, "")
        linha = f"[{datetime.now():%H:%M:%S}] {prefixo + ': ' if prefixo else ''}{mensagem}"
        with self._trava:
            self._logs.append(linha)
        self._imprimir(f"[{self.nome}] {linha}")
        self._gravar(linha)

    @staticmethod
    def _imprimir(texto: str):
        """Eco no terminal. Nunca deixa um problema de codificação do console derrubar a automação."""
        try:
            print(texto)
        except UnicodeEncodeError:
            print(texto.encode("ascii", "replace").decode("ascii"))
        except OSError:
            pass

    def detalhe(self, texto: str):
        """Informação técnica (ex.: traceback): só vai para o arquivo de log."""
        self._gravar(texto.rstrip())

    def _gravar(self, texto: str):
        if not self.arquivo_log:
            return
        try:
            with open(self.arquivo_log, "a", encoding="utf-8") as arquivo:
                arquivo.write(texto + "\n")
        except OSError:
            pass

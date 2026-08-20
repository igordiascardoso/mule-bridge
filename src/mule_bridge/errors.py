"""Exceções do mule-bridge. Tudo que é erro esperado herda de BridgeError."""


class BridgeError(Exception):
    """Erro esperado, exibido ao usuário sem traceback."""


class ConfigError(BridgeError):
    """Config ausente, inválida ou apontando para caminho inexistente."""


class DiscoveryError(BridgeError):
    """Não foi possível descobrir projetos na pasta de trabalho ou no workspace."""


class SyncError(BridgeError):
    """Falha durante a cópia/reconciliação de arquivos."""


class NonInteractiveError(BridgeError):
    """Precisava perguntar algo, mas não há terminal interativo (IDE, agente de IA, CI)."""

"""Pipeline real de pré-processamento e classificação de folhas de tomateiro."""

from .pipeline import (
    ErroArtefatoModelo,
    ResultadoAnalise,
    analisar,
    carregar_recursos,
)

__all__ = (
    "ErroArtefatoModelo",
    "ResultadoAnalise",
    "analisar",
    "carregar_recursos",
)

"""Pages module for Digital Twins Sales Simulator."""

from .setup import setup_page
from .simulacao import simulacao_page
from .veredito import veredito_page
from .coach import coach_page
from .export import export_page

__all__ = [
    "setup_page",
    "simulacao_page",
    "veredito_page",
    "coach_page",
    "export_page",
]

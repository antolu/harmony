from __future__ import annotations

from harmony._mod_replace import replace_modname

from .cli_ingest import main as cli_ingest_main

replace_modname(cli_ingest_main, __name__)

__all__ = ["cli_ingest_main"]

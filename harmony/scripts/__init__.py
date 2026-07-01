from __future__ import annotations

from harmony._mod_replace import replace_modname
from harmony.scripts.acl_backfill import AclBackfillJob
from harmony.scripts.acl_backfill import main as acl_backfill_main
from harmony.scripts.embedder import EmbedderConfig
from harmony.scripts.embedder import main as embedder_main
from harmony.scripts.reset_state import main as reset_state_main

replace_modname(AclBackfillJob, __name__)
replace_modname(EmbedderConfig, __name__)
replace_modname(acl_backfill_main, __name__)
replace_modname(embedder_main, __name__)
replace_modname(reset_state_main, __name__)

__all__ = [
    "AclBackfillJob",
    "EmbedderConfig",
    "acl_backfill_main",
    "embedder_main",
    "reset_state_main",
]

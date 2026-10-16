"""Provider-independent inference boundary for Continuity.

Nothing here contacts a model service by default.
"""

from .router import ModelRouter, OfflineProvider, RouterResult

__all__ = ["ModelRouter", "OfflineProvider", "RouterResult"]

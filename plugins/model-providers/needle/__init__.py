"""Needle 2 local specialist — OpenAI-compatible Worker/model target.

Packet §28 Phase 2 / §6.3: a Needle specialist has to be selectable by the
M.U.S.E. Worker/model primitive, not only as a dsh route. Named alias of
the custom OpenAI profile so routing can say `needle` instead of `custom`.

Environment:
  NEEDLE_BASE_URL   default http://127.0.0.1:8011/v1
  NEEDLE_API_KEY    optional; local server does not require one
"""

from __future__ import annotations

import os

from providers import register_provider
from providers.base import ProviderProfile

needle = ProviderProfile(
    name="needle",
    aliases=("needle2", "needle-local"),
    env_vars=(),
    display_name="Needle 2 (local)",
    description="Local Cactus Needle 2 specialist over OpenAI-compatible HTTP",
    signup_url="",
    fallback_models=("needle2",),
    base_url=os.environ.get("NEEDLE_BASE_URL", "http://127.0.0.1:8011/v1"),
    default_max_tokens=1024,
)

register_provider(needle)

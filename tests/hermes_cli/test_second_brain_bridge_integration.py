"""Live integration test for the Second Brain bridge.

Exercises the **real** Postgres(pgvector)-backed ``second_brain`` pipeline through
:mod:`hermes_cli.jarvis_prime.second_brain_bridge`: ingest a uniquely-marked
document, then retrieve it back through the bridge and assert the marker is in the
fused context.

Marked ``integration`` so it is excluded from the default suite
(``addopts = -m 'not integration'``) and self-skips unless a database is
configured (``SECOND_BRAIN_PG_*``) and ``psycopg2`` + ``second_brain`` import.

Run it against a pgvector-enabled database (graph disabled, no Neo4j needed)::

    # schema: apply second_brain/migrations/001_init.sql to a DB with the
    #         `vector` extension; create a login role that owns it.
    export SECOND_BRAIN_PG_HOST=localhost SECOND_BRAIN_PG_DB=secondbrain \
           SECOND_BRAIN_PG_USER=muse SECOND_BRAIN_PG_PASSWORD=... \
           SECOND_BRAIN_PG_SSLMODE=disable \
           SECOND_BRAIN_EMBEDDING_PROVIDER=hashing SECOND_BRAIN_EMBEDDING_DIM=1536
    uv run --with psycopg2-binary --with pgvector --with pytest-xdist \
            --with pytest-timeout \
        pytest -o addopts="" -m integration \
        tests/hermes_cli/test_second_brain_bridge_integration.py

(Verified green this way against Postgres 16 + pgvector 0.6.0.)
"""

from __future__ import annotations

import os
import uuid

import pytest

pytestmark = pytest.mark.integration

# Capture the DB config at import time — *before* the autouse hermetic-environment
# conftest fixture blanks credential-shaped vars (e.g. SECOND_BRAIN_PG_PASSWORD).
# The test re-applies these via monkeypatch so second_brain can actually connect.
_PG_ENV = {
    k: os.environ[k]
    for k in (
        "SECOND_BRAIN_PG_HOST",
        "SECOND_BRAIN_PG_PORT",
        "SECOND_BRAIN_PG_DB",
        "SECOND_BRAIN_PG_USER",
        "SECOND_BRAIN_PG_PASSWORD",
        "SECOND_BRAIN_PG_SSLMODE",
        "SECOND_BRAIN_EMBEDDING_PROVIDER",
        "SECOND_BRAIN_EMBEDDING_DIM",
    )
    if k in os.environ
}


def _db_configured() -> bool:
    return bool(
        _PG_ENV.get("SECOND_BRAIN_PG_HOST") or _PG_ENV.get("SECOND_BRAIN_PG_DB")
    )


@pytest.mark.skipif(
    not _db_configured(), reason="no SECOND_BRAIN_PG_* database configured"
)
def test_live_ingest_and_retrieve_through_bridge(monkeypatch):
    pytest.importorskip("psycopg2")
    sb = pytest.importorskip("second_brain.knowledge")

    # Re-apply the captured DB config — the hermetic conftest blanked the
    # credential-shaped vars (notably the password) during setup.
    for key, value in _PG_ENV.items():
        monkeypatch.setenv(key, value)

    from hermes_cli.jarvis_prime.second_brain_bridge import is_available, retrieve

    assert is_available() is True

    marker = uuid.uuid4().hex
    brain = sb.SecondBrain(sb.load_settings(), enable_graph=False)
    try:
        brain.ingest_text(
            f"The marker token is {marker}; it uniquely identifies this record.",
            f"int-{marker}",
        )
    finally:
        brain.close()

    ctx = retrieve(f"what is the marker token {marker}", enable_graph=False)
    assert ctx.source == "second_brain"
    assert ctx.block_count >= 1
    assert marker in ctx.text

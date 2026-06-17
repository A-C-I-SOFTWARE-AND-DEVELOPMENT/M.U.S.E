"""Second Brain — a hybrid (vector + graph), governed knowledge module.

The :class:`second_brain.knowledge.SecondBrain` facade wires five layers
(ingestion, vector + graph + document storage, hybrid retrieval, reasoning,
governance) over PostgreSQL/pgvector and Neo4j. Importing this package pulls in
**no** database drivers — backends are imported lazily when a backend is first
used — so it is safe to import (e.g. for capability checks) even where the
drivers or databases are not installed.

The thin, opt-in seam that lets the MUSE runtime *use* this module is
:mod:`hermes_cli.jarvis_prime.second_brain_bridge`.
"""

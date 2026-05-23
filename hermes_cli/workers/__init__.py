"""Hermes CLI worker modules.

Workers are always-available evidence-gathering routines that inspect
the local environment and produce structured reports for downstream
orchestration. Each worker writes its findings to ``shared-context/``
(consumed by other workers) and to ``workers/<name>/`` (its own
status + output).
"""

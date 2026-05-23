"""Worker adapters that hand structured tasks off to external coding agents.

Each adapter is a thin, side-effect-bounded module: it detects whether the
target tool is available on the local machine, materializes a prompt + status
pair under ``<workspace>/workers/<worker>/``, and (if execution is explicitly
enabled and the official CLI is present) drives the local tool. Adapters
never proxy a provider subscription, never automate a web UI, and never
fabricate credentials — handoff is the default.
"""

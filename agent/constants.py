"""Project-wide constants — single source of truth for magic numbers and strings.

Import from here instead of hardcoding values scattered across modules.
"""
from __future__ import annotations

# ── API / Network ──────────────────────────────────────────────
DEFAULT_API_TIMEOUT_SECONDS = 30
MAX_API_RETRIES = 3
API_RETRY_BASE_DELAY = 1.0
API_RETRY_MAX_DELAY = 30.0
CONNECTION_POOL_SIZE = 10
HEALTH_CHECK_INTERVAL_SECONDS = 30

# ── Agent Runtime ──────────────────────────────────────────────
DEFAULT_MAX_ITERATIONS = 90
DEFAULT_CONTEXT_WINDOW = 16000
COMPRESSION_THRESHOLD_PCT = 0.75
DEFAULT_TEMPERATURE = 0.7
DEFAULT_MAX_TOKENS = 4096

# ── Terminal / Display ─────────────────────────────────────────
SPINNER_UPDATE_INTERVAL = 0.12  # seconds
INTERRUPT_POLL_INTERVAL = 0.2   # seconds
COMPRESSION_RETRY_DELAY = 2.0   # seconds

# ── File / Path ────────────────────────────────────────────────
MAX_FILE_SIZE_KB = 500           # pre-commit check
LINE_LENGTH_LIMIT = 120          # ruff
LARGE_ARTIFACT_THRESHOLD = 1024 * 1024 * 100  # 100 MB

# ── Session / Storage ──────────────────────────────────────────
SESSION_DB_FILENAME = "sessions.db"
LOG_DIRNAME = "logs"
SKILLS_DIRNAME = "skills"
CONFIG_FILENAME = "config.yaml"
ENV_FILENAME = ".env"

# ── Retry / Backoff ────────────────────────────────────────────
DEFAULT_BACKOFF_FACTOR = 2.0
DEFAULT_JITTER_MAX = 0.5  # seconds
MAX_BACKOFF_DELAY = 60.0

# ── AAA Pipeline ───────────────────────────────────────────────
PIPELINE_TIMEOUT_MINUTES = 30
PROOF_BUILD_TIMEOUT_MINUTES = 60
TERRAIN_HEIGHTMAP_SIZE = 1024

# ── Security ───────────────────────────────────────────────────
MIN_API_KEY_LENGTH = 20
REDACTION_PLACEHOLDER = "[REDACTED]"
ENV_NAME_MAX_LENGTH = 256

# ── HTTP Status Codes ──────────────────────────────────────────
HTTP_OK = 200
HTTP_BAD_REQUEST = 400
HTTP_UNAUTHORIZED = 401
HTTP_FORBIDDEN = 403
HTTP_NOT_FOUND = 404
HTTP_RATE_LIMITED = 429
HTTP_INTERNAL_ERROR = 500
HTTP_BAD_GATEWAY = 502
HTTP_SERVICE_UNAVAILABLE = 503
HTTP_GATEWAY_TIMEOUT = 504

# Retryable HTTP status codes
RETRYABLE_STATUS_CODES = frozenset({429, 502, 503, 504})

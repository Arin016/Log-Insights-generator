"""Central configuration. Reads from environment with sensible defaults."""

import os
from pathlib import Path
from dotenv import load_dotenv

load_dotenv()

# Project root
PROJECT_ROOT = Path(__file__).parent.resolve()

# ─── Elasticsearch ──────────────────────────────────────────────────────
ELASTICSEARCH_URL = os.getenv("ELASTICSEARCH_URL", "http://localhost:9200")
ELASTICSEARCH_INDEX = os.getenv("ELASTICSEARCH_INDEX", "ff_insights_events")
ELASTICSEARCH_USERNAME = os.getenv("ELASTICSEARCH_USERNAME") or None
ELASTICSEARCH_PASSWORD = os.getenv("ELASTICSEARCH_PASSWORD") or None

# ─── LLM Backend Selection ──────────────────────────────────────────────
LLM_BACKEND = os.getenv("LLM_BACKEND", "kiro")  # "kiro" or "http"

# ─── Kiro CLI ───────────────────────────────────────────────────────────
KIRO_BINARY = os.getenv("KIRO_BINARY", "kiro-cli")
KIRO_MODEL = os.getenv("KIRO_MODEL", "claude-opus-4.6")

# ─── HTTP Backend (Anthropic) ───────────────────────────────────────────
ANTHROPIC_API_KEY = os.getenv("ANTHROPIC_API_KEY", "")
ANTHROPIC_MODEL = os.getenv("ANTHROPIC_MODEL", "claude-sonnet-4-20250514")

# ─── HTTP Backend (Saviynt) ─────────────────────────────────────────────
LLM_HTTP_BASE_URL = os.getenv("LLM_HTTP_BASE_URL", "")
LLM_HTTP_AUTH_URL = os.getenv("LLM_HTTP_AUTH_URL", "")
LLM_HTTP_USERNAME = os.getenv("LLM_HTTP_USERNAME", "")
LLM_HTTP_PASSWORD = os.getenv("LLM_HTTP_PASSWORD", "")

# ─── Bounded Autonomy Caps ──────────────────────────────────────────────
REACT_MAX_ITERATIONS = int(os.getenv("REACT_MAX_ITERATIONS", "7"))
REACT_MAX_PER_TOOL = int(os.getenv("REACT_MAX_PER_TOOL", "4"))
REACT_WALL_CLOCK_SECONDS = int(os.getenv("REACT_WALL_CLOCK_SECONDS", "300"))

# ─── Confidence Gate ────────────────────────────────────────────────────
CONFIDENCE_THRESHOLD = float(os.getenv("CONFIDENCE_THRESHOLD", "0.70"))

# ─── Evidence Verification ──────────────────────────────────────────────
EVIDENCE_VERIFY_MAX_RETRIES = int(os.getenv("EVIDENCE_VERIFY_MAX_RETRIES", "2"))

# ─── Local storage paths ────────────────────────────────────────────────
DATA_DIR = Path(os.getenv("DATA_DIR", PROJECT_ROOT / "data")).resolve()
LOG_DIR = Path(os.getenv("LOG_DIR", PROJECT_ROOT / "logs")).resolve()

FINDINGS_DIR = DATA_DIR / "findings"
LLM_AUDIT_DIR = DATA_DIR / "llm_audit"
REPORTS_DIR = DATA_DIR / "reports"
MANUAL_REVIEW_DIR = DATA_DIR / "manual_review"
PIPELINE_STATE_DIR = DATA_DIR / "pipeline_state"

# ─── Application config paths ───────────────────────────────────────────
APPLICATIONS_DIR = PROJECT_ROOT / "applications"
SAP_CONFIG_DIR = APPLICATIONS_DIR / "sap"

# Ensure directories exist
for _d in (FINDINGS_DIR, LLM_AUDIT_DIR, REPORTS_DIR, MANUAL_REVIEW_DIR, PIPELINE_STATE_DIR, LOG_DIR):
    _d.mkdir(parents=True, exist_ok=True)

# Versioning
PIPELINE_VERSION = "0.1.0"
PROMPT_VERSIONS = {
    "data_exfiltration": "v1",
    "financial_fraud": "v1",
    "logistics_fraud": "v1",
    "po_manipulation": "v1",
    "vendor_master_manipulation": "v1",
    "so_manipulation": "v1",
}

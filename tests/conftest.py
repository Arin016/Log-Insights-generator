"""Keep legacy imports confined to newly created disposable output paths."""
import os
import tempfile

os.environ["PYTHON_DOTENV_DISABLED"] = "1"
_safe_root = tempfile.mkdtemp(prefix="ff-v2-test-")
os.environ["DATA_DIR"] = _safe_root + "/data"
os.environ["LOG_DIR"] = _safe_root + "/logs"

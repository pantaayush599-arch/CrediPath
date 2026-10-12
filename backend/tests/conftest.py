import os
import sys
import tempfile
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

# Each test session uses a throwaway SQLite database unless DATABASE_URL is set explicitly.
if "DATABASE_URL" not in os.environ:
    _tmp = tempfile.mkdtemp(prefix="credipath-test-")
    os.environ["DATABASE_URL"] = f"sqlite:///{_tmp}/test.db"

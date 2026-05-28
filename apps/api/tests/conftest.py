import os
import sys
from pathlib import Path

# Tests do not connect to the DB; this satisfies app imports that require DATABASE_URL.
os.environ.setdefault(
    "DATABASE_URL",
    "postgresql://test:test@127.0.0.1:5432/hiivbuddy_test",
)

# apps/api as cwd for imports
_ROOT = Path(__file__).resolve().parents[1]
if str(_ROOT) not in sys.path:
    sys.path.insert(0, str(_ROOT))

# Vercel serverless entrypoint — wraps the FastAPI app with the writable-path
# env overrides serverless needs. The app itself is defined in api/server.py.
import os
import tempfile
from pathlib import Path

_tmp = Path(tempfile.gettempdir())
os.environ.setdefault("CDK16_DATA_DIR", str(_tmp / "cdk16" / "data"))
os.environ.setdefault("CDK16_RESULTS_DIR", str(_tmp / "cdk16" / "results"))
os.environ.setdefault("CDK16_SYNC", "1")

from api.server import app  # noqa: E402

handler = app

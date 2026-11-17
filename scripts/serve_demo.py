"""Start an authenticated temporary English-to-Hindi demo on this computer."""

import argparse
import json
import os
import secrets
import sys
from pathlib import Path

parser = argparse.ArgumentParser(description="Password-protected English-to-Hindi demo")
parser.add_argument(
    "--no-share", action="store_true", help="Use an external tunnel instead of Gradio sharing"
)
args = parser.parse_args()

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
os.chdir(ROOT)
os.environ.setdefault("GRADIO_ANALYTICS_ENABLED", "False")
runtime = ROOT / ".runtime"
runtime.mkdir(mode=0o700, exist_ok=True)
credentials = runtime / "demo-login.json"
if not credentials.exists():
    fd = os.open(credentials, os.O_CREAT | os.O_EXCL | os.O_WRONLY, 0o600)
    with os.fdopen(fd, "w") as stream:
        json.dump({"username": "demo", "password": secrets.token_urlsafe(24)}, stream)
credentials.chmod(0o600)
login = json.loads(credentials.read_text())
print(f"Demo login is stored in {credentials}", flush=True)

from multilingua.ui import launch

# A dedicated run directory keeps earlier private studio recordings off this demo.
launch(
    str(ROOT / "configs/local.json"),
    runs=str(ROOT / "runs/public-demo"),
    port=7860,
    share=not args.no_share,
    auth=(login["username"], login["password"]),
)

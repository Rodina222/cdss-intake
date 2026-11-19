"""Start the dashboard: python scripts/serve.py
Same as: streamlit run streamlit_app.py
Add --share to let other computers on your network open it (set APP_PASSWORD first)."""
import subprocess
import sys
from pathlib import Path

root = Path(__file__).resolve().parent.parent
cmd = [sys.executable, "-m", "streamlit", "run", str(root / "streamlit_app.py")]
if "--share" in sys.argv:
    cmd += ["--server.address", "0.0.0.0"]
raise SystemExit(subprocess.call(cmd, cwd=str(root)))

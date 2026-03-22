# store_monitor_bot package
import sys
from pathlib import Path

# Add package directory to sys.path so bare imports (e.g. "from config.settings import ...")
# resolve when running as `python -m store_monitor_bot.main`
_pkg_dir = str(Path(__file__).resolve().parent)
if _pkg_dir not in sys.path:
    sys.path.insert(0, _pkg_dir)

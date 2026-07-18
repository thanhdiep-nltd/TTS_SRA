"""Cấu hình pytest cho test pipeline: thêm `plugins/` vào sys.path để import edu_pipeline."""

import pathlib
import sys

_PLUGINS = pathlib.Path(__file__).resolve().parents[1] / "plugins"
if str(_PLUGINS) not in sys.path:
    sys.path.insert(0, str(_PLUGINS))

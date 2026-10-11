"""
Compatibility bridge for scripts expecting .calendar or calendar.py in data access package,
while safely preserving Python standard library calendar module when shadowed.
"""
import sys
import os
from pathlib import Path

# Prevent circular import during stdlib _strptime -> import calendar
# If this file is called as 'calendar', import the real standard library calendar first!
if __name__ == "calendar":
    import importlib.machinery
    # Find stdlib calendar
    for p in sys.path:
        if p and Path(p).resolve() != Path(__file__).parent.resolve():
            target = Path(p) / "calendar.py"
            if target.exists():
                loader = importlib.machinery.SourceFileLoader("_real_calendar", str(target))
                _mod = loader.load_module()
                for k, v in _mod.__dict__.items():
                    globals()[k] = v
                break

# Also expose NEPSE calendar symbols when explicitly imported
try:
    from scripts.nepse_trading_calendar import *
except Exception:
    try:
        from nepse_trading_calendar import *
    except Exception:
        pass

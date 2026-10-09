"""
Compatibility bridge for scripts expecting .models or models.py in data access package.
"""
import importlib.util
from pathlib import Path

_target = Path(__file__).parent / "04_data_schemas_and_pydantic_entities.py"
if _target.exists():
    _spec = importlib.util.spec_from_file_location("entities", str(_target))
    _mod = importlib.util.module_from_spec(_spec)
    _spec.loader.exec_module(_mod)
    for _k, _v in _mod.__dict__.items():
        if not _k.startswith("__"):
            globals()[_k] = _v

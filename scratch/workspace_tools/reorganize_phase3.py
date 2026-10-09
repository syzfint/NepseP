"""Phase 3: sub-structure reports/ and scratch/ and patch writers."""
import re
import shutil
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
R = ROOT / "reports"
SC = ROOT / "scratch"

def bucket_report(name: str) -> str:
    if name.startswith(("GATE_CERTIFICATION", "G9_CERTIFICATION")):
        return "certification"
    if name.startswith("FINAL_"):
        return "final_oos"
    if name.startswith(("PBO_", "DSR_", "G9_DSR", "G9_PBO")):
        return "pbo_dsr"
    if re.match(r"(GATE\d+_|G\d+_RESULT)", name):
        return "gates"
    return "audits"

moves = {}
for p in list(R.iterdir()):
    if p.is_file():
        b = bucket_report(p.name)
        (R / b).mkdir(exist_ok=True)
        shutil.move(str(p), str(R / b / p.name))
        moves[p.name] = b
        print(f"reports/{p.name} -> reports/{b}/")

# Patch writers/readers: "reports/NAME" and f"reports/GATE{...}_RESULT.json"
for p in list((ROOT / "scripts").rglob("*.py")) + [ROOT / "README.md"] + list((ROOT / "docs").glob("*.md")):
    t = p.read_text(encoding="utf-8")
    t2 = re.sub(r"reports/([A-Za-z0-9_{}\[\]:\-]+\.(?:json|csv|md))",
                lambda m: f"reports/{bucket_report(m.group(1))}/{m.group(1)}", t)
    t2 = t2.replace('os.makedirs("reports", exist_ok=True)',
                    'for _d in ("gates", "audits", "final_oos", "pbo_dsr", "certification"): os.makedirs(f"reports/{_d}", exist_ok=True)')
    if t2 != t:
        p.write_text(t2, encoding="utf-8")
        print(f"patched: {p.relative_to(ROOT)}")

# scratch/
def bucket_scratch(p: Path) -> str:
    if p.name.startswith("reorganize"):
        return "workspace_tools"
    if p.suffix == ".md":
        return "notes"
    if p.suffix in (".json", ".png"):
        return "outputs"
    return "experiments"

shutil.rmtree(SC / "__pycache__", ignore_errors=True)
for p in list(SC.iterdir()):
    if p.is_file():
        b = bucket_scratch(p)
        (SC / b).mkdir(exist_ok=True)
        shutil.move(str(p), str(SC / b / p.name))
        print(f"scratch/{p.name} -> scratch/{b}/")

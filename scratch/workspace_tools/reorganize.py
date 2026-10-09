import re
import shutil
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
REPORTS = ROOT / "reports"
DOCS = ROOT / "docs"
SCRATCH = ROOT / "scratch"
for d in (REPORTS, DOCS, SCRATCH):
    d.mkdir(exist_ok=True)

def mv(src: Path, dst_dir: Path):
    if src.exists():
        dst = dst_dir / src.name
        if dst.exists():
            print(f"SKIP (exists): {dst}")
            return
        shutil.move(str(src), str(dst))
        print(f"{src.relative_to(ROOT)} -> {dst.relative_to(ROOT)}")

REPORT_RE = re.compile(r"^(GATE|G\d+_|FINAL_|IC_|PBO_|DSR_|COST_|CORPORATE_|FEATURE_LEAKAGE|LIQUIDITY_|TRIAL_|EXPERIMENT_|BENCHMARK_)")

# 1. Gate / audit artifacts -> reports/
for p in list(ROOT.iterdir()):
    if p.is_file() and REPORT_RE.match(p.name) and p.suffix in (".json", ".csv", ".md"):
        mv(p, REPORTS)

# 2. Architecture docs -> docs/
for name in ["ARCHITECTURE_DIAGRAM.md", "MASTER_SYSTEM_MAP.md", "SYSTEM_ARCHITECTURE.md", "RESEARCH_TRACEABILITY.md"]:
    mv(ROOT / name, DOCS)

# 3. Loose debugging junk -> scratch/
for name in ["scratch_test_live.py", "grasp-report.json", "real_clef_response.json",
             "remote_openapi.json", "terminal_verified.png", "terminal_layman_verified.png"]:
    mv(ROOT / name, SCRATCH)

# 4. generate_terminal.py -> scripts/ (uses cwd-relative paths; run from repo root)
mv(ROOT / "generate_terminal.py", ROOT / "scripts")

# 5. Duplicate nepse-historical folder at root
dup = ROOT / "nepse-historical-market-data-csv-master"
if dup.exists():
    daily = ROOT / "nepse_data_all"
    raw = ROOT / "01_raw"
    for f in dup.glob("*.csv"):
        target = daily if re.match(r"\d{4}_\d{2}_\d{2}\.csv", f.name) else raw
        if (target / f.name).exists():
            f.unlink()
            print(f"dup removed: {f.name}")
        else:
            mv(f, target)
    inner = dup / "nepse-historical-market-data-csv-master"
    if inner.exists():
        dst = raw / "nepse-historical-scraper-repo"
        if not dst.exists():
            shutil.move(str(inner), str(dst))
            print(f"inner repo -> {dst.relative_to(ROOT)}")
    if not any(dup.iterdir()):
        dup.rmdir()
        print("removed empty root nepse-historical-market-data-csv-master/")

# 6. Rewrite gate scripts so they write/read in reports/
NAME = r"(?:GATE|G\d+_|FINAL_|IC_|PBO_|DSR_|COST_|CORPORATE_|FEATURE_LEAKAGE|LIQUIDITY_|TRIAL_|EXPERIMENT_|BENCHMARK_)[A-Za-z0-9_{}\[\]:\-]*\.(?:json|csv|md)"
PAT = re.compile(r'(open\(\s*f?|to_csv\(\s*f?|_path\s*=\s*f?|_file\s*=\s*f?)"(' + NAME + r')"')
for script in sorted((ROOT / "scripts").glob("2[2-8]_*.py")):
    src = script.read_text(encoding="utf-8")
    new = PAT.sub(lambda m: f'{m.group(1)}"reports/{m.group(2)}"', src)
    if new != src:
        if "os.makedirs(\"reports\"" not in new:
            new = new.replace("def main():", 'def main():\n    os.makedirs("reports", exist_ok=True)', 1)
            if not re.search(r"^import os", new, re.M):
                new = "import os\n" + new
        script.write_text(new, encoding="utf-8")
        print(f"patched paths: {script.name}")

# 7. Fix doc links
for md in [DOCS / "MASTER_SYSTEM_MAP.md", ROOT / "README.md"]:
    if md.exists():
        t = md.read_text(encoding="utf-8")
        t2 = re.sub(r"(file:///c:/Users/achar/Downloads/neps/)(" + NAME + ")", r"\1reports/\2", t)
        t2 = t2.replace("](SYSTEM_ARCHITECTURE.md", "](docs/SYSTEM_ARCHITECTURE.md") \
               .replace("](MASTER_SYSTEM_MAP.md", "](docs/MASTER_SYSTEM_MAP.md") \
               .replace("](ARCHITECTURE_DIAGRAM.md", "](docs/ARCHITECTURE_DIAGRAM.md") \
               .replace("](RESEARCH_TRACEABILITY.md", "](docs/RESEARCH_TRACEABILITY.md")
        if t2 != t:
            md.write_text(t2, encoding="utf-8")
            print(f"updated links: {md.name}")

# 8. pytest: only collect tests/
(ROOT / "pytest.ini").write_text("[pytest]\ntestpaths = tests\n", encoding="utf-8")
print("wrote pytest.ini")

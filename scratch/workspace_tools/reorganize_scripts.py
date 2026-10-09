"""Group flat scripts/ into themed subfolders and rewrite every path reference."""
import re
import shutil
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
S = ROOT / "scripts"

GROUPS = {
    "01_etl_and_ingestion": ["init_duckdb.py", "01_build_master_union.py"],
    "02_modeling_and_calculations": [
        "02_feature_engineering.py", "03_train_and_backtest.py", "05_shap_diagnostic_protocol.py",
        "06_verify_purged_embargo_split.py", "20_test_mean_reversion_engine.py",
        "21_calibrated_mean_reversion_engine.py"],
    "05_forensic_audit_gates": [
        "11_incremental_remediation_suite.py", "12_remediation_2010_start.py", "15_execute_steps_1_to_6.py",
        "16_remediation_deliverables.py", "17_institutional_ic_audit.py", "18_run_user_modules_audit.py",
        "19_execute_nepse_audit_suite.py", "22_generate_baseline_0000.py", "23_execute_full_forensic_gates.py",
        "24_execute_gate_certification_audit.py", "25_execute_g9_g10_evaluation.py",
        "26_update_master_certification.py", "27_reconstruct_experiment_registry.py",
        "28_update_g9_certification.py"],
    "06_forecasting_and_charts": [
        "29_predict_nepse_oct5_2026.py", "30_generate_oct5_layman_chart.py",
        "32_generate_nepali_layman_chart.py", "generate_terminal.py"],
    "07_clef_multimodal": [
        "33_clef_inference_bridge.py", "34_build_clef_training_dataset.py", "35_train_clef_lora_t4.py"],
    "08_dashboard_ui": ["04_streamlit_terminal_ui.py"],
    "99_ops_and_maintenance": ["00_organize_workspace.py", "setup_daily_task_scheduler.ps1"],
}

# 1. Move
moved = {}
for folder, files in GROUPS.items():
    (S / folder).mkdir(exist_ok=True)
    for name in files:
        src = S / name
        if src.exists():
            shutil.move(str(src), str(S / folder / name))
            moved[name] = folder
            print(f"scripts/{name} -> scripts/{folder}/{name}")

# 2. Fix depth of BASE_DIR in moved files (they are now one level deeper)
for name, folder in moved.items():
    p = S / folder / name
    if p.suffix != ".py":
        continue
    t = p.read_text(encoding="utf-8")
    t2 = re.sub(r"Path\(__file__\)\.resolve\(\)\.parent\.parent(?!\.parent)",
                "Path(__file__).resolve().parent.parent.parent", t)
    # streamlit UI loads schemas relative to scripts/
    t2 = t2.replace('Path(__file__).resolve().parent / "03_data_access_and_storage"',
                    'Path(__file__).resolve().parent.parent / "03_data_access_and_storage"')
    if t2 != t:
        p.write_text(t2, encoding="utf-8")

# 3. Rewrite references everywhere
targets = [p for p in ROOT.rglob("*") if p.is_file() and p.suffix in (".py", ".md", ".ps1", ".yml", ".yaml")
           and not any(x in p.parts for x in (".git", ".codeboarding", ".codeboarding-venv", "__pycache__", ".agents", "01_raw"))]
for p in targets:
    try:
        t = p.read_text(encoding="utf-8")
    except UnicodeDecodeError:
        continue
    t2 = t
    for name, folder in moved.items():
        n = re.escape(name)
        # scripts/NAME  or scripts\NAME
        t2 = re.sub(r"(scripts[/\\])" + n, lambda m: m.group(1) + folder + m.group(1)[-1] + name, t2)
        # BASE_DIR / "scripts" / "NAME"
        t2 = re.sub(r'("scripts"\s*/\s*)"' + n + '"', lambda m: f'{m.group(1)}"{folder}" / "{name}"', t2)
    if t2 != t:
        p.write_text(t2, encoding="utf-8")
        print(f"updated refs: {p.relative_to(ROOT)}")

# 4. Remove stale caches
for c in S.rglob("__pycache__"):
    shutil.rmtree(c, ignore_errors=True)

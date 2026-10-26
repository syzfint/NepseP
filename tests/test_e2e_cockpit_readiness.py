"""
tests/test_e2e_cockpit_readiness.py

End-to-End Cockpit Readiness & Integration Verification.
Simulates run_surveillance_cockpit.bat readiness gate:
- Tests all 10 Cockpit Screen routes return HTTP 200
- Tests Screen S04 Cont-Stoikov OFI & L2 Depth UI DOM components
- Tests Screen S10 Merkle Lakehouse & 3D Overfitting Surface WebGL canvas
- Tests /ws/pulse WebSocket handshake and telemetry frame delivery
- Tests Lakehouse Master Parquet and Merkle Provenance Ledger integrity
"""

import sys
import os
import json
from pathlib import Path

import pytest
import pyarrow.parquet as pq
from fastapi.testclient import TestClient

BASE_DIR = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(BASE_DIR))

from apex_engine.main import app
from apex_engine.config import MASTER_PARQUET, MERKLE_CHAIN, OUTPUT_JSON_PATH


@pytest.fixture(scope="module")
def client():
    with TestClient(app) as test_client:
        yield test_client


def test_root_command_center(client):
    res = client.get("/")
    assert res.status_code == 200
    assert "10-SCREEN INSTITUTIONAL COCKPIT" in res.text


@pytest.mark.parametrize("screen_id, path", [
    ("S01", "/cockpit/sebon-wash-dlq"),
    ("S02", "/cockpit/preopen-spoof"),
    ("S03", "/cockpit/vpin-toxicity"),
    ("S04", "/cockpit/ofi-depth"),
    ("S05", "/cockpit/hawkes-sweeps"),
    ("S06", "/cockpit/floorsheet-hhi"),
    ("S07", "/cockpit/promoter-lockin"),
    ("S08", "/cockpit/fund-maturity"),
    ("S09", "/cockpit/news-vlm-gate4"),
    ("S10", "/cockpit/merkle-lakehouse"),
])
def test_all_10_cockpit_screens_render_200(client, screen_id, path):
    res = client.get(path)
    assert res.status_code == 200
    assert screen_id in res.text


def test_screen_s04_ofi_depth_components(client):
    res = client.get("/cockpit/ofi-depth")
    assert res.status_code == 200
    html = res.text
    # Check essential microstructure and OFI elements
    assert "CONT-STOIKOV OFI" in html
    assert "nofi-gauge-track" in html
    assert "depth-ladder" in html
    assert "Stoikov Micro-Price" in html
    assert "ws://\"" in html or "ws://${" in html or "/ws/pulse" in html


def test_screen_s10_merkle_lakehouse_components(client):
    res = client.get("/cockpit/merkle-lakehouse")
    assert res.status_code == 200
    html = res.text
    # Check essential 3D WebGL and Merkle ledger elements
    assert "three.js" in html or "Three.js" in html or "THREE." in html
    assert "OrbitControls" in html
    assert "PlaneGeometry" in html
    assert "HMAC-SHA256" in html
    assert "webgl-container" in html
    assert "/api/merkle" in html


def test_rest_api_health_and_telemetry(client):
    h = client.get("/api/health")
    assert h.status_code == 200
    data_h = h.json()
    assert data_h["status"] == "ONLINE"
    assert "merkle_provenance" in data_h

    ofi = client.get("/api/ofi")
    assert ofi.status_code == 200
    data_o = ofi.json()
    assert "symbol" in data_o
    assert "bids" in data_o
    assert "asks" in data_o
    assert "nofi" in data_o

    merkle = client.get("/api/merkle")
    assert merkle.status_code == 200
    data_m = merkle.json()
    assert data_m["status"] == "OK"
    assert "blocks" in data_m


def test_websocket_pulse_telemetry_frame(client):
    with client.websocket_connect("/ws/pulse") as websocket:
        data = websocket.receive_json()
        assert data["type"] == "TELEMETRY_PULSE"
        assert "nepse_index" in data
        assert "ofi" in data
        assert "merkle" in data
        assert data["merkle"]["valid"] is True


def test_lakehouse_and_manifest_storage():
    assert MASTER_PARQUET.exists(), f"Lakehouse master missing at {MASTER_PARQUET}"
    pf = pq.ParquetFile(str(MASTER_PARQUET))
    assert pf.metadata.num_rows > 700000, f"Expected >700k rows, found {pf.metadata.num_rows}"

    assert OUTPUT_JSON_PATH.exists(), f"Output JSON missing at {OUTPUT_JSON_PATH}"
    with open(OUTPUT_JSON_PATH, "r", encoding="utf-8") as f:
        manifest = json.load(f)
    assert "provenance_hash_h_master" in manifest
    assert "top_candidates" in manifest
    assert len(manifest["top_candidates"]) > 0

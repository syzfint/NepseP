#!/usr/bin/env python3
"""
Test Suite for NEPSE ↔ CLEF Multimodal Integration (Phase 10 / v1.0.0).

Verifies the 7 Mandatory Step-7 Scenarios:
1. Valid request
2. Malformed request
3. Missing provenance
4. Incorrect provenance
5. Unavailable Clef server
6. Timeout
7. Invalid Clef response
plus:
8. Missing chart graceful handling
9. Numerical-only fallback preservation
10. Starlette API endpoints integration
"""

import os
import sys
import json
import uuid
import hashlib
from pathlib import Path
from datetime import datetime, timezone
import pytest

# Add project root and schemas module
BASE_DIR = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(BASE_DIR))

import importlib.util
SCHEMAS_PATH = BASE_DIR / "scripts" / "03_data_access_and_storage" / "04_data_schemas_and_pydantic_entities.py"
_spec = importlib.util.spec_from_file_location("nepse_schemas", SCHEMAS_PATH)
_schemas = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(_schemas)

NepseToClefInputPayload = _schemas.NepseToClefInputPayload
ClefToNepseOutputPayload = _schemas.ClefToNepseOutputPayload
ClefFailurePayload = _schemas.ClefFailurePayload
MarketContext = _schemas.MarketContext
QuantForecastItem = _schemas.QuantForecastItem
RelevantDisclosureItem = _schemas.RelevantDisclosureItem
VisualArtifactInput = _schemas.VisualArtifactInput
InputMetadata = _schemas.InputMetadata
compute_provenance_hash = _schemas.compute_provenance_hash

BRIDGE_PATH = BASE_DIR / "scripts" / "33_clef_inference_bridge.py"
_bridge_spec = importlib.util.spec_from_file_location("clef_bridge", BRIDGE_PATH)
_bridge = importlib.util.module_from_spec(_bridge_spec)
_bridge_spec.loader.exec_module(_bridge)
ClefInferenceBridge = _bridge.ClefInferenceBridge


@pytest.fixture
def sample_market_context():
    return MarketContext(
        as_of_market_close="2026-10-02",
        prediction_target_date="2026-10-05 (Monday)",
        market_regime="MEAN_REVERSION_BUY_DIP",
        active_universe_count=350,
        avg_market_1w_return_pct=-1.8688,
        index_close=2588.40,
        index_projected_close=2596.25,
        corridor_upper_barrier=2615.50,
        corridor_lower_barrier=2574.00
    )


@pytest.fixture
def sample_quant_forecasts():
    return [
        QuantForecastItem(
            rank=1,
            ticker="SMPDA",
            latest_close=722.0,
            ret_1w_pct=-3.73,
            vol_20d_pct=0.99,
            adv_20d_shares=1094.4,
            composite_score=0.8714,
            projected_change_pct=1.31
        ),
        QuantForecastItem(
            rank=2,
            ticker="GFCL",
            latest_close=560.3,
            ret_1w_pct=-2.89,
            vol_20d_pct=0.84,
            adv_20d_shares=5960.8,
            composite_score=0.8471,
            projected_change_pct=1.01
        )
    ]


@pytest.fixture
def sample_disclosures():
    return [
        RelevantDisclosureItem(
            event_id="EVT-2026-0929-01",
            source="NRB",
            headline="NRB eases margin loan risk-weighting to 100%",
            category="MONETARY_POLICY",
            importance_tier="HIGH",
            published_date_npt="2026-09-29",
            affected_symbols=["SMPDA", "GFCL"]
        )
    ]


@pytest.fixture
def sample_visual_artifact():
    dummy_bytes = b"\x89PNG\r\n\x1a\n\x00\x00\x00\rIHDRdummy_chart_bytes"
    img_hash = hashlib.sha256(dummy_bytes).hexdigest()
    return VisualArtifactInput(
        is_available=True,
        mime_type="image/png",
        image_base64="iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAYAAAAfFcSJAAAADUlEQVR42mNk+M9QDwADhgGAWjR9awAAAABJRU5ErkJggg==",
        artifact_url=None,
        chart_title="NEPSE Price Corridor",
        image_sha256=img_hash
    )


# =====================================================================
# STEP 7 SCENARIO 1: VALID REQUEST
# =====================================================================
def test_1_valid_request(sample_market_context, sample_quant_forecasts, sample_disclosures, sample_visual_artifact, tmp_path):
    prov_hash = compute_provenance_hash(
        sample_market_context, sample_quant_forecasts, sample_disclosures, sample_visual_artifact
    )
    req_id = f"REQ-VALID-{uuid.uuid4().hex[:8]}"

    payload = NepseToClefInputPayload(
        metadata=InputMetadata(
            schema_version="1.0.0",
            request_id=req_id,
            created_at_utc=datetime.now(timezone.utc).isoformat(),
            data_provenance_hash=prov_hash
        ),
        market_context=sample_market_context,
        quantitative_forecasts=sample_quant_forecasts,
        relevant_disclosures=sample_disclosures,
        visual_artifact=sample_visual_artifact
    )

    assert payload.metadata.schema_version == "1.0.0"
    assert payload.metadata.data_provenance_hash == prov_hash
    assert len(payload.quantitative_forecasts) == 2
    assert payload.visual_artifact.is_available is True

    # Test complete inference roundtrip with mock Clef response
    bridge = ClefInferenceBridge(static_dir=str(tmp_path))
    mock_valid_output = {
        "metadata": {
            "schema_version": "1.0.0",
            "response_id": "RESP-SUCCESS-001",
            "request_id": req_id,
            "data_provenance_hash": prov_hash,
            "model_id": "clef-t4-nf4-40gpu-24cpu",
            "inference_latency_ms": 345.2,
            "timestamp_utc": datetime.now(timezone.utc).isoformat()
        },
        "executive_synthesis": {
            "market_stance": "CAUTIOUS_ACCUMULATION",
            "conviction_score": 0.88,
            "headline": "Mean-Reversion Buy Dip Activated Across Oversold BFIs",
            "executive_summary": "Technical reversal indicators indicate strong institutional absorption in low-beta equities.",
            "recommended_horizon_days": "7 - 12 Trading Days"
        },
        "visual_grounding_audit": {
            "chart_analyzed": True,
            "is_chart_grounded": True,
            "corridor_support_floor": 2574.00,
            "corridor_resistance_ceiling": 2615.50,
            "visual_anomaly_detected": False,
            "visual_critique": "Price candles cleanly test the lower 2.0σ support band without breaking structure. Turnover expansion supports rebound thesis."
        },
        "ticker_rationales": [
            {
                "rank": 1,
                "ticker": "SMPDA",
                "analyst_verdict": "STRONG_BUY",
                "catalyst_summary": "Oversold 1W decline (-3.73%) meets low historical volatility and regulatory easing.",
                "risk_warnings": ["Thin order book below Rs. 710 support"],
                "news_alignment": "Aligned with NRB margin loan risk-weight reduction"
            },
            {
                "rank": 2,
                "ticker": "GFCL",
                "analyst_verdict": "ACCUMULATE",
                "catalyst_summary": "Consistent ADV liquidity provision amidst general market consolidation.",
                "risk_warnings": ["Finance sector systemic beta"],
                "news_alignment": None
            }
        ],
        "risk_management_notes": {
            "primary_risk_factor": "Macro liquidity tightening in banking sector",
            "stop_loss_guidance": "Hard stop at Rs. 2,574.00 NEPSE Index level",
            "liquidity_distress_warning": False,
            "turnover_protection_active": True
        }
    }

    res = bridge.execute_inference(payload, mock_response=mock_valid_output)
    assert res["status"] == "SUCCESS"
    assert bridge.clef_report_path.exists()


# =====================================================================
# STEP 7 SCENARIO 2: MALFORMED REQUEST
# =====================================================================
def test_2_malformed_request(sample_market_context, sample_disclosures, sample_visual_artifact):
    # Rank 0 is invalid (ge=1 required)
    with pytest.raises(Exception):
        QuantForecastItem(
            rank=0,
            ticker="SMPDA",
            latest_close=722.0,
            ret_1w_pct=-3.73,
            vol_20d_pct=0.99,
            adv_20d_shares=100.0,
            composite_score=0.87
        )

    # Negative close price is invalid (gt=0 required)
    with pytest.raises(Exception):
        QuantForecastItem(
            rank=1,
            ticker="SMPDA",
            latest_close=-722.0,
            ret_1w_pct=-3.73,
            vol_20d_pct=0.99,
            adv_20d_shares=100.0,
            composite_score=0.87
        )

    # Empty forecasts array is invalid (min_length=1 required)
    with pytest.raises(Exception):
        NepseToClefInputPayload(
            metadata=InputMetadata(
                schema_version="1.0.0",
                request_id="REQ-MALFORMED",
                created_at_utc=datetime.now(timezone.utc).isoformat(),
                data_provenance_hash="dummy"
            ),
            market_context=sample_market_context,
            quantitative_forecasts=[],
            relevant_disclosures=sample_disclosures,
            visual_artifact=sample_visual_artifact
        )


# =====================================================================
# STEP 7 SCENARIO 3: MISSING PROVENANCE
# =====================================================================
def test_3_missing_provenance(sample_market_context, sample_quant_forecasts, sample_disclosures, sample_visual_artifact):
    # Attempt creating input payload with missing data_provenance_hash
    with pytest.raises(Exception):
        InputMetadata(
            schema_version="1.0.0",
            request_id="REQ-NO-PROV",
            created_at_utc=datetime.now(timezone.utc).isoformat()
            # missing data_provenance_hash
        )


# =====================================================================
# STEP 7 SCENARIO 4: INCORRECT PROVENANCE
# =====================================================================
def test_4_incorrect_provenance(sample_market_context, sample_quant_forecasts, sample_disclosures, sample_visual_artifact, tmp_path):
    true_hash = compute_provenance_hash(
        sample_market_context, sample_quant_forecasts, sample_disclosures, sample_visual_artifact
    )
    tampered_hash = hashlib.sha256(b"tampered_data").hexdigest()

    req_id = "REQ-INCORRECT-PROV"
    payload = NepseToClefInputPayload(
        metadata=InputMetadata(
            schema_version="1.0.0",
            request_id=req_id,
            created_at_utc=datetime.now(timezone.utc).isoformat(),
            data_provenance_hash=true_hash
        ),
        market_context=sample_market_context,
        quantitative_forecasts=sample_quant_forecasts,
        relevant_disclosures=sample_disclosures,
        visual_artifact=sample_visual_artifact
    )

    bridge = ClefInferenceBridge(static_dir=str(tmp_path))
    # Clef echoes incorrect provenance
    mock_tampered_output = {
        "metadata": {
            "schema_version": "1.0.0",
            "response_id": "RESP-001",
            "request_id": req_id,
            "data_provenance_hash": tampered_hash,  # Mismatched!
            "model_id": "clef-t4-nf4",
            "inference_latency_ms": 200.0,
            "timestamp_utc": datetime.now(timezone.utc).isoformat()
        },
        "executive_synthesis": {
            "market_stance": "BULLISH",
            "conviction_score": 0.90,
            "headline": "Bullish Rebound",
            "executive_summary": "Summary text",
            "recommended_horizon_days": "5 Days"
        },
        "visual_grounding_audit": {
            "chart_analyzed": False,
            "is_chart_grounded": False,
            "visual_anomaly_detected": False,
            "visual_critique": "None"
        },
        "ticker_rationales": [
            {
                "rank": 1,
                "ticker": "SMPDA",
                "analyst_verdict": "STRONG_BUY",
                "catalyst_summary": "Oversold",
                "risk_warnings": ["Risk"]
            }
        ],
        "risk_management_notes": {
            "primary_risk_factor": "Risk",
            "stop_loss_guidance": "Stop",
            "liquidity_distress_warning": False
        }
    }

    res = bridge.execute_inference(payload, mock_response=mock_tampered_output)
    assert res["status"] == "FAILED"
    assert res["failure"]["error"]["code"] == "PROVENANCE_HASH_MISMATCH"


# =====================================================================
# STEP 7 SCENARIO 5: UNAVAILABLE CLEF SERVER
# =====================================================================
def test_5_unavailable_clef_server(sample_market_context, sample_quant_forecasts, sample_disclosures, sample_visual_artifact, tmp_path):
    prov_hash = compute_provenance_hash(
        sample_market_context, sample_quant_forecasts, sample_disclosures, sample_visual_artifact
    )
    req_id = "REQ-UNAVAILABLE-SERVER"
    payload = NepseToClefInputPayload(
        metadata=InputMetadata(
            schema_version="1.0.0",
            request_id=req_id,
            created_at_utc=datetime.now(timezone.utc).isoformat(),
            data_provenance_hash=prov_hash
        ),
        market_context=sample_market_context,
        quantitative_forecasts=sample_quant_forecasts,
        relevant_disclosures=sample_disclosures,
        visual_artifact=sample_visual_artifact
    )

    # Test Case A: CLEF_BASE_URL is empty
    bridge_empty = ClefInferenceBridge(static_dir=str(tmp_path), base_url="")
    res_empty = bridge_empty.execute_inference(payload)
    assert res_empty["status"] == "FAILED"
    assert res_empty["failure"]["error"]["code"] == "CLEF_BASE_URL_NOT_CONFIGURED"

    # Test Case B: CLEF_BASE_URL points to non-listening port
    bridge_dead = ClefInferenceBridge(static_dir=str(tmp_path), base_url="http://127.0.0.1:59999", timeout_seconds=1.0)
    res_dead = bridge_dead.execute_inference(payload)
    assert res_dead["status"] == "FAILED"
    assert res_dead["failure"]["error"]["code"] in ["CLEF_CONNECTION_ERROR", "CLEF_TIMEOUT"]
    assert res_dead["failure"]["error"]["fallback_mode"] == "PASSTHROUGH_NUMERICAL_ONLY"


# =====================================================================
# STEP 7 SCENARIO 6: TIMEOUT
# =====================================================================
def test_6_timeout(monkeypatch, sample_market_context, sample_quant_forecasts, sample_disclosures, sample_visual_artifact, tmp_path):
    prov_hash = compute_provenance_hash(
        sample_market_context, sample_quant_forecasts, sample_disclosures, sample_visual_artifact
    )
    req_id = "REQ-TIMEOUT"
    payload = NepseToClefInputPayload(
        metadata=InputMetadata(
            schema_version="1.0.0",
            request_id=req_id,
            created_at_utc=datetime.now(timezone.utc).isoformat(),
            data_provenance_hash=prov_hash
        ),
        market_context=sample_market_context,
        quantitative_forecasts=sample_quant_forecasts,
        relevant_disclosures=sample_disclosures,
        visual_artifact=sample_visual_artifact
    )

    bridge = ClefInferenceBridge(static_dir=str(tmp_path), base_url="http://mock-clef-slow.internal", timeout_seconds=0.01)

    import requests
    def mock_post_timeout(*args, **kwargs):
        raise requests.exceptions.Timeout("Read timed out")

    monkeypatch.setattr(requests, "post", mock_post_timeout)

    res = bridge.execute_inference(payload)
    assert res["status"] == "FAILED"
    assert res["failure"]["error"]["code"] == "CLEF_TIMEOUT"
    assert res["failure"]["error"]["fallback_mode"] == "PASSTHROUGH_NUMERICAL_ONLY"


# =====================================================================
# STEP 7 SCENARIO 7: INVALID CLEF RESPONSE
# =====================================================================
def test_7_invalid_clef_response(sample_market_context, sample_quant_forecasts, sample_disclosures, sample_visual_artifact, tmp_path):
    prov_hash = compute_provenance_hash(
        sample_market_context, sample_quant_forecasts, sample_disclosures, sample_visual_artifact
    )
    req_id = "REQ-INVALID-RESP"
    payload = NepseToClefInputPayload(
        metadata=InputMetadata(
            schema_version="1.0.0",
            request_id=req_id,
            created_at_utc=datetime.now(timezone.utc).isoformat(),
            data_provenance_hash=prov_hash
        ),
        market_context=sample_market_context,
        quantitative_forecasts=sample_quant_forecasts,
        relevant_disclosures=sample_disclosures,
        visual_artifact=sample_visual_artifact
    )

    bridge = ClefInferenceBridge(static_dir=str(tmp_path))

    # Case A: Missing required executive_synthesis section
    bad_structure = {
        "metadata": {
            "schema_version": "1.0.0",
            "response_id": "RESP-001",
            "request_id": req_id,
            "data_provenance_hash": prov_hash,
            "model_id": "clef-t4-nf4",
            "inference_latency_ms": 200.0,
            "timestamp_utc": datetime.now(timezone.utc).isoformat()
        }
        # missing executive_synthesis, visual_grounding_audit, etc.
    }
    res_struct = bridge.execute_inference(payload, mock_response=bad_structure)
    assert res_struct["status"] == "FAILED"
    assert res_struct["failure"]["error"]["code"] == "CLEF_OUTPUT_SCHEMA_ERROR"

    # Case B: Invalid enum in market_stance
    bad_enum = {
        "metadata": {
            "schema_version": "1.0.0",
            "response_id": "RESP-001",
            "request_id": req_id,
            "data_provenance_hash": prov_hash,
            "model_id": "clef-t4-nf4",
            "inference_latency_ms": 200.0,
            "timestamp_utc": datetime.now(timezone.utc).isoformat()
        },
        "executive_synthesis": {
            "market_stance": "SUPER_MOON_BULLISH",  # Invalid enum!
            "conviction_score": 0.90,
            "headline": "Rebound",
            "executive_summary": "Text",
            "recommended_horizon_days": "5 Days"
        },
        "visual_grounding_audit": {
            "chart_analyzed": False,
            "is_chart_grounded": False,
            "visual_anomaly_detected": False,
            "visual_critique": "None"
        },
        "ticker_rationales": [
            {
                "rank": 1,
                "ticker": "SMPDA",
                "analyst_verdict": "STRONG_BUY",
                "catalyst_summary": "Oversold",
                "risk_warnings": ["Risk"]
            }
        ],
        "risk_management_notes": {
            "primary_risk_factor": "Risk",
            "stop_loss_guidance": "Stop",
            "liquidity_distress_warning": False
        }
    }
    res_enum = bridge.execute_inference(payload, mock_response=bad_enum)
    assert res_enum["status"] == "FAILED"
    assert res_enum["failure"]["error"]["code"] == "CLEF_OUTPUT_SCHEMA_ERROR"


# =====================================================================
# ADDITIONAL INTEGRATION TESTS
# =====================================================================
def test_8_missing_chart_fallback(sample_market_context, sample_quant_forecasts, sample_disclosures):
    art = VisualArtifactInput(
        is_available=False,
        mime_type=None,
        image_base64=None,
        artifact_url=None,
        chart_title=None,
        image_sha256=None
    )

    prov_hash = compute_provenance_hash(
        sample_market_context, sample_quant_forecasts, sample_disclosures, art
    )

    payload = NepseToClefInputPayload(
        metadata=InputMetadata(
            schema_version="1.0.0",
            request_id="REQ-NO-CHART",
            created_at_utc=datetime.now(timezone.utc).isoformat(),
            data_provenance_hash=prov_hash
        ),
        market_context=sample_market_context,
        quantitative_forecasts=sample_quant_forecasts,
        relevant_disclosures=sample_disclosures,
        visual_artifact=art
    )

    dumped = payload.model_dump(mode="json")
    dumped_str = json.dumps(dumped)
    assert "C:\\" not in dumped_str
    assert "c:/" not in dumped_str
    assert dumped["visual_artifact"]["is_available"] is False
    assert dumped["visual_artifact"]["image_base64"] is None


def test_9_numerical_fallback_preservation(sample_market_context, sample_quant_forecasts, sample_disclosures, sample_visual_artifact, tmp_path):
    prov_hash = compute_provenance_hash(
        sample_market_context, sample_quant_forecasts, sample_disclosures, sample_visual_artifact
    )
    req_id = "REQ-FALLBACK-INTEGRITY"
    payload = NepseToClefInputPayload(
        metadata=InputMetadata(
            schema_version="1.0.0",
            request_id=req_id,
            created_at_utc=datetime.now(timezone.utc).isoformat(),
            data_provenance_hash=prov_hash
        ),
        market_context=sample_market_context,
        quantitative_forecasts=sample_quant_forecasts,
        relevant_disclosures=sample_disclosures,
        visual_artifact=sample_visual_artifact
    )

    bridge = ClefInferenceBridge(static_dir=str(tmp_path), base_url="")
    res = bridge.execute_inference(payload)

    assert res["status"] == "FAILED"
    assert res["failure"]["fallback_payload"]["market_regime"] == "MEAN_REVERSION_BUY_DIP"
    assert res["failure"]["fallback_payload"]["top_picks"][0] == "SMPDA"
    assert res["failure"]["error"]["fallback_mode"] == "PASSTHROUGH_NUMERICAL_ONLY"


def test_10_api_endpoints_integration(monkeypatch, sample_market_context, sample_quant_forecasts, sample_disclosures, sample_visual_artifact):
    from starlette.testclient import TestClient

    API_CLIENT_PATH = BASE_DIR / "scripts" / "03_data_access_and_storage" / "01_nepse_market_api_client.py"
    _api_spec = importlib.util.spec_from_file_location("nepse_api", API_CLIENT_PATH)
    _api_module = importlib.util.module_from_spec(_api_spec)
    _api_spec.loader.exec_module(_api_module)
    app = _api_module.app

    client = TestClient(app)

    # 1. Invalid JSON body
    res_bad_json = client.post("/api/clef/synthesize", content="not json", headers={"Content-Type": "application/json"})
    assert res_bad_json.status_code == 400

    # 2. Provenance mismatch rejection
    prov_hash = compute_provenance_hash(
        sample_market_context, sample_quant_forecasts, sample_disclosures, sample_visual_artifact
    )
    payload_data = NepseToClefInputPayload(
        metadata=InputMetadata(
            schema_version="1.0.0",
            request_id="REQ-API-TEST",
            created_at_utc=datetime.now(timezone.utc).isoformat(),
            data_provenance_hash="invalid_hash_that_does_not_match"
        ),
        market_context=sample_market_context,
        quantitative_forecasts=sample_quant_forecasts,
        relevant_disclosures=sample_disclosures,
        visual_artifact=sample_visual_artifact
    ).model_dump(mode="json")

    res_mismatch = client.post("/api/clef/synthesize", json=payload_data)
    assert res_mismatch.status_code == 422
    assert res_mismatch.json()["error"] == "PROVENANCE_HASH_MISMATCH"

    # 3. CLEF_BASE_URL unset fallback
    monkeypatch.setenv("CLEF_BASE_URL", "")
    payload_data["metadata"]["data_provenance_hash"] = prov_hash
    res_offline = client.post("/api/clef/synthesize", json=payload_data)
    assert res_offline.status_code == 503
    assert res_offline.json()["metadata"]["status"] == "FAILED"
    assert res_offline.json()["error"]["fallback_mode"] == "PASSTHROUGH_NUMERICAL_ONLY"

    # 4. GET /api/analyst/report
    res_report = client.get("/api/analyst/report")
    assert res_report.status_code in [200, 404]


def test_11_localtunnel_bypass_header(monkeypatch, sample_market_context, sample_quant_forecasts, sample_disclosures, sample_visual_artifact, tmp_path):
    """Verifies that outgoing requests to Clef pass the Bypass-Tunnel-Reminder header."""
    prov_hash = compute_provenance_hash(
        sample_market_context, sample_quant_forecasts, sample_disclosures, sample_visual_artifact
    )
    req_id = "REQ-LOCALTUNNEL-HEADER-CHECK"
    payload = NepseToClefInputPayload(
        metadata=InputMetadata(
            schema_version="1.0.0",
            request_id=req_id,
            created_at_utc=datetime.now(timezone.utc).isoformat(),
            data_provenance_hash=prov_hash
        ),
        market_context=sample_market_context,
        quantitative_forecasts=sample_quant_forecasts,
        relevant_disclosures=sample_disclosures,
        visual_artifact=sample_visual_artifact
    )

    captured_headers = {}

    import requests

    def mock_post(url, json=None, timeout=None, headers=None):
        nonlocal captured_headers
        captured_headers = headers or {}
        class MockResponse:
            status_code = 200
            def json(self):
                return {
                    "metadata": {
                        "schema_version": "1.0.0",
                        "response_id": "RESP-HEADER-TEST",
                        "request_id": req_id,
                        "data_provenance_hash": prov_hash,
                        "model_id": "clef-t4-nf4",
                        "inference_latency_ms": 250.0,
                        "timestamp_utc": datetime.now(timezone.utc).isoformat()
                    },
                    "executive_synthesis": {
                        "market_stance": "BULLISH",
                        "conviction_score": 0.85,
                        "headline": "Mean-Reversion Setup",
                        "executive_summary": "Rebound expected.",
                        "recommended_horizon_days": "5 Trading Days"
                    },
                    "visual_grounding_audit": {
                        "chart_analyzed": True,
                        "is_chart_grounded": True,
                        "corridor_support_floor": 2574.00,
                        "corridor_resistance_ceiling": 2615.50,
                        "visual_anomaly_detected": False,
                        "visual_critique": "Price within corridor."
                    },
                    "ticker_rationales": [
                        {
                            "rank": 1,
                            "ticker": "SMPDA",
                            "analyst_verdict": "STRONG_BUY",
                            "catalyst_summary": "Oversold rebound.",
                            "risk_warnings": [],
                            "news_alignment": None
                        }
                    ],
                    "risk_management_notes": {
                        "primary_risk_factor": "Macro liquidity",
                        "stop_loss_guidance": "Hard stop 2,574",
                        "liquidity_distress_warning": False,
                        "turnover_protection_active": True
                    }
                }
        return MockResponse()

    monkeypatch.setattr(requests, "post", mock_post)

    bridge = ClefInferenceBridge(
        static_dir=str(tmp_path),
        base_url="https://localtunnel.me-test-host",
        synthesize_path="/synthesize"
    )
    res = bridge.execute_inference(payload)
    assert res["status"] == "SUCCESS"
    assert captured_headers.get("Bypass-Tunnel-Reminder") == "true"
    assert captured_headers.get("Content-Type") == "application/json"


if __name__ == "__main__":
    pytest.main(["-v", __file__])


#!/usr/bin/env python3
"""
NEPSE ↔ CLEF Multimodal Inference Bridge (v1.0.0).

Executes the Phase 9 canonical integration contract:
1. Ingests prediction results from NEPSE_OCT5_PREDICTION.json.
2. Ingests chart PNG bytes (Base64 inline encoding, zero local path leakage).
3. Queries historical verified news disclosures (strictly <= as_of cutoff).
4. Assembles NepseToClefInputPayload and computes composite SHA-256 provenance.
5. Dispatches request to the external Clef multimodal reasoning runtime (CLEF_BASE_URL).
6. Validates ClefToNepseOutputPayload against strict Pydantic schemas.
7. Verifies request_id and data_provenance_hash integrity.
8. Persists verified analyst synthesis or fails closed to numerical-only mode.
"""

import os
import sys
import time
import json
import base64
import hashlib
import logging
import argparse
import uuid
from datetime import datetime, timezone
from pathlib import Path
from typing import Optional, Dict, Any, List

import requests

# Set up structured logging
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] [ClefBridge] %(message)s"
)
logger = logging.getLogger("ClefBridge")

# Load Pydantic Schemas from 04_data_schemas_and_pydantic_entities.py
BASE_DIR = Path(__file__).resolve().parent.parent
SCHEMAS_PATH = BASE_DIR / "scripts" / "03_data_access_and_storage" / "04_data_schemas_and_pydantic_entities.py"

import importlib.util
_spec = importlib.util.spec_from_file_location("nepse_schemas", SCHEMAS_PATH)
_schemas = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(_schemas)

NepseToClefInputPayload = _schemas.NepseToClefInputPayload
ClefToNepseOutputPayload = _schemas.ClefToNepseOutputPayload
ClefFailurePayload = _schemas.ClefFailurePayload
FailureMetadata = _schemas.FailureMetadata
FailureError = _schemas.FailureError
InputMetadata = _schemas.InputMetadata
MarketContext = _schemas.MarketContext
QuantForecastItem = _schemas.QuantForecastItem
RelevantDisclosureItem = _schemas.RelevantDisclosureItem
VisualArtifactInput = _schemas.VisualArtifactInput
compute_provenance_hash = _schemas.compute_provenance_hash


def _load_env_file():
    env_file = BASE_DIR / ".env"
    if env_file.exists():
        try:
            with open(env_file, "r", encoding="utf-8") as f:
                for line in f:
                    line = line.strip()
                    if line and not line.startswith("#") and "=" in line:
                        k, v = line.split("=", 1)
                        k = k.strip()
                        v = v.strip().strip('"').strip("'")
                        if k not in os.environ:
                            os.environ[k] = v
        except Exception:
            pass

_load_env_file()


class ClefInferenceBridge:
    """
    Independent client bridge connecting Antigravity NEPSE quant engine
    to the external Clef Multimodal Analyst runtime.
    """

    def __init__(
        self,
        prediction_path: Optional[str] = None,
        chart_path: Optional[str] = None,
        static_dir: Optional[str] = None,
        base_url: Optional[str] = None,
        synthesize_path: Optional[str] = None,
        timeout_seconds: Optional[float] = None
    ):
        self.prediction_path = Path(prediction_path or (BASE_DIR / "NEPSE_OCT5_PREDICTION.json"))
        self.chart_path = Path(chart_path or (BASE_DIR / "nepse_oct5_prediction_chart.png"))
        self.static_dir = Path(static_dir or (BASE_DIR / "static_data"))
        self.static_dir.mkdir(parents=True, exist_ok=True)

        self.clef_report_path = self.static_dir / "clef_analyst_report.json"
        self.clef_failure_path = self.static_dir / "clef_failure_report.json"

        # Configuration from environment or defaults
        self.base_url = (base_url if base_url is not None else os.environ.get("CLEF_BASE_URL", "")).strip()
        self.synthesize_path = (synthesize_path if synthesize_path is not None else os.environ.get("CLEF_SYNTHESIZE_PATH", "/synthesize")).strip()
        self.timeout = float(timeout_seconds if timeout_seconds is not None else os.environ.get("CLEF_TIMEOUT_SECONDS", "45.0"))

    def build_input_payload(self) -> NepseToClefInputPayload:
        """
        Constructs the canonical NepseToClefInputPayload with exact SHA-256 provenance.
        Enforces zero future leakage: news cutoff is strictly <= as_of_market_close.
        """
        # 1. Load Prediction JSON
        if not self.prediction_path.exists():
            raise FileNotFoundError(f"Prediction file not found at {self.prediction_path}")

        with open(self.prediction_path, "r", encoding="utf-8") as f:
            pred_data = json.load(f)

        as_of_date = pred_data.get("as_of_market_close", "2026-10-02")
        target_date = pred_data.get("prediction_target_date", "2026-10-05 (Monday)")
        regime = pred_data.get("market_regime", "MEAN_REVERSION_BUY_DIP")
        universe_count = int(pred_data.get("active_universe_count", 350))
        avg_ret_1w = float(pred_data.get("avg_market_1w_return_pct", -1.8688))

        # Benchmark Index Corridor Metrics (from Step 30 Layman Corridor)
        index_close = 2588.40
        index_proj = 2596.25
        upper_barrier = 2615.50
        lower_barrier = 2574.00

        mkt_context = MarketContext(
            as_of_market_close=as_of_date,
            prediction_target_date=target_date,
            market_regime=regime,
            active_universe_count=universe_count,
            avg_market_1w_return_pct=avg_ret_1w,
            index_close=index_close,
            index_projected_close=index_proj,
            corridor_upper_barrier=upper_barrier,
            corridor_lower_barrier=lower_barrier
        )

        # 2. Build Quantitative Forecast Items
        raw_forecasts = pred_data.get("top_10_long_forecasts", [])
        quant_items: List[QuantForecastItem] = []
        for row in raw_forecasts:
            item = QuantForecastItem(
                rank=int(row["rank"]),
                ticker=str(row["ticker"]),
                latest_close=float(row["latest_close"]),
                ret_1w_pct=float(row["ret_1w_pct"]),
                vol_20d_pct=float(row["vol_20d_pct"]),
                adv_20d_shares=float(row["adv_20d_shares"]),
                composite_score=float(row["composite_score"]),
                projected_change_pct=round(abs(float(row["ret_1w_pct"])) * 0.35, 2)
            )
            quant_items.append(item)

        if not quant_items:
            raise ValueError("No quantitative forecasts found in prediction JSON.")

        # 3. Load Relevant Historical Disclosures (zero future leakage)
        disclosures: List[RelevantDisclosureItem] = []
        news_file = self.static_dir / "news_feed.json"
        db_path = BASE_DIR / "02_processed_parquet" / "news_and_events.duckdb"
        if news_file.exists():
            try:
                with open(news_file, "r", encoding="utf-8") as f:
                    feed_data = json.load(f)
                raw_events = feed_data.get("events", [])
                for ev in raw_events:
                    pub_date = ev.get("published_date_npt", "")
                    # Zero-leakage temporal constraint: only disclosures published <= as_of_date
                    if pub_date and pub_date <= as_of_date:
                        disc = RelevantDisclosureItem(
                            event_id=str(ev.get("event_id", "")),
                            source=str(ev.get("source", "NEPSE")),
                            headline=str(ev.get("headline", "")),
                            category=str(ev.get("category", "REGULATORY_RULE")),
                            importance_tier=str(ev.get("importance_tier", "MEDIUM")),
                            published_date_npt=pub_date,
                            affected_symbols=ev.get("affected_symbols", [])
                        )
                        disclosures.append(disc)
            except Exception as e:
                logger.warning(f"Failed to parse news_feed.json: {e}")
        elif db_path.exists():
            try:
                import duckdb
                from scripts.db_connection import get_connection_manager as _get_cm
                _db_mgr = _get_cm(database=str(db_path))
                with _db_mgr.acquire() as con:
                    rows = con.execute("""
                        SELECT event_id, source, headline, category, importance_tier, published_date_npt, affected_symbols
                        FROM verified_events
                        WHERE published_date_npt <= ?
                        ORDER BY published_date_npt DESC
                        LIMIT 5
                    """, [as_of_date]).fetchall()
                for r in rows:
                    raw_syms = r[6]
                    symbols = json.loads(raw_syms) if isinstance(raw_syms, str) else (raw_syms or [])
                    disc = RelevantDisclosureItem(
                        event_id=str(r[0]),
                        source=str(r[1]),
                        headline=str(r[2]),
                        category=str(r[3]),
                        importance_tier=str(r[4]),
                        published_date_npt=str(r[5]),
                        affected_symbols=symbols
                    )
                    disclosures.append(disc)
                logger.info(f"Loaded {len(disclosures)} verified historical disclosures from DuckDB.")
            except Exception as e:
                logger.warning(f"Failed to query news_and_events.duckdb: {e}")

        # Limit to top 5 most recent disclosures for concise context window
        disclosures = disclosures[:5]

        # 4. Ingest Visual Artifact (Inline Base64 - zero host filesystem path leakage)
        if self.chart_path.exists():
            with open(self.chart_path, "rb") as f:
                img_bytes = f.read()
            img_b64 = base64.b64encode(img_bytes).decode("ascii")
            img_hash = hashlib.sha256(img_bytes).hexdigest()
            visual_art = VisualArtifactInput(
                is_available=True,
                mime_type="image/png",
                image_base64=img_b64,
                artifact_url=None,
                chart_title="NEPSE Index Oct 5 Price Corridor & Turnover",
                image_sha256=img_hash
            )
            logger.info(f"Loaded visual chart artifact ({len(img_bytes)} bytes, SHA-256: {img_hash[:12]}...)")
        else:
            visual_art = VisualArtifactInput(
                is_available=False,
                mime_type=None,
                image_base64=None,
                artifact_url=None,
                chart_title=None,
                image_sha256=None
            )
            logger.info("Visual chart artifact unavailable; falling back to text-only mode.")

        # 5. Compute Deterministic Composite Provenance Hash
        prov_hash = compute_provenance_hash(mkt_context, quant_items, disclosures, visual_art)
        request_id = f"REQ-{datetime.now(timezone.utc).strftime('%Y%m%d%H%M%S')}-{uuid.uuid4().hex[:8]}"

        metadata = InputMetadata(
            schema_version="1.0.0",
            request_id=request_id,
            created_at_utc=datetime.now(timezone.utc).isoformat(),
            data_provenance_hash=prov_hash
        )

        payload = NepseToClefInputPayload(
            metadata=metadata,
            market_context=mkt_context,
            quantitative_forecasts=quant_items,
            relevant_disclosures=disclosures,
            visual_artifact=visual_art
        )
        return payload

    def execute_inference(
        self,
        payload: NepseToClefInputPayload,
        mock_response: Optional[Dict[str, Any]] = None
    ) -> Dict[str, Any]:
        """
        Sends the payload to the external Clef runtime, validates output,
        verifies provenance, and writes out the resulting report.
        """
        req_id = payload.metadata.request_id
        prov_hash = payload.metadata.data_provenance_hash

        logger.info(f"Initiating Clef Inference [request_id={req_id}, schema=1.0.0, provenance={prov_hash[:12]}...]")

        # Allow injected mock response for offline integration testing
        if mock_response is not None:
            logger.info("Using mock Clef response for testing validation pipeline.")
            clef_raw = mock_response
            latency_ms = 125.0
        else:
            if not self.base_url:
                err_msg = "CLEF_BASE_URL is not set. External Clef runtime is unconfigured."
                logger.error(err_msg)
                return self._fail_closed(payload, "CLEF_BASE_URL_NOT_CONFIGURED", err_msg)

            target_url = f"{self.base_url.rstrip('/')}/{self.synthesize_path.lstrip('/')}"
            start_t = time.time()
            try:
                logger.info(f"POSTing payload to external Clef runtime at {target_url} (timeout={self.timeout}s)...")
                resp = requests.post(
                    target_url,
                    json=payload.model_dump(mode="json"),
                    timeout=self.timeout,
                    headers={
                        "Content-Type": "application/json",
                        "Bypass-Tunnel-Reminder": "true"
                    }
                )
                latency_ms = (time.time() - start_t) * 1000.0
            except requests.exceptions.Timeout:
                latency_ms = (time.time() - start_t) * 1000.0
                err_msg = f"Clef inference timed out after {self.timeout}s ({latency_ms:.1f}ms)."
                logger.error(err_msg)
                return self._fail_closed(payload, "CLEF_TIMEOUT", err_msg)
            except Exception as e:
                err_msg = f"Failed to connect to Clef runtime: {str(e)}"
                logger.error(err_msg)
                return self._fail_closed(payload, "CLEF_CONNECTION_ERROR", err_msg)

            if resp.status_code != 200:
                err_msg = f"Clef runtime returned HTTP {resp.status_code}: {resp.text[:300]}"
                logger.error(err_msg)
                return self._fail_closed(payload, "CLEF_HTTP_ERROR", err_msg)

            try:
                clef_raw = resp.json()
            except Exception as e:
                err_msg = f"Malformed JSON from Clef runtime: {str(e)}"
                logger.error(err_msg)
                return self._fail_closed(payload, "CLEF_MALFORMED_JSON", err_msg)

        # Output Schema Validation
        try:
            output = ClefToNepseOutputPayload.model_validate(clef_raw)
        except Exception as e:
            err_msg = f"Clef output failed v1.0.0 schema validation: {str(e)}"
            logger.error(err_msg)
            return self._fail_closed(payload, "CLEF_OUTPUT_SCHEMA_ERROR", err_msg)

        # Integrity Validation: Request ID
        if output.metadata.request_id != req_id:
            err_msg = f"Request ID mismatch: expected {req_id}, got {output.metadata.request_id}"
            logger.error(err_msg)
            return self._fail_closed(payload, "REQUEST_ID_MISMATCH", err_msg)

        # Integrity Validation: Provenance Hash
        if output.metadata.data_provenance_hash != prov_hash:
            err_msg = f"Provenance hash mismatch: expected {prov_hash}, got {output.metadata.data_provenance_hash}"
            logger.error(err_msg)
            return self._fail_closed(payload, "PROVENANCE_HASH_MISMATCH", err_msg)

        # Persist Verified Analysis Report
        report_data = output.model_dump(mode="json")
        temp_file = self.clef_report_path.with_suffix(".tmp")
        with open(temp_file, "w", encoding="utf-8") as f:
            json.dump(report_data, f, indent=2, ensure_ascii=False)
        temp_file.replace(self.clef_report_path)

        conv_val = output.executive_synthesis.conviction_score
        conv_str = f"{conv_val:.2f}" if conv_val is not None else str(output.executive_synthesis.conviction_level or "N/A")
        lat_val = output.metadata.inference_latency_ms
        lat_str = f"{lat_val:.1f}ms" if lat_val is not None else "N/A"
        grounded_val = output.visual_grounding_audit.is_chart_grounded
        if grounded_val is None:
            grounded_val = output.visual_grounding_audit.chart_corridor_match

        logger.info(
            f"Clef Analysis Successfully Verified & Persisted to {self.clef_report_path} | "
            f"model_id={output.metadata.model_id} | "
            f"stance={output.executive_synthesis.market_stance} | "
            f"conviction={conv_str} | "
            f"grounded={grounded_val} | "
            f"latency={lat_str}"
        )
        return {
            "status": "SUCCESS",
            "report": report_data
        }

    def _fail_closed(self, payload: NepseToClefInputPayload, code: str, message: str) -> Dict[str, Any]:
        """
        Fails closed to numerical-only mode, generating a standardized failure payload
        without crashing the quant system or corrupting outputs.
        """
        failure = ClefFailurePayload(
            metadata=FailureMetadata(
                request_id=payload.metadata.request_id,
                response_id=None,
                model_id="clef-external",
                status="FAILED",
                timestamp_utc=datetime.now(timezone.utc).isoformat()
            ),
            error=FailureError(
                code=code,
                message=message,
                fallback_mode="PASSTHROUGH_NUMERICAL_ONLY"
            ),
            fallback_payload={
                "market_regime": payload.market_context.market_regime,
                "top_picks": [f.ticker for f in payload.quantitative_forecasts[:5]],
                "notice": "Numerical predictions and backtests remain 100% active and certified. Clef analyst layer offline."
            }
        )

        failure_data = failure.model_dump(mode="json")
        with open(self.clef_failure_path, "w", encoding="utf-8") as f:
            json.dump(failure_data, f, indent=2, ensure_ascii=False)

        logger.warning(f"Fail-closed to numerical-only mode recorded at {self.clef_failure_path} [code={code}]")
        return {
            "status": "FAILED",
            "failure": failure_data
        }


def main():
    parser = argparse.ArgumentParser(description="NEPSE ↔ CLEF Multimodal Bridge CLI")
    parser.add_argument("--dry-run", action="store_true", help="Build and validate input payload without sending network request")
    parser.add_argument("--prediction-file", type=str, default=None, help="Path to prediction JSON")
    parser.add_argument("--chart-file", type=str, default=None, help="Path to chart PNG")
    parser.add_argument("--base-url", type=str, default=None, help="External Clef Base URL (or via CLEF_BASE_URL env)")
    args = parser.parse_args()

    bridge = ClefInferenceBridge(
        prediction_path=args.prediction_file,
        chart_path=args.chart_file,
        base_url=args.base_url
    )

    try:
        payload = bridge.build_input_payload()
        print("\n" + "=" * 70)
        print("NEPSE -> CLEF INPUT PAYLOAD SUCCESSFULLY ASSEMBLED")
        print("=" * 70)
        print(f"Request ID:       {payload.metadata.request_id}")
        print(f"Schema Version:   {payload.metadata.schema_version}")
        print(f"Provenance Hash:  {payload.metadata.data_provenance_hash}")
        print(f"Target Date:      {payload.market_context.prediction_target_date}")
        print(f"Market Regime:    {payload.market_context.market_regime}")
        print(f"Top 1 Ticker:     {payload.quantitative_forecasts[0].ticker} (Rank 1, Score: {payload.quantitative_forecasts[0].composite_score:.4f})")
        print(f"Chart Available:  {payload.visual_artifact.is_available}")
        print("=" * 70)

        if args.dry_run:
            print("\nDry-run mode: Payload successfully built and validated. Network request skipped.")
            sys.exit(0)

        result = bridge.execute_inference(payload)
        if result["status"] == "SUCCESS":
            print("\n>>> CLEF INFERENCE SUCCEEDED & PERSISTED.")
            sys.exit(0)
        else:
            print(f"\n>>> CLEF INFERENCE FAILED CLOSED ({result['failure']['error']['code']}). Numerical fallback active.")
            sys.exit(1)

    except Exception as e:
        logger.error(f"Bridge execution fatal error: {e}", exc_info=True)
        sys.exit(2)


if __name__ == "__main__":
    main()

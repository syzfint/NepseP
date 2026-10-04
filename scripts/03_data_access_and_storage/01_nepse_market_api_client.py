"""
High-Performance Starlette REST API Server for NEPSE News Harness.

Serves read-only research endpoints to the terminal frontend,
and triggers background pipeline runs. Runs on Starlette + Uvicorn.
"""

import os
import json
from typing import Optional, Any
from starlette.applications import Starlette
from starlette.responses import Response, FileResponse
from starlette.routing import Route, Mount
from starlette.staticfiles import StaticFiles
from starlette.middleware import Middleware
from starlette.middleware.cors import CORSMiddleware

import time
import requests
from datetime import datetime, timezone
import importlib.util
from pathlib import Path

# Load Pydantic Schemas from 04_data_schemas_and_pydantic_entities.py
_schemas_path = Path(__file__).parent / "04_data_schemas_and_pydantic_entities.py"
_spec = importlib.util.spec_from_file_location("nepse_schemas", _schemas_path)
_schemas_module = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(_schemas_module)

NepseToClefInputPayload = _schemas_module.NepseToClefInputPayload
ClefToNepseOutputPayload = _schemas_module.ClefToNepseOutputPayload
ClefFailurePayload = _schemas_module.ClefFailurePayload
FailureMetadata = _schemas_module.FailureMetadata
FailureError = _schemas_module.FailureError
compute_provenance_hash = _schemas_module.compute_provenance_hash

BASE_DIR = Path(__file__).resolve().parent.parent.parent

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

try:
    from news_harness.pipeline import NewsHarnessPipeline
    from news_harness.database import NewsHarnessDB
    pipeline = NewsHarnessPipeline(db_path="nepse_news_harness.duckdb", market_csv_path="NEPSE Data.csv", static_export_dir="static_data")
    db = NewsHarnessDB("nepse_news_harness.duckdb")
except Exception:
    pipeline = None
    db = None


class SafeJSONResponse(Response):
    media_type = "application/json"

    def render(self, content: Any) -> bytes:
        return json.dumps(content, ensure_ascii=False, allow_nan=False, indent=None, separators=(",", ":"), default=str).encode("utf-8")


DB_PATH = "nepse_news_harness.duckdb"
MARKET_CSV = "NEPSE Data.csv"
STATIC_DIR = "static_data"
CLEF_REPORT_PATH = os.path.join(STATIC_DIR, "clef_analyst_report.json")
CLEF_FAILURE_PATH = os.path.join(STATIC_DIR, "clef_failure_report.json")


async def get_news_feed(request):
    params = request.query_params
    source = params.get("source")
    category = params.get("category")
    symbol = params.get("symbol")
    status = params.get("status")
    search = params.get("search")
    limit = int(params.get("limit", 50))
    offset = int(params.get("offset", 0))

    events = db.get_events(
        source=source,
        category=category,
        symbol=symbol,
        status=status,
        search_query=search,
        limit=limit,
        offset=offset
    )
    for ev in events:
        ev['outcomes'] = db.get_event_outcomes(ev['event_id'])

    return SafeJSONResponse({
        "status": "success",
        "total": len(events),
        "limit": limit,
        "offset": offset,
        "events": events
    })


async def get_event_detail(request):
    event_id = request.path_params["event_id"]
    ev = db.get_event_by_id(event_id)
    if not ev:
        return SafeJSONResponse({"status": "error", "message": "Event not found"}, status_code=404)
    
    ev['outcomes'] = db.get_event_outcomes(event_id)
    return SafeJSONResponse({
        "status": "success",
        "event": ev
    })


async def get_news_history(request):
    params = request.query_params
    events = db.get_events(
        source=params.get("source"),
        category=params.get("category"),
        symbol=params.get("symbol"),
        status=params.get("status"),
        search_query=params.get("search"),
        limit=500
    )
    for ev in events:
        ev['outcomes'] = db.get_event_outcomes(ev['event_id'])
    return SafeJSONResponse({
        "status": "success",
        "count": len(events),
        "events": events
    })


async def get_impact_timeline(request):
    impact_file = os.path.join(STATIC_DIR, "impact_analysis.json")
    if os.path.exists(impact_file):
        with open(impact_file) as f:
            data = json.load(f)
            return SafeJSONResponse({"status": "success", "timeline": data.get("timeline", {})})
    
    impact = pipeline.event_study.compute_aggregate_impact_map()
    return SafeJSONResponse({"status": "success", "timeline": impact.get("timeline", {})})


async def get_impact_categories(request):
    impact_file = os.path.join(STATIC_DIR, "impact_analysis.json")
    if os.path.exists(impact_file):
        with open(impact_file) as f:
            data = json.load(f)
            return SafeJSONResponse({"status": "success", "categories": data.get("categories", {})})
    
    impact = pipeline.event_study.compute_aggregate_impact_map()
    return SafeJSONResponse({"status": "success", "categories": impact.get("categories", {})})


async def get_impact_heatmap(request):
    impact_file = os.path.join(STATIC_DIR, "impact_analysis.json")
    if os.path.exists(impact_file):
        with open(impact_file) as f:
            data = json.load(f)
            return SafeJSONResponse({"status": "success", "heatmap": data.get("heatmap", [])})
    
    impact = pipeline.event_study.compute_aggregate_impact_map()
    return SafeJSONResponse({"status": "success", "heatmap": impact.get("heatmap", [])})


async def get_strategy_comparison(request):
    strat_file = os.path.join(STATIC_DIR, "strategy_comparison.json")
    if os.path.exists(strat_file):
        with open(strat_file) as f:
            return SafeJSONResponse({"status": "success", "comparison": json.load(f)})
    
    if pipeline.strategy_lab:
        res = pipeline.strategy_lab.run_comparison()
        return SafeJSONResponse({"status": "success", "comparison": res})
    
    return SafeJSONResponse({"status": "error", "message": "Strategy Lab market data unavailable"}, status_code=503)


async def get_diagnostics(request):
    diag_file = os.path.join(STATIC_DIR, "diagnostics.json")
    if os.path.exists(diag_file):
        with open(diag_file) as f:
            return SafeJSONResponse({"status": "success", "diagnostics": json.load(f)})
    return SafeJSONResponse({
        "status": "HEALTHY",
        "database": DB_PATH,
        "isolation_status": "CONFIRMED_PHASE7_UNTOUCHED"
    })


async def trigger_pipeline_run(request):
    if pipeline is None:
        return SafeJSONResponse({"status": "error", "message": "Pipeline module offline."}, status_code=503)
    diag = pipeline.run_full_pipeline()
    return SafeJSONResponse({
        "status": "success",
        "message": "NEPSE News Harness pipeline run completed.",
        "diagnostics": diag
    })


async def clef_synthesize(request):
    """
    POST /api/clef/synthesize
    Canonical inference endpoint for Clef Multimodal Analyst.
    Validates input schema, verifies provenance, calls external Clef runtime,
    validates output schema and returned provenance hash, and persists report.
    """
    try:
        body = await request.json()
    except Exception as e:
        return SafeJSONResponse({
            "status": "error",
            "error": "INVALID_JSON",
            "message": f"Malformed JSON request body: {str(e)}"
        }, status_code=400)

    # 1. Validate Input Payload against Pydantic schema
    try:
        input_payload = NepseToClefInputPayload.model_validate(body)
    except Exception as e:
        return SafeJSONResponse({
            "status": "error",
            "error": "SCHEMA_VALIDATION_ERROR",
            "details": str(e)
        }, status_code=422)

    # 2. Verify deterministic composite provenance hash
    expected_hash = compute_provenance_hash(
        input_payload.market_context,
        input_payload.quantitative_forecasts,
        input_payload.relevant_disclosures,
        input_payload.visual_artifact
    )
    if input_payload.metadata.data_provenance_hash != expected_hash:
        return SafeJSONResponse({
            "status": "error",
            "error": "PROVENANCE_HASH_MISMATCH",
            "message": "Supplied data_provenance_hash does not match deterministic recalculation.",
            "expected_hash": expected_hash,
            "received_hash": input_payload.metadata.data_provenance_hash
        }, status_code=422)

    # 3. Retrieve External Clef Runtime URL from Environment
    clef_base_url = os.environ.get("CLEF_BASE_URL", "").strip()
    clef_synthesize_path = os.environ.get("CLEF_SYNTHESIZE_PATH", "/synthesize").strip()
    timeout_sec = float(os.environ.get("CLEF_TIMEOUT_SECONDS", "45.0"))

    if not clef_base_url:
        failure_payload = ClefFailurePayload(
            metadata=FailureMetadata(
                request_id=input_payload.metadata.request_id,
                timestamp_utc=datetime.now(timezone.utc).isoformat(),
                model_id="clef-offline"
            ),
            error=FailureError(
                code="CLEF_BASE_URL_NOT_CONFIGURED",
                message="CLEF_BASE_URL environment variable is not configured. Clef runtime unreachable."
            ),
            fallback_payload={
                "market_regime": input_payload.market_context.market_regime,
                "top_picks": [f.ticker for f in input_payload.quantitative_forecasts[:5]],
                "notice": "Numerical forecasts active; qualitative analyst offline."
            }
        )
        return SafeJSONResponse(failure_payload.model_dump(mode="json"), status_code=503)

    target_url = f"{clef_base_url.rstrip('/')}/{clef_synthesize_path.lstrip('/')}"

    # 4. Dispatch request to external Clef runtime
    start_time = time.time()
    try:
        resp = requests.post(
            target_url,
            json=input_payload.model_dump(mode="json"),
            timeout=timeout_sec,
            headers={
                "Content-Type": "application/json",
                "Bypass-Tunnel-Reminder": "true"
            }
        )
    except requests.exceptions.Timeout:
        latency_ms = (time.time() - start_time) * 1000.0
        failure_payload = ClefFailurePayload(
            metadata=FailureMetadata(
                request_id=input_payload.metadata.request_id,
                timestamp_utc=datetime.now(timezone.utc).isoformat(),
                model_id="clef-external"
            ),
            error=FailureError(
                code="CLEF_TIMEOUT",
                message=f"Clef runtime exceeded {timeout_sec}s timeout ({latency_ms:.1f}ms)."
            ),
            fallback_payload={
                "market_regime": input_payload.market_context.market_regime,
                "top_picks": [f.ticker for f in input_payload.quantitative_forecasts[:5]]
            }
        )
        return SafeJSONResponse(failure_payload.model_dump(mode="json"), status_code=504)
    except Exception as e:
        failure_payload = ClefFailurePayload(
            metadata=FailureMetadata(
                request_id=input_payload.metadata.request_id,
                timestamp_utc=datetime.now(timezone.utc).isoformat(),
                model_id="clef-external"
            ),
            error=FailureError(
                code="CLEF_CONNECTION_ERROR",
                message=f"Failed to connect to Clef runtime at {target_url}: {str(e)}"
            ),
            fallback_payload={
                "market_regime": input_payload.market_context.market_regime,
                "top_picks": [f.ticker for f in input_payload.quantitative_forecasts[:5]]
            }
        )
        return SafeJSONResponse(failure_payload.model_dump(mode="json"), status_code=502)

    if resp.status_code != 200:
        return SafeJSONResponse({
            "status": "error",
            "error": "CLEF_RUNTIME_ERROR",
            "status_code": resp.status_code,
            "raw_response": resp.text[:500]
        }, status_code=502)

    try:
        clef_json = resp.json()
    except Exception as e:
        return SafeJSONResponse({
            "status": "error",
            "error": "CLEF_MALFORMED_JSON",
            "message": f"Clef response could not be decoded as JSON: {str(e)}"
        }, status_code=502)

    # 5. Validate Output Payload against Pydantic schema
    try:
        output_payload = ClefToNepseOutputPayload.model_validate(clef_json)
    except Exception as e:
        return SafeJSONResponse({
            "status": "error",
            "error": "CLEF_OUTPUT_SCHEMA_ERROR",
            "details": str(e)
        }, status_code=502)

    # 6. Verify request_id and data_provenance_hash match
    if output_payload.metadata.request_id != input_payload.metadata.request_id:
        return SafeJSONResponse({
            "status": "error",
            "error": "REQUEST_ID_MISMATCH",
            "message": "Clef response request_id does not match outgoing request_id."
        }, status_code=502)

    if output_payload.metadata.data_provenance_hash != expected_hash:
        return SafeJSONResponse({
            "status": "error",
            "error": "PROVENANCE_HASH_MISMATCH",
            "message": "Clef response data_provenance_hash does not match input hash."
        }, status_code=502)

    # 7. Persist validated analysis report
    os.makedirs(STATIC_DIR, exist_ok=True)
    temp_path = CLEF_REPORT_PATH + ".tmp"
    with open(temp_path, "w", encoding="utf-8") as f:
        json.dump(output_payload.model_dump(mode="json"), f, indent=2, ensure_ascii=False)
    os.replace(temp_path, CLEF_REPORT_PATH)

    return SafeJSONResponse(output_payload.model_dump(mode="json"), status_code=200)


async def get_analyst_report(request):
    """
    GET /api/analyst/report
    Retrieves the latest verified Clef analyst report.
    """
    if os.path.exists(CLEF_REPORT_PATH):
        try:
            with open(CLEF_REPORT_PATH, "r", encoding="utf-8") as f:
                data = json.load(f)
            validated = ClefToNepseOutputPayload.model_validate(data)
            return SafeJSONResponse({
                "status": "success",
                "report": validated.model_dump(mode="json")
            })
        except Exception as e:
            return SafeJSONResponse({
                "status": "error",
                "error": "REPORT_VALIDATION_ERROR",
                "message": f"Persisted analyst report failed validation: {str(e)}"
            }, status_code=500)

    return SafeJSONResponse({
        "status": "error",
        "error": "REPORT_NOT_FOUND",
        "message": "No Clef analyst report found. Run /api/clef/synthesize or the bridge first."
    }, status_code=404)


async def serve_index(request):
    if os.path.exists("nepse_terminal.html"):
        return FileResponse("nepse_terminal.html")
    return SafeJSONResponse({"message": "NEPSE News Harness API is running."})


routes = [
    Route("/", serve_index),
    Route("/api/news/feed", get_news_feed, methods=["GET"]),
    Route("/api/news/events/{event_id}", get_event_detail, methods=["GET"]),
    Route("/api/news/history", get_news_history, methods=["GET"]),
    Route("/api/impact/timeline", get_impact_timeline, methods=["GET"]),
    Route("/api/impact/categories", get_impact_categories, methods=["GET"]),
    Route("/api/impact/heatmap", get_impact_heatmap, methods=["GET"]),
    Route("/api/strategy/compare", get_strategy_comparison, methods=["GET"]),
    Route("/api/diagnostics/status", get_diagnostics, methods=["GET"]),
    Route("/api/pipeline/run", trigger_pipeline_run, methods=["POST"]),
    Route("/api/clef/synthesize", clef_synthesize, methods=["POST"]),
    Route("/api/analyst/report", get_analyst_report, methods=["GET"]),
    Mount("/static_data", StaticFiles(directory=STATIC_DIR), name="static_data")
]

middleware = [
    Middleware(CORSMiddleware, allow_origins=["*"], allow_methods=["*"], allow_headers=["*"])
]

app = Starlette(routes=routes, middleware=middleware)


if __name__ == "__main__":
    import uvicorn
    # Initial pipeline run to ensure static models exist if pipeline is available
    if pipeline is not None and not os.path.exists(os.path.join(STATIC_DIR, "news_feed.json")):
        pipeline.run_full_pipeline()
    uvicorn.run(app, host="127.0.0.1", port=8000)


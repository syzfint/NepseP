"""
Data models and typed contracts for the NEPSE News Harness.
All models are strictly typed and immutable/idempotent safe.
"""

import json
from dataclasses import dataclass, field, asdict
from datetime import datetime, date, timezone
from enum import Enum
from typing import List, Optional, Dict, Any, Union


class DisclosureSource(str, Enum):
    NRB = "NRB"              # Nepal Rastra Bank (Central Bank)
    SEBON = "SEBON"          # Securities Board of Nepal (Regulator)
    NEPSE = "NEPSE"          # Nepal Stock Exchange (Exchange notices)
    COMPANY = "COMPANY"      # Listed Company / Issuer Disclosures
    GOVERNMENT = "GOVERNMENT"# Ministry of Finance / Official Gazette


class EventCategory(str, Enum):
    MONETARY_POLICY = "MONETARY_POLICY"          # Interest rates, CRR, repo, macroprudential caps (e.g. 12/15/20 cr margin loan cap)
    REGULATORY_RULE = "REGULATORY_RULE"          # Margin lending norms, circuit breaker, broker rules, SEBON directives
    ISSUER_DISCLOSURE = "ISSUER_DISCLOSURE"      # Dividend declaration, right share, quarterly financial reports, AGM
    SECTOR_POLICY = "SECTOR_POLICY"              # Hydropower PPA, insurance capital hike, commercial bank merger mandates
    MACRO_ECONOMIC = "MACRO_ECONOMIC"            # Inflation, remittance figures, budget, fiscal policy


class EventScope(str, Enum):
    BROAD_MARKET = "BROAD_MARKET"
    SECTOR = "SECTOR"
    ISSUER = "ISSUER"


class VerificationStatus(str, Enum):
    VERIFIED = "VERIFIED"          # Exact source document snapshot hashed & retrieved
    UNVERIFIED = "UNVERIFIED"      # Ingested via headline/reference without full document snapshot
    PROTOTYPE = "PROTOTYPE"        # Research calibration fixture (clearly labeled)


class ProcessingStatus(str, Enum):
    INGESTED = "INGESTED"
    VERIFIED = "VERIFIED"
    LINKED = "LINKED"
    ANALYZED = "ANALYZED"
    UNLINKED = "UNLINKED"
    FAILED = "FAILED"


class EventTimingConvention(str, Enum):
    PRE_MARKET = "PRE_MARKET"         # Published before 11:00 AM NPT on trading day -> T0 is today
    IN_SESSION = "IN_SESSION"         # Published 11:00 AM - 3:00 PM NPT -> T0 is today (or T+1 if past cutoff)
    POST_MARKET = "POST_MARKET"       # Published after 3:00 PM NPT -> T0 is next trading day
    WEEKEND_HOLIDAY = "WEEKEND_HOLIDAY"# Published on Fri/Sat/Holiday -> T0 is next trading day


@dataclass
class RawDisclosure:
    """Raw disclosure ingested from official disclosure sources."""
    source: DisclosureSource
    source_url: str
    headline: str
    body_text: str
    published_npt: datetime
    retrieved_at: datetime
    raw_hash: str
    verification_status: VerificationStatus = VerificationStatus.VERIFIED
    source_metadata: Dict[str, Any] = field(default_factory=dict)


@dataclass
class VerifiedEvent:
    """Verified and classified news event record."""
    event_id: str
    source: DisclosureSource
    source_url: str
    headline: str
    summary: str
    body_hash: str
    published_npt: str  # ISO string
    retrieved_at: str   # ISO string
    
    # Classification (Ex-Ante Importance)
    category: EventCategory
    scope: EventScope
    confidence: float
    classifier_version: str
    importance_tier: str  # 'HIGH', 'MEDIUM', 'LOW'
    
    # Calendar alignment
    published_date_npt: str     # YYYY-MM-DD
    timing_convention: EventTimingConvention
    t0_date: str                # Target market trading session (YYYY-MM-DD)
    t_minus_1_date: str         # Last session strictly before T0 (YYYY-MM-DD)
    
    # Mapping details
    affected_broad_market: bool = False
    affected_sectors: List[str] = field(default_factory=list)
    affected_symbols: List[str] = field(default_factory=list)
    mapping_rationale: str = ""
    
    # Processing state
    status: ProcessingStatus = ProcessingStatus.INGESTED
    verification_status: VerificationStatus = VerificationStatus.VERIFIED
    failure_reason: Optional[str] = None
    created_at: str = field(default_factory=lambda: datetime.now(timezone.utc).isoformat())

    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)


@dataclass
class PreEventMarketFeatures:
    """Point-in-time market state measured strictly at or before T-1."""
    event_id: str
    t_minus_1_date: str
    market_turnover: float
    market_return_1d: float
    market_volatility_20d: float
    market_breadth_advance_pct: float
    is_valid: bool = True
    missing_reason: Optional[str] = None


@dataclass
class HorizonOutcome:
    """Measured market reaction for a specific entity over a horizon."""
    horizon_label: str       # e.g., 'T0', 'T+1', 'T+3', 'T+5', 'T+20', 'T-1', 'T-5'
    session_offset: int      # relative trading session offset (e.g. 0, 1, 3, 5, 20)
    target_date: str         # actual trading session date (YYYY-MM-DD)
    raw_return: float        # asset return over window
    benchmark_return: float  # NEPSE index return over identical window
    mar: float               # Market-Adjusted Return (raw_return - benchmark_return)
    volume_ratio: float      # Volume vs 20d pre-event average
    turnover_ratio: float    # Turnover vs 20d pre-event average


@dataclass
class EventStudyRecord:
    """Complete event study observation for an entity (Market / Sector / Symbol)."""
    event_id: str
    entity_type: str         # 'MARKET', 'SECTOR', 'SYMBOL'
    entity_id: str           # e.g. 'NEPSE', 'COMMERCIAL_BANKS', 'NABIL'
    t0_date: str
    t_minus_1_date: str
    outcomes: Dict[str, HorizonOutcome] = field(default_factory=dict)
    pre_event_vol_20d: Optional[float] = None
    post_event_vol_5d: Optional[float] = None
    has_overlapping_event: bool = False
    overlapping_event_ids: List[str] = field(default_factory=list)
    quality_status: str = "COMPLETE" # 'COMPLETE', 'PARTIAL', 'MISSING_DATA'
    notes: str = ""

    def to_dict(self) -> Dict[str, Any]:
        d = asdict(self)
        return d


# =====================================================================
# CLEF MULTIMODAL INTEGRATION CONTRACT (v1.0.0)
# =====================================================================
import hashlib
from pydantic import BaseModel, Field, ConfigDict


def to_canonical_dict(obj: Any) -> Any:
    if hasattr(obj, "model_dump"):
        return obj.model_dump(mode="json")
    elif hasattr(obj, "to_dict"):
        return obj.to_dict()
    elif isinstance(obj, list):
        return [to_canonical_dict(item) for item in obj]
    elif isinstance(obj, dict):
        return {k: to_canonical_dict(v) for k, v in obj.items()}
    return obj


def canonical_json_dumps(obj: Any) -> str:
    """Serializes object to deterministic canonical JSON with sorted keys and minimal separators."""
    converted = to_canonical_dict(obj)
    return json.dumps(converted, sort_keys=True, separators=(",", ":"), ensure_ascii=False)


def compute_provenance_hash(
    market_context: Any,
    quantitative_forecasts: Any,
    relevant_disclosures: Any,
    visual_artifact: Any
) -> str:
    """
    Computes exact SHA-256 composite provenance hash across all 4 contract components:
    H_ctx = SHA256(canonical(market_context))
    H_fcst = SHA256(canonical(quantitative_forecasts))
    H_disc = SHA256(canonical(relevant_disclosures))
    H_vis = image_sha256 if is_available else SHA256(b"")
    H_master = SHA256(H_ctx + ":" + H_fcst + ":" + H_disc + ":" + H_vis)
    """
    ctx_str = canonical_json_dumps(market_context)
    h_ctx = hashlib.sha256(ctx_str.encode("utf-8")).hexdigest()

    fcst_str = canonical_json_dumps(quantitative_forecasts)
    h_fcst = hashlib.sha256(fcst_str.encode("utf-8")).hexdigest()

    disc_str = canonical_json_dumps(relevant_disclosures)
    h_disc = hashlib.sha256(disc_str.encode("utf-8")).hexdigest()

    # Visual hash
    if hasattr(visual_artifact, "is_available"):
        is_avail = visual_artifact.is_available
        img_hash = getattr(visual_artifact, "image_sha256", None)
    elif isinstance(visual_artifact, dict):
        is_avail = visual_artifact.get("is_available", False)
        img_hash = visual_artifact.get("image_sha256")
    else:
        is_avail = False
        img_hash = None

    if is_avail and img_hash:
        h_vis = str(img_hash)
    else:
        h_vis = hashlib.sha256(b"").hexdigest()

    composite_src = f"{h_ctx}:{h_fcst}:{h_disc}:{h_vis}"
    return hashlib.sha256(composite_src.encode("utf-8")).hexdigest()


class MarketStanceEnum(str, Enum):
    BULLISH = "BULLISH"
    BEARISH = "BEARISH"
    NEUTRAL = "NEUTRAL"
    CAUTIOUS_ACCUMULATION = "CAUTIOUS_ACCUMULATION"


class AnalystVerdictEnum(str, Enum):
    STRONG_BUY = "STRONG_BUY"
    ACCUMULATE = "ACCUMULATE"
    HOLD = "HOLD"
    AVOID = "AVOID"


class InputMetadata(BaseModel):
    model_config = ConfigDict(extra="forbid")
    schema_version: str = Field(default="1.0.0")
    request_id: str
    created_at_utc: str
    data_provenance_hash: str


class MarketContext(BaseModel):
    model_config = ConfigDict(extra="forbid")
    as_of_market_close: str
    prediction_target_date: str
    market_regime: str
    active_universe_count: int = Field(ge=1)
    avg_market_1w_return_pct: float
    index_close: float = Field(gt=0)
    index_projected_close: float = Field(gt=0)
    corridor_upper_barrier: float = Field(gt=0)
    corridor_lower_barrier: float = Field(gt=0)


class QuantForecastItem(BaseModel):
    model_config = ConfigDict(extra="forbid")
    rank: int = Field(ge=1)
    ticker: str
    latest_close: float = Field(gt=0)
    ret_1w_pct: float
    vol_20d_pct: float = Field(ge=0)
    adv_20d_shares: float = Field(ge=0)
    composite_score: float = Field(ge=0.0, le=1.0)
    projected_change_pct: Optional[float] = None


class RelevantDisclosureItem(BaseModel):
    model_config = ConfigDict(extra="forbid")
    event_id: str
    source: str
    headline: str
    category: str
    importance_tier: str
    published_date_npt: str
    affected_symbols: List[str] = Field(default_factory=list)


class VisualArtifactInput(BaseModel):
    model_config = ConfigDict(extra="forbid")
    is_available: bool
    mime_type: Optional[str] = None
    image_base64: Optional[str] = None
    artifact_url: Optional[str] = None
    chart_title: Optional[str] = None
    image_sha256: Optional[str] = None


class NepseToClefInputPayload(BaseModel):
    model_config = ConfigDict(extra="forbid")
    metadata: InputMetadata
    market_context: MarketContext
    quantitative_forecasts: List[QuantForecastItem] = Field(min_length=1)
    relevant_disclosures: List[RelevantDisclosureItem] = Field(default_factory=list)
    visual_artifact: VisualArtifactInput


class OutputMetadata(BaseModel):
    model_config = ConfigDict(extra="ignore")
    schema_version: str = Field(default="1.0.0")
    response_id: str
    request_id: str
    data_provenance_hash: str
    model_id: str
    inference_latency_ms: Optional[float] = None
    timestamp_utc: str
    status: Optional[str] = None


class ExecutiveSynthesis(BaseModel):
    model_config = ConfigDict(extra="ignore")
    market_stance: MarketStanceEnum
    conviction_score: Optional[float] = None
    conviction_level: Optional[str] = None
    headline: Optional[str] = None
    executive_summary: Optional[str] = None
    primary_drivers: Optional[List[str]] = None
    macro_sector_context: Optional[str] = None
    recommended_horizon_days: Optional[str] = None


class VisualGroundingAudit(BaseModel):
    model_config = ConfigDict(extra="ignore")
    chart_analyzed: Optional[bool] = None
    is_chart_grounded: Optional[bool] = None
    chart_corridor_match: Optional[bool] = None
    support_resistance_conformance: Optional[bool] = None
    corridor_support_floor: Optional[float] = None
    corridor_resistance_ceiling: Optional[float] = None
    visual_anomaly_detected: bool = False
    visual_critique: Optional[str] = None
    corridor_notes: Optional[str] = None


class TickerRationaleItem(BaseModel):
    model_config = ConfigDict(extra="ignore")
    rank: int = Field(ge=1)
    ticker: str
    analyst_verdict: Optional[Union[AnalystVerdictEnum, str]] = None
    catalyst_summary: Optional[str] = None
    risk_warnings: List[str] = Field(default_factory=list)
    news_alignment: Optional[str] = None


class RiskManagementNotes(BaseModel):
    model_config = ConfigDict(extra="ignore")
    primary_risk_factor: Optional[str] = None
    stop_loss_guidance: Optional[str] = None
    liquidity_distress_warning: Optional[bool] = None
    turnover_protection_active: Optional[bool] = None


class ResearchCitationItem(BaseModel):
    model_config = ConfigDict(extra="ignore")
    event_id: Optional[str] = None
    citation_text: Optional[str] = None
    relevance_summary: Optional[str] = None


class RiskAndInvalidation(BaseModel):
    model_config = ConfigDict(extra="ignore")
    invalidation_conditions: List[str] = Field(default_factory=list)
    downside_risk_summary: Optional[str] = None


class ClefToNepseOutputPayload(BaseModel):
    model_config = ConfigDict(extra="ignore")
    metadata: OutputMetadata
    executive_synthesis: ExecutiveSynthesis
    visual_grounding_audit: VisualGroundingAudit
    research_citations: Optional[List[Union[ResearchCitationItem, Dict[str, Any]]]] = None
    risk_and_invalidation: Optional[Union[RiskAndInvalidation, Dict[str, Any]]] = None
    ticker_rationales: Optional[List[TickerRationaleItem]] = None
    risk_management_notes: Optional[RiskManagementNotes] = None


class FailureError(BaseModel):
    model_config = ConfigDict(extra="forbid")
    code: str
    message: str
    fallback_mode: str = "PASSTHROUGH_NUMERICAL_ONLY"


class FailureMetadata(BaseModel):
    model_config = ConfigDict(extra="forbid")
    schema_version: str = "1.0.0"
    request_id: str
    response_id: Optional[str] = None
    model_id: str = "clef-external"
    status: str = "FAILED"
    timestamp_utc: str


class ClefFailurePayload(BaseModel):
    model_config = ConfigDict(extra="forbid")
    metadata: FailureMetadata
    error: FailureError
    fallback_payload: Dict[str, Any] = Field(default_factory=dict)


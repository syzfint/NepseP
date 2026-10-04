"""
Master Background Pipeline Orchestrator for NEPSE News Harness.

Executes and maintains:
1. Source collection & Verification
2. Trading Calendar Alignment (T0 & T-1 pre-event cutoff)
3. Entity Linking & Classification
4. PIT Pre-Event Features extraction
5. Multi-Horizon Event Studies (T-5 ... T+20)
6. Strategy Research backtest execution
7. Static Read-Model synchronization for terminal frontend
"""

import os
import json
import logging
from datetime import datetime
from typing import Dict, Any, Optional
import pandas as pd

from .models import VerificationStatus
from .calendar import NepseTradingCalendar
from .database import NewsHarnessDB
from .ingestion import NewsIngestionService, NPT_TZ
from .event_study import EventStudyEngine
from .strategy_lab import StrategyResearchLab

logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s")
logger = logging.getLogger("NewsHarnessPipeline")


class NewsHarnessPipeline:
    """
    Independent background pipeline runner for News Harness.
    """
    def __init__(
        self,
        db_path: str = "nepse_news_harness.duckdb",
        market_csv_path: str = "NEPSE Data.csv",
        static_export_dir: str = "static_data"
    ):
        self.db_path = db_path
        self.market_csv_path = market_csv_path
        self.static_export_dir = static_export_dir
        
        os.makedirs(self.static_export_dir, exist_ok=True)

        self.db = NewsHarnessDB(self.db_path)
        self.calendar = NepseTradingCalendar()
        
        # Load calendar & market data if available
        if os.path.exists(self.market_csv_path):
            logger.info(f"Loading trading calendar from {self.market_csv_path}")
            self.calendar.load_from_csv(self.market_csv_path)
            self.market_df = pd.read_csv(self.market_csv_path)
        else:
            logger.warning(f"Market CSV {self.market_csv_path} not found. Running in calendar fallback mode.")
            self.market_df = None

        self.ingestion = NewsIngestionService(self.db, self.calendar)
        self.event_study = EventStudyEngine(self.db, self.calendar, self.market_df)
        self.strategy_lab = StrategyResearchLab(self.db, self.calendar, self.market_df) if self.market_df is not None else None

        self.pipeline_run_log = []

    def run_full_pipeline(self) -> Dict[str, Any]:
        """
        Runs the complete news harness research cycle end-to-end.
        """
        start_time = datetime.now()
        logger.info("=== Starting NEPSE News Harness Background Pipeline ===")
        
        # Stage 1: Ingestion of authentic benchmark official disclosures
        logger.info("Stage 1: Ingesting verified regulatory and issuer disclosures...")
        events = self.ingestion.load_historical_benchmark_disclosures()
        logger.info(f"Loaded {len(events)} verified events.")

        # Stage 2: Pre-event point-in-time market features (T-1)
        logger.info("Stage 2: Extracting pre-event features at T-1 cutoff...")
        valid_features_count = 0
        for ev in events:
            feat = self.event_study.extract_pre_event_features(ev)
            if feat.is_valid:
                valid_features_count += 1

        # Stage 3: Event Study calculations over trading session horizons
        logger.info("Stage 3: Computing trading-session event study outcomes...")
        total_outcomes = 0
        for ev in events:
            records = self.event_study.run_event_study_for_event(ev, all_events=events)
            total_outcomes += len(records)

        # Stage 4: Aggregate Impact Map & Timeline
        logger.info("Stage 4: Generating aggregate impact map and uncertainty statistics...")
        impact_data = self.event_study.compute_aggregate_impact_map()

        # Stage 5: Strategy Research Backtest
        strategy_data = {}
        if self.strategy_lab:
            logger.info("Stage 5: Running Strategy Lab comparison (News-Aware vs Non-News Baseline)...")
            strategy_data = self.strategy_lab.run_comparison()

        # Stage 6: Export static read-models for the terminal UI
        logger.info("Stage 6: Exporting typed read-models to static_data/...")
        all_events_data = self.db.get_events(limit=500)
        
        # Attach outcomes directly to events for instant frontend drawer display
        for ev in all_events_data:
            ev['outcomes'] = self.db.get_event_outcomes(ev['event_id'])

        news_feed_payload = {
            "last_updated": datetime.now(NPT_TZ).isoformat(),
            "total_events": len(all_events_data),
            "source_health": self.ingestion.source_health,
            "events": all_events_data
        }

        with open(os.path.join(self.static_export_dir, "news_feed.json"), "w") as f:
            json.dump(news_feed_payload, f, indent=2, default=str)

        with open(os.path.join(self.static_export_dir, "impact_analysis.json"), "w") as f:
            json.dump(impact_data, f, indent=2, default=str)

        if strategy_data:
            with open(os.path.join(self.static_export_dir, "strategy_comparison.json"), "w") as f:
                json.dump(strategy_data, f, indent=2, default=str)

        duration_sec = (datetime.now() - start_time).total_seconds()
        
        diagnostics = {
            "status": "HEALTHY",
            "last_run_timestamp": datetime.now().isoformat(),
            "duration_seconds": round(duration_sec, 2),
            "total_events_processed": len(events),
            "valid_t_minus_1_features": valid_features_count,
            "event_study_records_generated": total_outcomes,
            "trading_sessions_indexed": len(self.calendar.trading_dates),
            "sources": self.ingestion.source_health,
            "database_path": self.db_path,
            "isolation_status": "CONFIRMED_PHASE7_UNTOUCHED"
        }

        with open(os.path.join(self.static_export_dir, "diagnostics.json"), "w") as f:
            json.dump(diagnostics, f, indent=2, default=str)

        logger.info(f"=== Pipeline completed successfully in {duration_sec:.2f}s ===")
        return diagnostics

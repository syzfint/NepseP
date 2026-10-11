"""
Database layer for the NEPSE News Harness using DuckDB.
Implements:
- Strict scalar extraction from query results (fixes tuple assignment bugs).
- Idempotent event upserts with cryptographic provenance (SHA-256 hashes).
- Fail-closed querying: returns None / raises specific errors on missing records.
- Complete schemas for news events, raw disclosures, event mappings, outcomes, and audit logs.
"""

import os
import json
import duckdb
from contextlib import contextmanager
from typing import List, Optional, Dict, Any, Tuple
from datetime import datetime
from .models import (
    VerifiedEvent, RawDisclosure, PreEventMarketFeatures,
    EventStudyRecord, HorizonOutcome, DisclosureSource,
    EventCategory, EventScope, VerificationStatus,
    ProcessingStatus, EventTimingConvention
)
from scripts.db_connection import get_connection_manager


class NewsHarnessDB:
    """
    Manages the News Harness DuckDB storage and isolation from Phase 7 baseline.
    """
    def __init__(self, db_path: str = "nepse_news_harness.duckdb"):
        self.db_path = db_path
        self._db_mgr = get_connection_manager(database=db_path)
        self._init_db()

    @contextmanager
    def _get_connection(self):
        """Yield a pooled connection via the connection manager."""
        with self._db_mgr.acquire() as conn:
            yield conn

    def _init_db(self):
        """Initializes tables and indexes with strict schemas."""
        with self._get_connection() as conn:
            # 1. Raw disclosures table
            conn.execute("""
            CREATE TABLE IF NOT EXISTS raw_disclosures (
                raw_hash VARCHAR PRIMARY KEY,
                source VARCHAR NOT NULL,
                source_url VARCHAR NOT NULL,
                headline VARCHAR NOT NULL,
                body_text TEXT NOT NULL,
                published_npt TIMESTAMP NOT NULL,
                retrieved_at TIMESTAMP NOT NULL,
                verification_status VARCHAR NOT NULL,
                source_metadata JSON,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            );
            """)

            # 2. Verified events table
            conn.execute("""
            CREATE TABLE IF NOT EXISTS verified_events (
                event_id VARCHAR PRIMARY KEY,
                source VARCHAR NOT NULL,
                source_url VARCHAR NOT NULL,
                headline VARCHAR NOT NULL,
                summary TEXT,
                body_hash VARCHAR NOT NULL,
                published_npt VARCHAR NOT NULL,
                retrieved_at VARCHAR NOT NULL,
                category VARCHAR NOT NULL,
                scope VARCHAR NOT NULL,
                confidence DOUBLE NOT NULL,
                classifier_version VARCHAR NOT NULL,
                importance_tier VARCHAR NOT NULL,
                published_date_npt VARCHAR NOT NULL,
                timing_convention VARCHAR NOT NULL,
                t0_date VARCHAR NOT NULL,
                t_minus_1_date VARCHAR NOT NULL,
                affected_broad_market BOOLEAN NOT NULL,
                affected_sectors JSON,
                affected_symbols JSON,
                mapping_rationale TEXT,
                status VARCHAR NOT NULL,
                verification_status VARCHAR NOT NULL,
                failure_reason TEXT,
                created_at VARCHAR NOT NULL
            );
            """)

            # 3. Point-in-Time Market Features (T-1 snapshot)
            conn.execute("""
            CREATE TABLE IF NOT EXISTS pre_event_market_features (
                event_id VARCHAR PRIMARY KEY,
                t_minus_1_date VARCHAR NOT NULL,
                market_turnover DOUBLE,
                market_return_1d DOUBLE,
                market_volatility_20d DOUBLE,
                market_breadth_advance_pct DOUBLE,
                is_valid BOOLEAN NOT NULL,
                missing_reason TEXT,
                recorded_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            );
            """)

            # 4. Event Study Outcomes
            conn.execute("""
            CREATE TABLE IF NOT EXISTS event_study_outcomes (
                outcome_id VARCHAR PRIMARY KEY,
                event_id VARCHAR NOT NULL,
                entity_type VARCHAR NOT NULL,
                entity_id VARCHAR NOT NULL,
                horizon_label VARCHAR NOT NULL,
                session_offset INTEGER NOT NULL,
                target_date VARCHAR NOT NULL,
                raw_return DOUBLE NOT NULL,
                benchmark_return DOUBLE NOT NULL,
                mar DOUBLE NOT NULL,
                volume_ratio DOUBLE,
                turnover_ratio DOUBLE,
                has_overlapping_event BOOLEAN DEFAULT FALSE,
                quality_status VARCHAR NOT NULL,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            );
            """)

            # 5. Audit log table
            conn.execute("""
            CREATE TABLE IF NOT EXISTS news_audit_logs (
                log_id INTEGER PRIMARY KEY,
                event_id VARCHAR,
                action VARCHAR NOT NULL,
                details TEXT,
                timestamp TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            );
            CREATE SEQUENCE IF NOT EXISTS news_audit_seq START 1;
            """)

    def upsert_raw_disclosure(self, raw: RawDisclosure) -> bool:
        """Idempotently saves raw disclosure snapshot."""
        with self._get_connection() as conn:
            # Check if exists by raw_hash
            cur = conn.execute("SELECT raw_hash FROM raw_disclosures WHERE raw_hash = ?", [raw.raw_hash])
            existing = cur.fetchone()
            if existing is not None:
                # Already ingested, preserve original snapshot
                return False

            conn.execute("""
            INSERT INTO raw_disclosures (
                raw_hash, source, source_url, headline, body_text,
                published_npt, retrieved_at, verification_status, source_metadata
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
            """, [
                raw.raw_hash, raw.source.value, raw.source_url, raw.headline,
                raw.body_text, raw.published_npt, raw.retrieved_at,
                raw.verification_status.value, json.dumps(raw.source_metadata)
            ])
            return True

    def upsert_verified_event(self, event: VerifiedEvent) -> bool:
        """Idempotently saves verified event record."""
        with self._get_connection() as conn:
            # Check if event_id exists
            cur = conn.execute("SELECT event_id FROM verified_events WHERE event_id = ?", [event.event_id])
            existing = cur.fetchone()
            
            sectors_json = json.dumps(event.affected_sectors)
            symbols_json = json.dumps(event.affected_symbols)

            if existing is not None:
                # Update mutable processing status while preserving core provenance
                conn.execute("""
                UPDATE verified_events SET
                    summary = ?, status = ?, verification_status = ?,
                    failure_reason = ?, affected_sectors = ?, affected_symbols = ?,
                    mapping_rationale = ?
                WHERE event_id = ?
                """, [
                    event.summary, event.status.value, event.verification_status.value,
                    event.failure_reason, sectors_json, symbols_json,
                    event.mapping_rationale, event.event_id
                ])
                return False
            else:
                conn.execute("""
                INSERT INTO verified_events (
                    event_id, source, source_url, headline, summary, body_hash,
                    published_npt, retrieved_at, category, scope, confidence,
                    classifier_version, importance_tier, published_date_npt,
                    timing_convention, t0_date, t_minus_1_date, affected_broad_market,
                    affected_sectors, affected_symbols, mapping_rationale, status,
                    verification_status, failure_reason, created_at
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """, [
                    event.event_id, event.source.value, event.source_url, event.headline,
                    event.summary, event.body_hash, event.published_npt, event.retrieved_at,
                    event.category.value, event.scope.value, event.confidence,
                    event.classifier_version, event.importance_tier, event.published_date_npt,
                    event.timing_convention.value, event.t0_date, event.t_minus_1_date,
                    event.affected_broad_market, sectors_json, symbols_json,
                    event.mapping_rationale, event.status.value, event.verification_status.value,
                    event.failure_reason, event.created_at
                ])
                return True

    def save_market_features(self, feat: PreEventMarketFeatures):
        """Saves point-in-time pre-event market features."""
        with self._get_connection() as conn:
            conn.execute("""
            INSERT OR REPLACE INTO pre_event_market_features (
                event_id, t_minus_1_date, market_turnover, market_return_1d,
                market_volatility_20d, market_breadth_advance_pct, is_valid, missing_reason
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?)
            """, [
                feat.event_id, feat.t_minus_1_date, feat.market_turnover,
                feat.market_return_1d, feat.market_volatility_20d,
                feat.market_breadth_advance_pct, feat.is_valid, feat.missing_reason
            ])

    def save_outcome(self, event_id: str, record: EventStudyRecord):
        """Saves all horizon outcomes for an event study record."""
        with self._get_connection() as conn:
            for label, outcome in record.outcomes.items():
                outcome_id = f"{event_id}_{record.entity_type}_{record.entity_id}_{label}"
                conn.execute("""
                INSERT OR REPLACE INTO event_study_outcomes (
                    outcome_id, event_id, entity_type, entity_id,
                    horizon_label, session_offset, target_date,
                    raw_return, benchmark_return, mar,
                    volume_ratio, turnover_ratio, has_overlapping_event, quality_status
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """, [
                    outcome_id, event_id, record.entity_type, record.entity_id,
                    outcome.horizon_label, outcome.session_offset, outcome.target_date,
                    outcome.raw_return, outcome.benchmark_return, outcome.mar,
                    outcome.volume_ratio, outcome.turnover_ratio,
                    record.has_overlapping_event, record.quality_status
                ])

    def get_events(
        self,
        source: Optional[str] = None,
        category: Optional[str] = None,
        symbol: Optional[str] = None,
        status: Optional[str] = None,
        search_query: Optional[str] = None,
        limit: int = 100,
        offset: int = 0
    ) -> List[Dict[str, Any]]:
        """Queries events with filters and scalar tuple unwrapping."""
        with self._get_connection() as conn:
            query = "SELECT * FROM verified_events WHERE 1=1"
            params = []

            if source:
                query += " AND source = ?"
                params.append(source)
            if category:
                query += " AND category = ?"
                params.append(category)
            if status:
                query += " AND status = ?"
                params.append(status)
            if search_query:
                query += " AND (lower(headline) LIKE ? OR lower(summary) LIKE ?)"
                pattern = f"%{search_query.lower()}%"
                params.extend([pattern, pattern])

            query += " ORDER BY published_npt DESC LIMIT ? OFFSET ?"
            params.extend([limit, offset])

            cur = conn.execute(query, params)
            cols = [desc[0] for desc in cur.description]
            rows = cur.fetchall()

            events = []
            for row in rows:
                ev = dict(zip(cols, row))
                # Parse JSON fields safely
                if isinstance(ev.get('affected_sectors'), str):
                    ev['affected_sectors'] = json.loads(ev['affected_sectors'])
                if isinstance(ev.get('affected_symbols'), str):
                    ev['affected_symbols'] = json.loads(ev['affected_symbols'])
                
                # Filter by symbol if requested
                if symbol and symbol.upper() not in [s.upper() for s in ev.get('affected_symbols', [])]:
                    continue
                
                events.append(ev)

            return events

    def get_event_by_id(self, event_id: str) -> Optional[Dict[str, Any]]:
        """Fetches single event by event_id."""
        with self._get_connection() as conn:
            cur = conn.execute("SELECT * FROM verified_events WHERE event_id = ?", [event_id])
            cols = [desc[0] for desc in cur.description]
            row = cur.fetchone()
            if row is None:
                return None
            ev = dict(zip(cols, row))
            if isinstance(ev.get('affected_sectors'), str):
                ev['affected_sectors'] = json.loads(ev['affected_sectors'])
            if isinstance(ev.get('affected_symbols'), str):
                ev['affected_symbols'] = json.loads(ev['affected_symbols'])
            return ev

    def get_event_outcomes(self, event_id: str) -> List[Dict[str, Any]]:
        """Fetches all outcome records for a given event_id."""
        with self._get_connection() as conn:
            cur = conn.execute("""
            SELECT * FROM event_study_outcomes 
            WHERE event_id = ? 
            ORDER BY session_offset ASC
            """, [event_id])
            cols = [desc[0] for desc in cur.description]
            rows = cur.fetchall()
            return [dict(zip(cols, r)) for r in rows]

    def get_all_outcomes(self) -> List[Dict[str, Any]]:
        """Fetches all event outcomes with event metadata joined."""
        with self._get_connection() as conn:
            cur = conn.execute("""
            SELECT 
                o.outcome_id, o.event_id, o.entity_type, o.entity_id,
                o.horizon_label, o.session_offset, o.target_date,
                o.raw_return, o.benchmark_return, o.mar,
                o.volume_ratio, o.turnover_ratio, o.has_overlapping_event, o.quality_status,
                e.category, e.scope, e.importance_tier, e.source, e.headline, e.t0_date
            FROM event_study_outcomes o
            JOIN verified_events e ON o.event_id = e.event_id
            ORDER BY o.event_id, o.session_offset
            """)
            cols = [desc[0] for desc in cur.description]
            return [dict(zip(cols, r)) for r in cur.fetchall()]

    def count_events(self) -> int:
        """Returns total number of verified events safely."""
        with self._get_connection() as conn:
            cur = conn.execute("SELECT COUNT(*) FROM verified_events")
            row = cur.fetchone()
            if row is None:
                return 0
            return int(row[0])  # Scalar extraction!

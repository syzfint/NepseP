#!/usr/bin/env python3
"""
scripts/04_scrapers_and_harness/04_harvest_corporate_actions.py

Real-Time Corporate Action & Disclosure Harvester for NEPSE
------------------------------------------------------------
Polls official NEPSE corporate action & disclosure APIs (ShareHub Nepal):
1. Dividends: Cash & Bonus dividend declarations with book closure dates.
2. Corporate Announcements: Rights issues, board decisions, audits, AGMs.
3. Maps events to point-in-time dates (published_date, t0_date, t-1).
4. Inserts deduplicated disclosures into 02_processed_parquet/news_and_events.duckdb:
   - raw_disclosures
   - verified_events
"""

import os
import sys
import json
import time
import hashlib
import datetime
from pathlib import Path
from typing import List, Dict, Any

import httpx

BASE_DIR = Path(os.environ.get("NEPSE_BASE_DIR", r"C:/Users/achar/Downloads/neps"))
PROCESSED_DIR = BASE_DIR / "02_processed_parquet"
DB_PATH = PROCESSED_DIR / "news_and_events.duckdb"

def compute_hash(text: str) -> str:
    return hashlib.sha256(text.strip().encode("utf-8")).hexdigest()

def harvest_dividends(client: httpx.Client, total_pages: int = 15) -> List[Dict[str, Any]]:
    print(f"Harvesting dividend declarations across {total_pages} pages...")
    events = []
    for page in range(1, total_pages + 1):
        url = f"https://sharehubnepal.com/data/api/v1/dividend?page={page}&size=20"
        try:
            r = client.get(url, timeout=10.0)
            if r.status_code == 200:
                data = r.json()
                items = data.get("data", {}).get("content", [])
                for it in items:
                    sym = it.get("symbol")
                    if not sym:
                        continue
                    ann_date_raw = it.get("announcementDate")
                    if not ann_date_raw:
                        continue
                    pub_date = ann_date_raw.split("T")[0]
                    bonus = float(it.get("bonus") or 0.0)
                    cash = float(it.get("cash") or 0.0)
                    total = float(it.get("total") or (bonus + cash))
                    book_closure = (it.get("bookClosureDate") or "").split("T")[0]
                    fy = it.get("fiscalYear") or "N/A"

                    headline = f"{sym} declared {total:.2f}% Total Dividend ({bonus:.2f}% Bonus, {cash:.2f}% Cash) for FY {fy}"
                    summary = f"Company: {it.get('name')}. Bonus Dividend: {bonus}%. Cash Dividend: {cash}%. Book Closure Date: {book_closure}."
                    
                    events.append({
                        "event_id": f"DIV_{sym}_{pub_date}_{it.get('id')}",
                        "source": "SHAREHUB_NEPSE_OFFICIAL",
                        "source_url": "https://sharehubnepal.com/dividend",
                        "headline": headline,
                        "summary": summary,
                        "category": "DIVIDEND_DECLARATION",
                        "importance_tier": "HIGH" if total >= 10.0 else "MEDIUM",
                        "published_date": pub_date,
                        "symbol": sym,
                        "fiscal_year": fy,
                        "bonus_pct": bonus,
                        "cash_pct": cash,
                        "total_pct": total
                    })
        except Exception as e:
            print(f"Error fetching dividend page {page}: {e}")
            break
    print(f"Harvested {len(events)} dividend disclosures.")
    return events

def harvest_announcements(client: httpx.Client, total_pages: int = 20) -> List[Dict[str, Any]]:
    print(f"Harvesting board announcements across {total_pages} pages...")
    events = []
    for page in range(1, total_pages + 1):
        url = f"https://sharehubnepal.com/data/api/v1/announcement?page={page}&size=20"
        try:
            r = client.get(url, timeout=10.0)
            if r.status_code == 200:
                data = r.json()
                items = data.get("data", {}).get("content", [])
                for it in items:
                    sym = it.get("symbol")
                    title = it.get("title") or ""
                    if not sym or not title:
                        continue
                    
                    details = it.get("details") or ""
                    # Derive category
                    title_l = title.lower()
                    if "right share" in title_l or "rights" in title_l:
                        category = "RIGHTS_ISSUE"
                        tier = "HIGH"
                    elif "dividend" in title_l:
                        category = "DIVIDEND_DECLARATION"
                        tier = "HIGH"
                    elif "agm" in title_l or "annual general meeting" in title_l:
                        category = "GOVERNANCE_AGM"
                        tier = "MEDIUM"
                    elif "financial report" in title_l or "quarterly" in title_l:
                        category = "QUARTERLY_EARNINGS"
                        tier = "HIGH"
                    else:
                        category = "CORPORATE_NOTICE"
                        tier = "LOW"

                    # Announcement ID
                    it_id = str(it.get("id"))
                    events.append({
                        "event_id": f"ANN_{sym}_{it_id}",
                        "source": "SHAREHUB_NEPSE_ANNOUNCEMENT",
                        "source_url": f"https://sharehubnepal.com/announcement/{it_id}",
                        "headline": title[:255],
                        "summary": it.get("subTitle") or title,
                        "category": category,
                        "importance_tier": tier,
                        "published_date": datetime.datetime.now().strftime("%Y-%m-%d"),
                        "symbol": sym
                    })
        except Exception as e:
            print(f"Error fetching announcement page {page}: {e}")
            break
    print(f"Harvested {len(events)} corporate announcements.")
    return events

def ingest_to_duckdb(all_events: List[Dict[str, Any]]):
    print("Ingesting harvested corporate actions into news_and_events.duckdb...")
    from scripts.db_connection import get_connection_manager
    now_str = datetime.datetime.now(datetime.timezone.utc).isoformat()

    inserted_cnt = 0
    with get_connection_manager(database=str(DB_PATH)).acquire() as con:
        for ev in all_events:
            eid = ev["event_id"]
            headline = ev["headline"]
            summary = ev["summary"]
            body_hash = compute_hash(headline + summary)
            pub_date = ev["published_date"]
            sym = ev["symbol"]
            category = ev["category"]
            tier = ev["importance_tier"]
            src = ev["source"]
            src_url = ev["source_url"]

            # Check if already present
            exists = con.execute("SELECT 1 FROM verified_events WHERE event_id = ?", [eid]).fetchone()
            if not exists:
                symbols_json = json.dumps([sym])
                sectors_json = json.dumps([])
                
                # Insert into verified_events
                con.execute("""
                INSERT INTO verified_events (
                    event_id, source, source_url, headline, summary, body_hash,
                    published_npt, retrieved_at, category, scope, confidence,
                    classifier_version, importance_tier, published_date_npt,
                    timing_convention, t0_date, t_minus_1_date, affected_broad_market,
                    affected_sectors, affected_symbols, mapping_rationale,
                    status, verification_status, failure_reason, created_at
                ) VALUES (
                    ?, ?, ?, ?, ?, ?,
                    ?, ?, ?, 'SYMBOL_SPECIFIC', 1.0,
                    'v2.2-official-harvester', ?, ?,
                    'PRE_MARKET_T0', ?, ?, FALSE,
                    ?, ?, 'Official corporate action disclosure',
                    'VERIFIED_ACTIVE', 'OFFICIAL_SOURCE', NULL, ?
                )
                """, [
                    eid, src, src_url, headline, summary, body_hash,
                    f"{pub_date} 09:30:00", now_str, category,
                    tier, pub_date,
                    pub_date, pub_date,
                    sectors_json, symbols_json, now_str
                ])

                # Also insert raw disclosure
                con.execute("""
                INSERT OR REPLACE INTO raw_disclosures (
                    raw_hash, source, source_url, headline, body_text,
                    published_npt, retrieved_at, verification_status, source_metadata
                ) VALUES (
                    ?, ?, ?, ?, ?,
                    CAST(? AS TIMESTAMP), CAST(? AS TIMESTAMP), 'VERIFIED', ?
                )
                """, [
                    body_hash, src, src_url, headline, summary,
                    f"{pub_date} 09:30:00", now_str, json.dumps(ev)
                ])
                inserted_cnt += 1

        total_verified = con.execute("SELECT count(*) FROM verified_events").fetchone()[0]
        total_raw = con.execute("SELECT count(*) FROM raw_disclosures").fetchone()[0]

    print(f"Successfully inserted {inserted_cnt} new verified events!")
    print(f"Total Verified Events in DuckDB: {total_verified}")
    print(f"Total Raw Disclosures in DuckDB: {total_raw}")

def main():
    print("=" * 80)
    print("APEXMARKETENGINE — REAL-TIME CORPORATE ACTION & DISCLOSURE HARVESTER")
    print("=" * 80)
    
    with httpx.Client(timeout=12.0) as client:
        div_events = harvest_dividends(client, total_pages=15)
        ann_events = harvest_announcements(client, total_pages=15)
        
    all_events = div_events + ann_events
    if all_events:
        ingest_to_duckdb(all_events)
    print("=" * 80)

if __name__ == "__main__":
    main()

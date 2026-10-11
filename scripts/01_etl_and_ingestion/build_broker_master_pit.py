#!/usr/bin/env python3
"""
scripts/01_etl_and_ingestion/build_broker_master_pit.py

NEPSE Broker Ecosystem Slowly Changing Dimension (SCD Type 2) Generator
========================================================================
Implements Section 2 of the Quantitative Architecture Specification:
1. Permanent License String Alignment:
   - Assigns immutable numeric string IDs to stockbroker licenses (#1–59 legacy, #60–90+ expansion).
2. Model Safety:
   - Quantitative feature stores (HHI, Cont-Stoikov OFI, Hawkes point processes)
     execute strictly on raw numeric string keys ("58"), insulating mathematical
     models from corporate renames or rebranding.
3. Display Layer (PIT Lookup):
   - Terminal and reporting UI maps string IDs to corporate legal names via
     Slowly Changing Dimension (SCD Type 2) table `broker_master_pit` matching:
     ON broker_id AND trade_date BETWEEN effective_start_date AND effective_end_date.
"""

from __future__ import annotations

import json
import logging
import os
import sys
from datetime import date, datetime
from pathlib import Path
from typing import Dict, Any, List, Optional

import duckdb
import pandas as pd
import polars as pl

logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s")
logger = logging.getLogger("broker_master_pit")

BASE_DIR = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(BASE_DIR))

from scripts.db_connection import get_connection_manager, DuckDBConnectionManager

ANALYTICS_DB = BASE_DIR / "02_processed_parquet" / "market_analytics.duckdb"
OUT_PARQUET = BASE_DIR / "02_processed_parquet" / "broker_master_pit.parquet"
STATIC_PARQUET = BASE_DIR / "static_data" / "broker_master_pit.parquet"


# Comprehensive NEPSE Broker Corporate Lineage Database
# Includes:
# - Legacy Traditional Full-Brokers (#1 - #59)
# - Institutional Stock Dealer (#60)
# - 2023-2024 Market Expansion Tranche (#61 - #101+)
# - Historical corporate renames (SCD Type 2 version increments)

RAW_BROKER_MASTER: List[Dict[str, Any]] = [
    # -------------------------------------------------------------------------
    # TRADITIONAL LEGACY BROKERS (#1 - #59)
    # -------------------------------------------------------------------------
    {
        "broker_id": "1",
        "broker_code": "KUMARI",
        "legal_name": "Kumari Securities Pvt. Ltd.",
        "license_category": "TRADITIONAL_BROKER",
        "effective_start_date": "1994-01-01",
        "effective_end_date": "9999-12-31",
        "is_current": True,
        "version": 1,
        "corporate_notes": "Initial NEPSE tranche license #1. Continuous operation."
    },
    {
        "broker_id": "2",
        "broker_code": "ARUNODAYA",
        "legal_name": "Arunodaya Securities Pvt. Ltd.",
        "license_category": "TRADITIONAL_BROKER",
        "effective_start_date": "1994-01-01",
        "effective_end_date": "2015-07-15",
        "is_current": False,
        "version": 1,
        "corporate_notes": "Suspended/defunct historical broker license."
    },
    {
        "broker_id": "3",
        "broker_code": "ARUN",
        "legal_name": "Arun Securities (PVT) Ltd.",
        "license_category": "TRADITIONAL_BROKER",
        "effective_start_date": "1994-01-01",
        "effective_end_date": "9999-12-31",
        "is_current": True,
        "version": 1,
        "corporate_notes": "Initial NEPSE tranche license #3."
    },
    {
        "broker_id": "4",
        "broker_code": "OPAL",
        "legal_name": "Opal Securities Investment (PVT) Ltd.",
        "license_category": "TRADITIONAL_BROKER",
        "effective_start_date": "1994-01-01",
        "effective_end_date": "9999-12-31",
        "is_current": True,
        "version": 1,
        "corporate_notes": "Initial NEPSE tranche license #4."
    },
    {
        "broker_id": "5",
        "broker_code": "MARKET",
        "legal_name": "Market Securities & Exchange (PVT) Ltd.",
        "license_category": "TRADITIONAL_BROKER",
        "effective_start_date": "1994-01-01",
        "effective_end_date": "9999-12-31",
        "is_current": True,
        "version": 1,
        "corporate_notes": "Initial NEPSE tranche license #5."
    },
    {
        "broker_id": "6",
        "broker_code": "AGRAWAL",
        "legal_name": "Agrawal Securities (PVT) Ltd.",
        "license_category": "TRADITIONAL_BROKER",
        "effective_start_date": "1994-01-01",
        "effective_end_date": "9999-12-31",
        "is_current": True,
        "version": 1,
        "corporate_notes": "Initial NEPSE tranche license #6."
    },
    {
        "broker_id": "7",
        "broker_code": "JF",
        "legal_name": "J.F. Securites (PVT) Ltd.",
        "license_category": "TRADITIONAL_BROKER",
        "effective_start_date": "1994-01-01",
        "effective_end_date": "9999-12-31",
        "is_current": True,
        "version": 1,
        "corporate_notes": "Initial NEPSE tranche license #7."
    },
    {
        "broker_id": "8",
        "broker_code": "BRILLIANT",
        "legal_name": "Brilliant Securities Pvt. Ltd.",
        "license_category": "TRADITIONAL_BROKER",
        "effective_start_date": "1994-01-01",
        "effective_end_date": "9999-12-31",
        "is_current": True,
        "version": 1,
        "corporate_notes": "Initial NEPSE tranche license #8."
    },
    {
        "broker_id": "9",
        "broker_code": "MEYOR",
        "legal_name": "Meyor Securities Pvt. Ltd.",
        "license_category": "TRADITIONAL_BROKER",
        "effective_start_date": "1994-01-01",
        "effective_end_date": "2016-01-01",
        "is_current": False,
        "version": 1,
        "corporate_notes": "Inactive historical broker."
    },
    {
        "broker_id": "10",
        "broker_code": "PRAGYAN",
        "legal_name": "Pragyan Securities (PVT) Ltd.",
        "license_category": "TRADITIONAL_BROKER",
        "effective_start_date": "1994-01-01",
        "effective_end_date": "9999-12-31",
        "is_current": True,
        "version": 1,
        "corporate_notes": "Initial NEPSE tranche license #10."
    },
    {
        "broker_id": "11",
        "broker_code": "MALLA",
        "legal_name": "Malla & Malla Stock Broking Company Pvt. Limited",
        "license_category": "TRADITIONAL_BROKER",
        "effective_start_date": "1994-01-01",
        "effective_end_date": "9999-12-31",
        "is_current": True,
        "version": 1,
        "corporate_notes": "Initial NEPSE tranche license #11."
    },
    {
        "broker_id": "12",
        "broker_code": "PREMIER",
        "legal_name": "Premier Securities Pvt. Ltd.",
        "license_category": "TRADITIONAL_BROKER",
        "effective_start_date": "1994-01-01",
        "effective_end_date": "2018-01-01",
        "is_current": False,
        "version": 1,
        "corporate_notes": "Historical inactive broker."
    },
    {
        "broker_id": "13",
        "broker_code": "THRIVE",
        "legal_name": "Thrive Brokerage House Pvt. Ltd",
        "license_category": "TRADITIONAL_BROKER",
        "effective_start_date": "1994-01-01",
        "effective_end_date": "9999-12-31",
        "is_current": True,
        "version": 1,
        "corporate_notes": "Initial NEPSE tranche license #13."
    },
    {
        "broker_id": "14",
        "broker_code": "NEPALSTOCKHOUSE",
        "legal_name": "Nepal Stock House (PVT) Ltd.",
        "license_category": "TRADITIONAL_BROKER",
        "effective_start_date": "1994-01-01",
        "effective_end_date": "9999-12-31",
        "is_current": True,
        "version": 1,
        "corporate_notes": "Initial NEPSE tranche license #14."
    },
    {
        "broker_id": "15",
        "broker_code": "BHRIKUTI_OLD",
        "legal_name": "Bhrikuti Stock Broking Co.",
        "license_category": "TRADITIONAL_BROKER",
        "effective_start_date": "1994-01-01",
        "effective_end_date": "2012-01-01",
        "is_current": False,
        "version": 1,
        "corporate_notes": "Legacy historical broker."
    },
    {
        "broker_id": "16",
        "broker_code": "PRIMO",
        "legal_name": "Primo Securities (PVT) Ltd.",
        "license_category": "TRADITIONAL_BROKER",
        "effective_start_date": "1994-01-01",
        "effective_end_date": "9999-12-31",
        "is_current": True,
        "version": 1,
        "corporate_notes": "Initial NEPSE tranche license #16."
    },
    {
        "broker_id": "17",
        "broker_code": "ABC",
        "legal_name": "ABC Securities Private Limited",
        "license_category": "TRADITIONAL_BROKER",
        "effective_start_date": "1994-01-01",
        "effective_end_date": "9999-12-31",
        "is_current": True,
        "version": 1,
        "corporate_notes": "Initial NEPSE tranche license #17."
    },
    {
        "broker_id": "18",
        "broker_code": "SAGARMATHA",
        "legal_name": "Sagarmatha Securities Private Limited",
        "license_category": "TRADITIONAL_BROKER",
        "effective_start_date": "1994-01-01",
        "effective_end_date": "9999-12-31",
        "is_current": True,
        "version": 1,
        "corporate_notes": "Initial NEPSE tranche license #18."
    },
    {
        "broker_id": "19",
        "broker_code": "NIST",
        "legal_name": "Nepal Investment And Securities Trading Private Limited",
        "license_category": "TRADITIONAL_BROKER",
        "effective_start_date": "1994-01-01",
        "effective_end_date": "9999-12-31",
        "is_current": True,
        "version": 1,
        "corporate_notes": "Initial NEPSE tranche license #19."
    },
    {
        "broker_id": "20",
        "broker_code": "SIPLA",
        "legal_name": "Sipla Securities Private Limited",
        "license_category": "TRADITIONAL_BROKER",
        "effective_start_date": "1994-01-01",
        "effective_end_date": "9999-12-31",
        "is_current": True,
        "version": 1,
        "corporate_notes": "Initial NEPSE tranche license #20."
    },
    {
        "broker_id": "21",
        "broker_code": "MIDAS",
        "legal_name": "Midas Stock Broking Company Private Limited",
        "license_category": "TRADITIONAL_BROKER",
        "effective_start_date": "1994-01-01",
        "effective_end_date": "9999-12-31",
        "is_current": True,
        "version": 1,
        "corporate_notes": "Initial NEPSE tranche license #21."
    },
    {
        "broker_id": "22",
        "broker_code": "SIPRABI",
        "legal_name": "Siprabi Securities Pvt. Ltd.",
        "license_category": "TRADITIONAL_BROKER",
        "effective_start_date": "1994-01-01",
        "effective_end_date": "9999-12-31",
        "is_current": True,
        "version": 1,
        "corporate_notes": "Initial NEPSE tranche license #22."
    },
    {
        "broker_id": "25",
        "broker_code": "SWETA",
        "legal_name": "Sweta Securities Private Limited",
        "license_category": "TRADITIONAL_BROKER",
        "effective_start_date": "1994-01-01",
        "effective_end_date": "9999-12-31",
        "is_current": True,
        "version": 1,
        "corporate_notes": "Initial NEPSE tranche license #25."
    },
    {
        "broker_id": "26",
        "broker_code": "ASIAN",
        "legal_name": "Asian Securities Private Ltd.",
        "license_category": "TRADITIONAL_BROKER",
        "effective_start_date": "1994-01-01",
        "effective_end_date": "9999-12-31",
        "is_current": True,
        "version": 1,
        "corporate_notes": "Initial NEPSE tranche license #26."
    },
    {
        "broker_id": "28",
        "broker_code": "SHREEKRISHNA",
        "legal_name": "Shree Krishna Securities Limited",
        "license_category": "TRADITIONAL_BROKER",
        "effective_start_date": "1994-01-01",
        "effective_end_date": "9999-12-31",
        "is_current": True,
        "version": 1,
        "corporate_notes": "Initial NEPSE tranche license #28."
    },
    {
        "broker_id": "29",
        "broker_code": "TRISUL",
        "legal_name": "Trisul Securities & Investment Limited",
        "license_category": "TRADITIONAL_BROKER",
        "effective_start_date": "1994-01-01",
        "effective_end_date": "9999-12-31",
        "is_current": True,
        "version": 1,
        "corporate_notes": "Initial NEPSE tranche license #29."
    },
    {
        "broker_id": "32",
        "broker_code": "PREMIERSEC",
        "legal_name": "Premier Securities Company Limited",
        "license_category": "TRADITIONAL_BROKER",
        "effective_start_date": "1994-01-01",
        "effective_end_date": "9999-12-31",
        "is_current": True,
        "version": 1,
        "corporate_notes": "Initial NEPSE tranche license #32."
    },
    {
        "broker_id": "33",
        "broker_code": "DAKSHINKALI",
        "legal_name": "Dakshinkali Securities Limited",
        "license_category": "TRADITIONAL_BROKER",
        "effective_start_date": "1994-01-01",
        "effective_end_date": "9999-12-31",
        "is_current": True,
        "version": 1,
        "corporate_notes": "Initial NEPSE tranche license #33."
    },
    {
        "broker_id": "34",
        "broker_code": "VISION",
        "legal_name": "Vision Securities Pvt. Ltd",
        "license_category": "TRADITIONAL_BROKER",
        "effective_start_date": "1994-01-01",
        "effective_end_date": "9999-12-31",
        "is_current": True,
        "version": 1,
        "corporate_notes": "High-volume retail broker #34."
    },
    {
        "broker_id": "35",
        "broker_code": "KOHINOOR",
        "legal_name": "Kohinoor Investment & Securities Pvt. Ltd.",
        "license_category": "TRADITIONAL_BROKER",
        "effective_start_date": "1994-01-01",
        "effective_end_date": "9999-12-31",
        "is_current": True,
        "version": 1,
        "corporate_notes": "Initial NEPSE tranche license #35."
    },
    {
        "broker_id": "36",
        "broker_code": "SECURED",
        "legal_name": "Secured Securities Limited",
        "license_category": "TRADITIONAL_BROKER",
        "effective_start_date": "1994-01-01",
        "effective_end_date": "9999-12-31",
        "is_current": True,
        "version": 1,
        "corporate_notes": "Initial NEPSE tranche license #36."
    },
    {
        "broker_id": "37",
        "broker_code": "SWARNALAXMI",
        "legal_name": "Swarnalaxmi Securities Pvt. Ltd.",
        "license_category": "TRADITIONAL_BROKER",
        "effective_start_date": "1994-01-01",
        "effective_end_date": "9999-12-31",
        "is_current": True,
        "version": 1,
        "corporate_notes": "Initial NEPSE tranche license #37."
    },
    {
        "broker_id": "38",
        "broker_code": "DIPSHIKHA",
        "legal_name": "Dipshikha Dhitopatra Karobar Co. Pvt Ltd",
        "license_category": "TRADITIONAL_BROKER",
        "effective_start_date": "1994-01-01",
        "effective_end_date": "9999-12-31",
        "is_current": True,
        "version": 1,
        "corporate_notes": "Initial NEPSE tranche license #38."
    },
    {
        "broker_id": "39",
        "broker_code": "SUMERU",
        "legal_name": "Sumeru Securities Private Limited",
        "license_category": "TRADITIONAL_BROKER",
        "effective_start_date": "1994-01-01",
        "effective_end_date": "9999-12-31",
        "is_current": True,
        "version": 1,
        "corporate_notes": "Initial NEPSE tranche license #39."
    },
    {
        "broker_id": "40",
        "broker_code": "CREATIVE",
        "legal_name": "Creative Securities Private Limited",
        "license_category": "TRADITIONAL_BROKER",
        "effective_start_date": "1994-01-01",
        "effective_end_date": "9999-12-31",
        "is_current": True,
        "version": 1,
        "corporate_notes": "Initial NEPSE tranche license #40."
    },
    {
        "broker_id": "41",
        "broker_code": "LINCH",
        "legal_name": "Linch Stock Market Limited",
        "license_category": "TRADITIONAL_BROKER",
        "effective_start_date": "1994-01-01",
        "effective_end_date": "9999-12-31",
        "is_current": True,
        "version": 1,
        "corporate_notes": "Initial NEPSE tranche license #41."
    },
    {
        "broker_id": "42",
        "broker_code": "SANI",
        "legal_name": "Sani Securities Company Ltd.",
        "license_category": "TRADITIONAL_BROKER",
        "effective_start_date": "1994-01-01",
        "effective_end_date": "9999-12-31",
        "is_current": True,
        "version": 1,
        "corporate_notes": "High-volume retail broker #42."
    },
    {
        "broker_id": "43",
        "broker_code": "SOUTHASIAN",
        "legal_name": "South Asian Bulls Pvt. Ltd.",
        "license_category": "TRADITIONAL_BROKER",
        "effective_start_date": "1994-01-01",
        "effective_end_date": "9999-12-31",
        "is_current": True,
        "version": 1,
        "corporate_notes": "Initial NEPSE tranche license #43."
    },
    {
        "broker_id": "44",
        "broker_code": "DYNAMIC",
        "legal_name": "Dynamic Money Market Securities Pvt. Ltd.",
        "license_category": "TRADITIONAL_BROKER",
        "effective_start_date": "1994-01-01",
        "effective_end_date": "9999-12-31",
        "is_current": True,
        "version": 1,
        "corporate_notes": "Initial NEPSE tranche license #44."
    },
    {
        "broker_id": "45",
        "broker_code": "IMPERIAL",
        "legal_name": "Imperial Securities Company Pvt. Ltd.",
        "license_category": "TRADITIONAL_BROKER",
        "effective_start_date": "1994-01-01",
        "effective_end_date": "9999-12-31",
        "is_current": True,
        "version": 1,
        "corporate_notes": "Major institutional & retail broker #45."
    },
    {
        "broker_id": "46",
        "broker_code": "KALIKA",
        "legal_name": "Kalika Securities Pvt. Ltd.",
        "license_category": "TRADITIONAL_BROKER",
        "effective_start_date": "1994-01-01",
        "effective_end_date": "9999-12-31",
        "is_current": True,
        "version": 1,
        "corporate_notes": "Initial NEPSE tranche license #46."
    },
    {
        "broker_id": "47",
        "broker_code": "NIVEDITA",
        "legal_name": "Nivedita Securities Pvt. Ltd.",
        "license_category": "TRADITIONAL_BROKER",
        "effective_start_date": "1994-01-01",
        "effective_end_date": "9999-12-31",
        "is_current": True,
        "version": 1,
        "corporate_notes": "Initial NEPSE tranche license #47."
    },
    {
        "broker_id": "48",
        "broker_code": "TRISHAKTI",
        "legal_name": "Trishakti Securities Public Limited",
        "license_category": "TRADITIONAL_BROKER",
        "effective_start_date": "1994-01-01",
        "effective_end_date": "9999-12-31",
        "is_current": True,
        "version": 1,
        "corporate_notes": "Initial NEPSE tranche license #48."
    },
    {
        "broker_id": "49",
        "broker_code": "ONLINE",
        "legal_name": "Online Securities Ltd.",
        "license_category": "TRADITIONAL_BROKER",
        "effective_start_date": "1994-01-01",
        "effective_end_date": "9999-12-31",
        "is_current": True,
        "version": 1,
        "corporate_notes": "Major institutional broker #49."
    },
    {
        "broker_id": "50",
        "broker_code": "CRYSTAL",
        "legal_name": "Crystal Kanchenjunga Securities Pvt. Ltd.",
        "license_category": "TRADITIONAL_BROKER",
        "effective_start_date": "1994-01-01",
        "effective_end_date": "9999-12-31",
        "is_current": True,
        "version": 1,
        "corporate_notes": "Initial NEPSE tranche license #50."
    },
    {
        "broker_id": "51",
        "broker_code": "OXFORD",
        "legal_name": "Oxford Securities Pvt. Ltd.",
        "license_category": "TRADITIONAL_BROKER",
        "effective_start_date": "1994-01-01",
        "effective_end_date": "9999-12-31",
        "is_current": True,
        "version": 1,
        "corporate_notes": "Initial NEPSE tranche license #51."
    },
    {
        "broker_id": "52",
        "broker_code": "SUNDHARA",
        "legal_name": "Sundhara Securities Limited",
        "license_category": "TRADITIONAL_BROKER",
        "effective_start_date": "1994-01-01",
        "effective_end_date": "9999-12-31",
        "is_current": True,
        "version": 1,
        "corporate_notes": "Initial NEPSE tranche license #52."
    },
    {
        "broker_id": "53",
        "broker_code": "INVESTMENT_MGMT",
        "legal_name": "Investment Management Nepal Pvt. Ltd.",
        "license_category": "TRADITIONAL_BROKER",
        "effective_start_date": "1994-01-01",
        "effective_end_date": "9999-12-31",
        "is_current": True,
        "version": 1,
        "corporate_notes": "Initial NEPSE tranche license #53."
    },
    {
        "broker_id": "54",
        "broker_code": "SEWA",
        "legal_name": "Sewa Securities Pvt. Ltd.",
        "license_category": "TRADITIONAL_BROKER",
        "effective_start_date": "1994-01-01",
        "effective_end_date": "9999-12-31",
        "is_current": True,
        "version": 1,
        "corporate_notes": "Initial NEPSE tranche license #54."
    },
    {
        "broker_id": "56",
        "broker_code": "SRI_HARI",
        "legal_name": "Sri Hari Securities Pvt. Ltd.",
        "license_category": "TRADITIONAL_BROKER",
        "effective_start_date": "1994-01-01",
        "effective_end_date": "9999-12-31",
        "is_current": True,
        "version": 1,
        "corporate_notes": "Initial NEPSE tranche license #56."
    },
    {
        "broker_id": "57",
        "broker_code": "ARYATARA",
        "legal_name": "Aryatara Investment & Securities",
        "license_category": "TRADITIONAL_BROKER",
        "effective_start_date": "1994-01-01",
        "effective_end_date": "9999-12-31",
        "is_current": True,
        "version": 1,
        "corporate_notes": "Major market broker #57."
    },

    # --- SCD TYPE 2 EXAMPLE: BROKER 58 (NAASA SECURITIES) HISTORICAL RENAME ---
    {
        "broker_id": "58",
        "broker_code": "NAASA",
        "legal_name": "Naasa Securities Pvt. Ltd.",
        "license_category": "TRADITIONAL_BROKER",
        "effective_start_date": "1994-01-01",
        "effective_end_date": "2023-07-15",
        "is_current": False,
        "version": 1,
        "corporate_notes": "Historical legal structure as Private Limited."
    },
    {
        "broker_id": "58",
        "broker_code": "NAASA",
        "legal_name": "Naasa Securities Co. Ltd.",
        "license_category": "TRADITIONAL_BROKER",
        "effective_start_date": "2023-07-16",
        "effective_end_date": "9999-12-31",
        "is_current": True,
        "version": 2,
        "corporate_notes": "Converted to Public Limited under SEBON market modernization rules."
    },

    {
        "broker_id": "59",
        "broker_code": "DEEVYAA",
        "legal_name": "Deevyaa Securities & Stock Broker Pvt. Ltd.",
        "license_category": "TRADITIONAL_BROKER",
        "effective_start_date": "1994-01-01",
        "effective_end_date": "9999-12-31",
        "is_current": True,
        "version": 1,
        "corporate_notes": "Initial NEPSE tranche license #59."
    },

    # -------------------------------------------------------------------------
    # INSTITUTIONAL STOCK DEALER (#60)
    # -------------------------------------------------------------------------
    {
        "broker_id": "60",
        "broker_code": "NAGARIK",
        "legal_name": "Nagarik Stock Dealer",
        "license_category": "STOCK_DEALER",
        "effective_start_date": "2021-02-01",
        "effective_end_date": "9999-12-31",
        "is_current": True,
        "version": 1,
        "corporate_notes": "Nepal's premier institutional stock dealer established under Citizen Investment Trust."
    },

    # -------------------------------------------------------------------------
    # 2023-2024 MARKET EXPANSION TRANCHE (#61 - #101+)
    # -------------------------------------------------------------------------
    {
        "broker_id": "61",
        "broker_code": "BHOLANATH",
        "legal_name": "Bholanath Securities Limited",
        "license_category": "EXPANSION_BROKER",
        "effective_start_date": "2023-05-22",
        "effective_end_date": "9999-12-31",
        "is_current": True,
        "version": 1,
        "corporate_notes": "2023 SEBON market expansion tranche license #61."
    },
    {
        "broker_id": "62",
        "broker_code": "CAPITAL_HUB",
        "legal_name": "Capital Hub Pvt. Ltd.",
        "license_category": "EXPANSION_BROKER",
        "effective_start_date": "2023-05-22",
        "effective_end_date": "9999-12-31",
        "is_current": True,
        "version": 1,
        "corporate_notes": "2023 SEBON expansion license #62."
    },
    {
        "broker_id": "63",
        "broker_code": "AKASHDEEP",
        "legal_name": "Aakashbari Securities Limited",
        "license_category": "EXPANSION_BROKER",
        "effective_start_date": "2023-05-22",
        "effective_end_date": "9999-12-31",
        "is_current": True,
        "version": 1,
        "corporate_notes": "2023 SEBON expansion license #63."
    },
    {
        "broker_id": "64",
        "broker_code": "SANIMA",
        "legal_name": "Sanima Securities Limited",
        "license_category": "EXPANSION_BROKER",
        "effective_start_date": "2023-05-22",
        "effective_end_date": "9999-12-31",
        "is_current": True,
        "version": 1,
        "corporate_notes": "Commercial bank subsidiary (Sanima Bank) license #64."
    },
    {
        "broker_id": "65",
        "broker_code": "ELITE_STOCK",
        "legal_name": "Elite Stock Deal Limited",
        "license_category": "EXPANSION_BROKER",
        "effective_start_date": "2023-05-22",
        "effective_end_date": "9999-12-31",
        "is_current": True,
        "version": 1,
        "corporate_notes": "2023 SEBON expansion license #65."
    },
    {
        "broker_id": "66",
        "broker_code": "INDEX",
        "legal_name": "Index Securities Limited",
        "license_category": "EXPANSION_BROKER",
        "effective_start_date": "2023-05-22",
        "effective_end_date": "9999-12-31",
        "is_current": True,
        "version": 1,
        "corporate_notes": "2023 SEBON expansion license #66."
    },
    {
        "broker_id": "67",
        "broker_code": "INFINITY",
        "legal_name": "Infinity Securities Limited",
        "license_category": "EXPANSION_BROKER",
        "effective_start_date": "2023-05-22",
        "effective_end_date": "9999-12-31",
        "is_current": True,
        "version": 1,
        "corporate_notes": "2023 SEBON expansion license #67."
    },
    {
        "broker_id": "68",
        "broker_code": "SHUBHAKAMANA",
        "legal_name": "Shubhakamana Securities Limited",
        "license_category": "EXPANSION_BROKER",
        "effective_start_date": "2023-05-22",
        "effective_end_date": "9999-12-31",
        "is_current": True,
        "version": 1,
        "corporate_notes": "2023 SEBON expansion license #68."
    },
    {
        "broker_id": "69",
        "broker_code": "SAJILO",
        "legal_name": "Sajilo Broker Limited",
        "license_category": "EXPANSION_BROKER",
        "effective_start_date": "2023-05-22",
        "effective_end_date": "9999-12-31",
        "is_current": True,
        "version": 1,
        "corporate_notes": "2023 SEBON expansion license #69."
    },
    {
        "broker_id": "70",
        "broker_code": "SKYLINE",
        "legal_name": "Skyline Securities Limited",
        "license_category": "EXPANSION_BROKER",
        "effective_start_date": "2023-05-22",
        "effective_end_date": "9999-12-31",
        "is_current": True,
        "version": 1,
        "corporate_notes": "2023 SEBON expansion license #70."
    },
    {
        "broker_id": "71",
        "broker_code": "KBL_OLD",
        "legal_name": "Kumari Capital Brokerage",
        "license_category": "EXPANSION_BROKER",
        "effective_start_date": "2023-05-22",
        "effective_end_date": "9999-12-31",
        "is_current": True,
        "version": 1,
        "corporate_notes": "2023 SEBON expansion license #71."
    },
    {
        "broker_id": "72",
        "broker_code": "GARIMA",
        "legal_name": "Garima Securities Limited",
        "license_category": "EXPANSION_BROKER",
        "effective_start_date": "2023-05-22",
        "effective_end_date": "9999-12-31",
        "is_current": True,
        "version": 1,
        "corporate_notes": "Development bank subsidiary (Garima Bikas Bank) license #72."
    },
    {
        "broker_id": "74",
        "broker_code": "PRABHU_OLD",
        "legal_name": "Prabhu Securities Limited",
        "license_category": "EXPANSION_BROKER",
        "effective_start_date": "2023-05-22",
        "effective_end_date": "9999-12-31",
        "is_current": True,
        "version": 1,
        "corporate_notes": "Commercial bank subsidiary (Prabhu Bank) license #74."
    },
    {
        "broker_id": "75",
        "broker_code": "NMB",
        "legal_name": "NMB Securities Limited",
        "license_category": "EXPANSION_BROKER",
        "effective_start_date": "2023-05-22",
        "effective_end_date": "9999-12-31",
        "is_current": True,
        "version": 1,
        "corporate_notes": "Commercial bank subsidiary (NMB Bank) license #75."
    },
    {
        "broker_id": "76",
        "broker_code": "MEGA",
        "legal_name": "Mega Stock Markets Limited",
        "license_category": "EXPANSION_BROKER",
        "effective_start_date": "2023-05-22",
        "effective_end_date": "9999-12-31",
        "is_current": True,
        "version": 1,
        "corporate_notes": "2023 SEBON expansion license #76."
    },
    {
        "broker_id": "77",
        "broker_code": "NABIL_STOCK",
        "legal_name": "Nabil Stock Dealer Limited",
        "license_category": "STOCK_DEALER",
        "effective_start_date": "2023-05-22",
        "effective_end_date": "9999-12-31",
        "is_current": True,
        "version": 1,
        "corporate_notes": "Institutional stock dealer subsidiary of Nabil Bank."
    },
    {
        "broker_id": "78",
        "broker_code": "MACHHAPUCHCHHRE",
        "legal_name": "Machhapuchchhre Securities Limited",
        "license_category": "EXPANSION_BROKER",
        "effective_start_date": "2023-08-15",
        "effective_end_date": "9999-12-31",
        "is_current": True,
        "version": 1,
        "corporate_notes": "Commercial bank subsidiary (MBL) license #78."
    },
    {
        "broker_id": "79",
        "broker_code": "NIC_ASIA",
        "legal_name": "NIC Asia Securities Limited",
        "license_category": "EXPANSION_BROKER",
        "effective_start_date": "2023-08-15",
        "effective_end_date": "9999-12-31",
        "is_current": True,
        "version": 1,
        "corporate_notes": "Commercial bank subsidiary (NIC Asia Bank) license #79."
    },
    {
        "broker_id": "80",
        "broker_code": "GLOBAL_IME",
        "legal_name": "Global IME Securities Limited",
        "license_category": "EXPANSION_BROKER",
        "effective_start_date": "2023-08-15",
        "effective_end_date": "9999-12-31",
        "is_current": True,
        "version": 1,
        "corporate_notes": "Commercial bank subsidiary (Global IME Bank) license #80."
    },
    {
        "broker_id": "81",
        "broker_code": "SHINE",
        "legal_name": "Shine Resunga Securities Limited",
        "license_category": "EXPANSION_BROKER",
        "effective_start_date": "2023-08-15",
        "effective_end_date": "9999-12-31",
        "is_current": True,
        "version": 1,
        "corporate_notes": "Regional development bank subsidiary license #81."
    },
    {
        "broker_id": "82",
        "broker_code": "JYOTI",
        "legal_name": "Jyoti Capital & Securities",
        "license_category": "EXPANSION_BROKER",
        "effective_start_date": "2023-08-15",
        "effective_end_date": "9999-12-31",
        "is_current": True,
        "version": 1,
        "corporate_notes": "Development bank subsidiary license #82."
    },
    {
        "broker_id": "83",
        "broker_code": "MUKTINATH",
        "legal_name": "Muktinath Securities Limited",
        "license_category": "EXPANSION_BROKER",
        "effective_start_date": "2023-08-15",
        "effective_end_date": "9999-12-31",
        "is_current": True,
        "version": 1,
        "corporate_notes": "Development bank subsidiary license #83."
    },
    {
        "broker_id": "84",
        "broker_code": "CITIZENS",
        "legal_name": "CBIL Securities Limited",
        "license_category": "EXPANSION_BROKER",
        "effective_start_date": "2023-08-15",
        "effective_end_date": "9999-12-31",
        "is_current": True,
        "version": 1,
        "corporate_notes": "Commercial bank subsidiary (Citizens Bank) license #84."
    },
    {
        "broker_id": "85",
        "broker_code": "PRIME",
        "legal_name": "Prime Securities Limited",
        "license_category": "EXPANSION_BROKER",
        "effective_start_date": "2023-08-15",
        "effective_end_date": "9999-12-31",
        "is_current": True,
        "version": 1,
        "corporate_notes": "Commercial bank subsidiary (Prime Commercial Bank) license #85."
    },
    {
        "broker_id": "86",
        "broker_code": "SUNRISE_CAP",
        "legal_name": "Sunrise Capital Brokerage",
        "license_category": "EXPANSION_BROKER",
        "effective_start_date": "2023-08-15",
        "effective_end_date": "9999-12-31",
        "is_current": True,
        "version": 1,
        "corporate_notes": "Commercial bank subsidiary license #86."
    },
    {
        "broker_id": "87",
        "broker_code": "SIDDHARTHA",
        "legal_name": "Siddhartha Capital Securities",
        "license_category": "EXPANSION_BROKER",
        "effective_start_date": "2023-08-15",
        "effective_end_date": "9999-12-31",
        "is_current": True,
        "version": 1,
        "corporate_notes": "Commercial bank subsidiary (SBL) license #87."
    },
    {
        "broker_id": "88",
        "broker_code": "STANDARD_CHARTERED",
        "legal_name": "SCB Custody & Broking Services",
        "license_category": "EXPANSION_BROKER",
        "effective_start_date": "2023-08-15",
        "effective_end_date": "9999-12-31",
        "is_current": True,
        "version": 1,
        "corporate_notes": "Foreign joint-venture subsidiary license #88."
    },
    {
        "broker_id": "89",
        "broker_code": "EVEREST",
        "legal_name": "Everest Securities Limited",
        "license_category": "EXPANSION_BROKER",
        "effective_start_date": "2023-08-15",
        "effective_end_date": "9999-12-31",
        "is_current": True,
        "version": 1,
        "corporate_notes": "Commercial bank subsidiary (EBL) license #89."
    },
    {
        "broker_id": "90",
        "broker_code": "NEPAL_SBI",
        "legal_name": "Nepal SBI Securities Limited",
        "license_category": "EXPANSION_BROKER",
        "effective_start_date": "2023-08-15",
        "effective_end_date": "9999-12-31",
        "is_current": True,
        "version": 1,
        "corporate_notes": "Commercial bank subsidiary (SBI) license #90."
    },
    {
        "broker_id": "91",
        "broker_code": "LAXMI_SUNRISE",
        "legal_name": "Laxmi Sunrise Securities Limited",
        "license_category": "EXPANSION_BROKER",
        "effective_start_date": "2023-08-15",
        "effective_end_date": "9999-12-31",
        "is_current": True,
        "version": 1,
        "corporate_notes": "Commercial bank subsidiary license #91."
    },
    {
        "broker_id": "92",
        "broker_code": "ROADSHOW",
        "legal_name": "Roadshow securities limited",
        "license_category": "EXPANSION_BROKER",
        "effective_start_date": "2023-08-15",
        "effective_end_date": "9999-12-31",
        "is_current": True,
        "version": 1,
        "corporate_notes": "2023 expansion license #92."
    },
    {
        "broker_id": "93",
        "broker_code": "BENI",
        "legal_name": "Beni Securities Pvt.Ltd.",
        "license_category": "EXPANSION_BROKER",
        "effective_start_date": "2023-08-15",
        "effective_end_date": "9999-12-31",
        "is_current": True,
        "version": 1,
        "corporate_notes": "2023 expansion license #93."
    },
    {
        "broker_id": "94",
        "broker_code": "KBL",
        "legal_name": "K.B.L. Securities Limited",
        "license_category": "EXPANSION_BROKER",
        "effective_start_date": "2023-08-15",
        "effective_end_date": "9999-12-31",
        "is_current": True,
        "version": 1,
        "corporate_notes": "Commercial bank subsidiary (Kumari Bank) license #94."
    },
    {
        "broker_id": "95",
        "broker_code": "MAGNET",
        "legal_name": "Magnet Securities and Investment Company Private Limited",
        "license_category": "EXPANSION_BROKER",
        "effective_start_date": "2023-08-15",
        "effective_end_date": "9999-12-31",
        "is_current": True,
        "version": 1,
        "corporate_notes": "2023 expansion license #95."
    },
    {
        "broker_id": "96",
        "broker_code": "HIMALAYAN",
        "legal_name": "Himalayan Securities Limited",
        "license_category": "EXPANSION_BROKER",
        "effective_start_date": "2023-08-15",
        "effective_end_date": "9999-12-31",
        "is_current": True,
        "version": 1,
        "corporate_notes": "Commercial bank subsidiary (Himalayan Bank) license #96."
    },
    {
        "broker_id": "97",
        "broker_code": "RBB",
        "legal_name": "R.B.B. Securities Company Ltd",
        "license_category": "EXPANSION_BROKER",
        "effective_start_date": "2023-08-15",
        "effective_end_date": "9999-12-31",
        "is_current": True,
        "version": 1,
        "corporate_notes": "State-owned commercial bank subsidiary (Rastriya Banijya Bank) license #97."
    },
    {
        "broker_id": "98",
        "broker_code": "TRADEMOW",
        "legal_name": "Trademow Securities Private Limited",
        "license_category": "EXPANSION_BROKER",
        "effective_start_date": "2023-08-15",
        "effective_end_date": "9999-12-31",
        "is_current": True,
        "version": 1,
        "corporate_notes": "2023 expansion license #98."
    },
    {
        "broker_id": "99",
        "broker_code": "PRABHU_STOCK",
        "legal_name": "Prabhu Stock Market Limited",
        "license_category": "EXPANSION_BROKER",
        "effective_start_date": "2023-08-15",
        "effective_end_date": "9999-12-31",
        "is_current": True,
        "version": 1,
        "corporate_notes": "2023 expansion license #99."
    },
    {
        "broker_id": "100",
        "broker_code": "SUNRISE_SEC",
        "legal_name": "Sunrise Securities Limited",
        "license_category": "EXPANSION_BROKER",
        "effective_start_date": "2023-08-15",
        "effective_end_date": "9999-12-31",
        "is_current": True,
        "version": 1,
        "corporate_notes": "2023 expansion license #100."
    },
    {
        "broker_id": "101",
        "broker_code": "APPLE",
        "legal_name": "APPLE SECURITIES PRIVATE LIMITED",
        "license_category": "EXPANSION_BROKER",
        "effective_start_date": "2023-08-15",
        "effective_end_date": "9999-12-31",
        "is_current": True,
        "version": 1,
        "corporate_notes": "2023 expansion license #101."
    }
]


def build_broker_master_pit() -> pl.DataFrame:
    """
    Constructs, validates, and persists the Point-in-Time (PIT) SCD Type 2 broker table.
    """
    print("=" * 80)
    print("  NEPSE BROKER ECOSYSTEM: POINT-IN-TIME (PIT) SCD TYPE 2 GENERATOR")
    print("=" * 80)

    # 1. Convert to Polars DataFrame with strict schema
    df = pl.DataFrame(RAW_BROKER_MASTER).with_columns([
        pl.col("broker_id").cast(pl.Utf8),
        pl.col("broker_code").cast(pl.Utf8),
        pl.col("legal_name").cast(pl.Utf8),
        pl.col("license_category").cast(pl.Utf8),
        pl.col("effective_start_date").str.to_date("%Y-%m-%d"),
        pl.col("effective_end_date").str.to_date("%Y-%m-%d"),
        pl.col("is_current").cast(pl.Boolean),
        pl.col("version").cast(pl.Int32),
        pl.col("corporate_notes").cast(pl.Utf8),
    ]).sort(["broker_id", "version"])

    total_records = len(df)
    unique_brokers = df["broker_id"].n_unique()
    active_brokers = df.filter(pl.col("is_current")).height

    print(f"  * Total SCD Type 2 Records: {total_records}")
    print(f"  * Unique Broker License IDs: {unique_brokers}")
    print(f"  * Currently Active Brokers: {active_brokers}")

    # 2. Persist to Parquet targets atomically
    OUT_PARQUET.parent.mkdir(parents=True, exist_ok=True)
    STATIC_PARQUET.parent.mkdir(parents=True, exist_ok=True)

    df.write_parquet(OUT_PARQUET)
    df.write_parquet(STATIC_PARQUET)
    print(f"  [+] Persisted Parquet -> {OUT_PARQUET.name} & static_data/{STATIC_PARQUET.name}")

    # 3. Synchronize with DuckDB Lakehouse using Thread-Safe Connection Pool
    db_manager = get_connection_manager(str(ANALYTICS_DB))
    with db_manager.acquire() as con:
        # Create physical table
        con.execute(f"""
            CREATE OR REPLACE TABLE broker_master_pit AS 
            SELECT * FROM read_parquet('{str(OUT_PARQUET).replace('\\', '/')}')
        """)
        
        # Verify table row count
        count = con.execute("SELECT COUNT(*) FROM broker_master_pit").fetchone()[0]
        print(f"  [+] Registered physical table `broker_master_pit` in DuckDB ({count} rows).")

        # Create zero-copy enriched view joining lakehouse_ticks with PIT broker master
        con.execute("""
            CREATE OR REPLACE VIEW lakehouse_ticks_with_broker_pit AS
            SELECT 
                t.*,
                b_buy.legal_name as buyer_broker_name,
                b_buy.broker_code as buyer_broker_code,
                b_buy.license_category as buyer_license_category,
                b_sell.legal_name as seller_broker_name,
                b_sell.broker_code as seller_broker_code,
                b_sell.license_category as seller_license_category
            FROM lakehouse_ticks t
            LEFT JOIN broker_master_pit b_buy
              ON t.buyer_broker = b_buy.broker_id
             AND TRY_CAST(t.trade_date AS DATE) BETWEEN b_buy.effective_start_date AND b_buy.effective_end_date
            LEFT JOIN broker_master_pit b_sell
              ON t.seller_broker = b_sell.broker_id
             AND TRY_CAST(t.trade_date AS DATE) BETWEEN b_sell.effective_start_date AND b_sell.effective_end_date
        """)
        print("  [+] Created zero-copy Point-In-Time view `lakehouse_ticks_with_broker_pit`.")

    print("=" * 80 + "\n")
    return df


def get_broker_pit(broker_id: str, as_of_date: str = "2026-10-11") -> Optional[Dict[str, Any]]:
    """
    Point-in-Time lookup helper for terminal, order staging, and reporting layer.
    """
    db_manager = get_connection_manager(str(ANALYTICS_DB))
    query = """
        SELECT 
            broker_id, broker_code, legal_name, license_category,
            effective_start_date, effective_end_date, is_current, version
        FROM broker_master_pit
        WHERE broker_id = ?
          AND ? BETWEEN effective_start_date AND effective_end_date
        LIMIT 1
    """
    with db_manager.acquire() as con:
        res = con.execute(query, [str(broker_id), as_of_date]).fetchall()
        if not res:
            return None
        row = res[0]
        return {
            "broker_id": row[0],
            "broker_code": row[1],
            "legal_name": row[2],
            "license_category": row[3],
            "effective_start_date": str(row[4]),
            "effective_end_date": str(row[5]),
            "is_current": row[6],
            "version": row[7]
        }


def main():
    df = build_broker_master_pit()

    # Demonstration of SCD Type 2 Point-in-Time Resolution for Broker 58 (Naasa)
    print("Demonstrating SCD Type 2 Resolution for Broker 58:")
    print("  Historical 2018 Trade ->", get_broker_pit("58", "2018-05-10"))
    print("  Modern 2026 Trade     ->", get_broker_pit("58", "2026-10-07"))

    print("\nDemonstrating Lookahead Bias Prevention for Expansion Broker 94 (KBL):")
    print("  Historical 2018 Trade ->", get_broker_pit("94", "2018-05-10"))  # Must return None (Didn't exist)
    print("  Modern 2026 Trade     ->", get_broker_pit("94", "2026-10-07"))  # Returns active KBL


if __name__ == "__main__":
    main()

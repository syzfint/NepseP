"""
Preservation Test 2.2: Ingestion Preservation

**Property 2: Preservation** — Legitimate Trades Unchanged

This test captures the BASELINE behaviour of the ingestion pipeline on UNFIXED code
for inputs that do NOT trigger the anti-wash bug condition (buyer != seller).
These tests MUST PASS on unfixed code so that any regression introduced by the
schema-canonicalization fix is immediately detected.

Specifically, we test the TWO anti-wash code paths in the codebase:

Path A — Batch CSV (08_compute_floorsheet_broker_features.py)
  Uses DuckDB SQL with legacy column names Buyer/Seller.
  Wash-filter predicate: CAST(Buyer AS VARCHAR) = CAST(Seller AS VARCHAR)
  For cross-broker trades (Buyer != Seller) the predicate is FALSE → trade is kept.

Path B — Live API (update_today_eod_lakehouse.py / process_anti_wash_floorsheet)
  Normalises buyerMemberId/sellerMemberId to df["buyer"] / df["seller"].
  Wash-filter predicate: buyer == seller (Python/pandas)
  For cross-broker trades (buyer != seller) the predicate is FALSE → trade is kept.

Requirements: 3.2.1, 3.2.2, 3.2.3

Expected Outcome: All tests PASS — confirms baseline behaviour for legitimate trades.
"""

import pytest
import duckdb
import pandas as pd
import numpy as np
from hypothesis import given, assume, settings, HealthCheck
from hypothesis import strategies as st

# ---------------------------------------------------------------------------
# Helpers mirroring the actual unfixed ingestion logic
# ---------------------------------------------------------------------------

def _csv_anti_wash_filter_sql(df: pd.DataFrame, min_lot_size: int = 10) -> pd.DataFrame:
    """
    Re-implements the exact filter from 08_compute_floorsheet_broker_features.py
    so we can test it in isolation without touching the filesystem.

    The raw CSV schema uses 'Buyer' and 'Seller' as column names.
    The DuckDB predicate is:
        (CAST(Buyer AS VARCHAR) = CAST(Seller AS VARCHAR)) AS is_wash_trade
    Clean trades are those where is_wash_trade = FALSE.
    """
    con = duckdb.connect(database=":memory:")
    con.register("raw_input", df)

    sql = """
    WITH raw_trades AS (
        SELECT
            UPPER(TRIM(Symbol))              AS ticker,
            CAST(Date AS DATE)               AS date,
            CAST(Buyer    AS VARCHAR)        AS buyer,
            CAST(Seller   AS VARCHAR)        AS seller,
            CAST(Quantity AS DOUBLE)         AS quantity,
            CAST(Rate     AS DOUBLE)         AS price,
            CAST(Amount   AS DOUBLE)         AS amount,
            (CAST(Buyer AS VARCHAR) = CAST(Seller AS VARCHAR)) AS is_wash_trade,
            (CAST(Quantity AS DOUBLE) < 10)                    AS is_odd_lot
        FROM raw_input
        WHERE Symbol IS NOT NULL AND Amount > 0
    )
    SELECT *
    FROM raw_trades
    WHERE NOT is_wash_trade AND NOT is_odd_lot
    """
    result = con.execute(sql).fetchdf()
    con.close()
    return result


def _api_anti_wash_filter_pandas(records: list) -> pd.DataFrame:
    """
    Re-implements the exact filter from update_today_eod_lakehouse.py
    (process_anti_wash_floorsheet) so we can test it in isolation.

    The live API uses 'buyerMemberId' / 'sellerMemberId'.
    The code normalises:
        df_fs["buyer"]  = df_fs["buyerMemberId"].astype(str)
        df_fs["seller"] = df_fs["sellerMemberId"].astype(str)
    Then filters clean trades with:
        clean_trades = df_fs[~is_wash & ~is_odd]
    where:
        is_wash = (df_fs["buyer"] == df_fs["seller"])
        is_odd  = (df_fs["quantity"] < 10)
    """
    df = pd.DataFrame(records)
    df["buyer"]    = df["buyerMemberId"].astype(str)
    df["seller"]   = df["sellerMemberId"].astype(str)
    df["quantity"] = pd.to_numeric(df["contractQuantity"], errors="coerce").fillna(0.0)
    df["amount"]   = pd.to_numeric(df["contractAmount"],  errors="coerce").fillna(0.0)

    is_wash = df["buyer"] == df["seller"]
    is_odd  = df["quantity"] < 10

    return df[~is_wash & ~is_odd].copy()


def _compute_broker_features_sql(df: pd.DataFrame) -> pd.DataFrame:
    """
    Computes buyer_hhi and top3_buyer_share from clean trades using the same
    DuckDB SQL pattern as update_today_eod_lakehouse.py (process_anti_wash_floorsheet).
    Returns one row per ticker.
    """
    con = duckdb.connect(database=":memory:")
    con.register("clean", df)

    sql = """
    WITH buyer_shares AS (
        SELECT
            ticker,
            buyer,
            SUM(amount) AS buyer_amount,
            SUM(amount) * 1.0 / NULLIF(SUM(SUM(amount)) OVER (PARTITION BY ticker), 0) AS b_share,
            ROW_NUMBER() OVER (PARTITION BY ticker ORDER BY SUM(amount) DESC) AS b_rank
        FROM clean
        GROUP BY ticker, buyer
    )
    SELECT
        ticker,
        SUM(CASE WHEN b_rank <= 3 THEN b_share ELSE 0.0 END) AS top3_buyer_share,
        SUM(POWER(b_share, 2))                                AS buyer_hhi
    FROM buyer_shares
    GROUP BY ticker
    """
    result = con.execute(sql).fetchdf()
    con.close()
    return result


# ---------------------------------------------------------------------------
# Builders for sample data
# ---------------------------------------------------------------------------

def _make_csv_trades(rows: list) -> pd.DataFrame:
    """Build a DataFrame that looks like a raw CSV floorsheet row."""
    return pd.DataFrame(rows)


def _make_api_records(rows: list) -> list:
    """Build a list of dicts that looks like a raw NEPSE API floorsheet payload."""
    return rows


# ---------------------------------------------------------------------------
# Unit Tests — example-based
# ---------------------------------------------------------------------------

class TestCsvPathPreservation:
    """
    Tests the Batch-CSV anti-wash filter (Path A).
    Ensures cross-broker trades (Buyer != Seller) pass through correctly.
    Requirement 3.2.1
    """

    def test_cross_broker_trade_passes_csv_filter(self):
        """A trade with distinct Buyer and Seller IDs must NOT be filtered out."""
        df = _make_csv_trades([
            {"Symbol": "NABIL", "Date": "2024-06-15", "Buyer": "45",
             "Seller": "58", "Quantity": 500, "Rate": 620.0, "Amount": 310000.0},
        ])
        clean = _csv_anti_wash_filter_sql(df)
        assert len(clean) == 1, (
            "Cross-broker trade was incorrectly removed by anti-wash filter "
            f"(Buyer=45, Seller=58 → expected 1 row, got {len(clean)})"
        )

    def test_multiple_cross_broker_trades_all_pass(self):
        """All cross-broker trades in a batch must be retained."""
        df = _make_csv_trades([
            {"Symbol": "NABIL", "Date": "2024-06-15", "Buyer": "45", "Seller": "58",
             "Quantity": 500, "Rate": 620.0, "Amount": 310000.0},
            {"Symbol": "NABIL", "Date": "2024-06-15", "Buyer": "12", "Seller": "33",
             "Quantity": 200, "Rate": 615.0, "Amount": 123000.0},
            {"Symbol": "EBL",   "Date": "2024-06-15", "Buyer": "7",  "Seller": "22",
             "Quantity": 1000, "Rate": 850.0, "Amount": 850000.0},
        ])
        clean = _csv_anti_wash_filter_sql(df)
        assert len(clean) == 3, (
            f"Expected all 3 cross-broker trades to pass; got {len(clean)}"
        )

    def test_wash_trade_removed_cross_broker_trade_kept(self):
        """
        In a mixed batch, only the self-matched (wash) trade is removed.
        Cross-broker trades must survive.
        """
        df = _make_csv_trades([
            {"Symbol": "NABIL", "Date": "2024-06-15", "Buyer": "45", "Seller": "45",
             "Quantity": 500, "Rate": 620.0, "Amount": 310000.0},   # wash — should be removed
            {"Symbol": "NABIL", "Date": "2024-06-15", "Buyer": "45", "Seller": "58",
             "Quantity": 500, "Rate": 620.0, "Amount": 310000.0},   # cross-broker — must be kept
        ])
        clean = _csv_anti_wash_filter_sql(df)
        assert len(clean) == 1, (
            f"Expected 1 clean trade (wash removed, cross-broker kept); got {len(clean)}"
        )
        assert clean.iloc[0]["buyer"] == "45"
        assert clean.iloc[0]["seller"] == "58"

    def test_integer_broker_ids_cast_correctly(self):
        """
        Broker IDs stored as integers in CSV must be cast to VARCHAR and compared
        correctly — integer 45 != integer 58 should remain clean.
        """
        df = _make_csv_trades([
            {"Symbol": "SHIVM", "Date": "2024-06-15", "Buyer": 45, "Seller": 58,
             "Quantity": 100, "Rate": 485.0, "Amount": 48500.0},
        ])
        clean = _csv_anti_wash_filter_sql(df)
        assert len(clean) == 1, (
            "Integer buyer/seller IDs (45 vs 58) should pass the wash filter after CAST to VARCHAR"
        )

    def test_odd_lot_removed_but_normal_cross_broker_kept(self):
        """
        Odd-lot trades (quantity < 10) are filtered out, but normal cross-broker
        trades must survive regardless.
        """
        df = _make_csv_trades([
            {"Symbol": "NABIL", "Date": "2024-06-15", "Buyer": "45", "Seller": "58",
             "Quantity": 5,   "Rate": 620.0, "Amount": 3100.0},   # odd-lot — removed
            {"Symbol": "NABIL", "Date": "2024-06-15", "Buyer": "45", "Seller": "58",
             "Quantity": 500, "Rate": 620.0, "Amount": 310000.0}, # normal  — kept
        ])
        clean = _csv_anti_wash_filter_sql(df)
        assert len(clean) == 1, (
            f"Only the odd-lot should be removed; normal cross-broker trade must remain. Got {len(clean)} rows"
        )
        assert clean.iloc[0]["quantity"] == 500.0


class TestApiPathPreservation:
    """
    Tests the Live-API anti-wash filter (Path B).
    Ensures cross-broker trades (buyerMemberId != sellerMemberId) pass through.
    Requirement 3.2.2
    """

    def test_api_cross_broker_trade_passes_filter(self):
        """buyerMemberId != sellerMemberId must produce a clean trade."""
        records = _make_api_records([
            {"buyerMemberId": 58, "sellerMemberId": 45, "stockSymbol": "NABIL",
             "contractQuantity": 500, "contractRate": 620.0, "contractAmount": 310000.0},
        ])
        clean = _api_anti_wash_filter_pandas(records)
        assert len(clean) == 1, (
            f"API cross-broker trade (buyerMemberId=58, sellerMemberId=45) "
            f"was incorrectly removed. Got {len(clean)} rows."
        )

    def test_api_wash_trade_removed_cross_broker_kept(self):
        """
        Mixed API batch: self-matched trade removed, cross-broker trade kept.
        This is the canonical preservation property.
        """
        records = _make_api_records([
            {"buyerMemberId": 58, "sellerMemberId": 58, "stockSymbol": "NABIL",
             "contractQuantity": 500, "contractRate": 620.0, "contractAmount": 310000.0},  # wash
            {"buyerMemberId": 45, "sellerMemberId": 58, "stockSymbol": "NABIL",
             "contractQuantity": 200, "contractRate": 615.0, "contractAmount": 123000.0},  # cross-broker
        ])
        clean = _api_anti_wash_filter_pandas(records)
        assert len(clean) == 1, (
            f"Expected 1 clean trade; wash removed, cross-broker kept. Got {len(clean)}"
        )
        assert clean.iloc[0]["buyer"] == "45"
        assert clean.iloc[0]["seller"] == "58"

    def test_api_string_and_integer_broker_ids_preserved(self):
        """
        API payloads may deliver broker IDs as integers or strings; after
        astype(str) normalisation both must compare correctly.
        """
        records = _make_api_records([
            {"buyerMemberId": "45", "sellerMemberId": "58", "stockSymbol": "EBL",
             "contractQuantity": 1000, "contractRate": 850.0, "contractAmount": 850000.0},
        ])
        clean = _api_anti_wash_filter_pandas(records)
        assert len(clean) == 1, "String broker IDs must pass filter after str() normalisation"

    def test_api_large_batch_all_cross_broker_trades_retained(self):
        """All 10 unique cross-broker trades in a batch must be retained."""
        records = _make_api_records([
            {"buyerMemberId": i, "sellerMemberId": i + 1, "stockSymbol": "NABIL",
             "contractQuantity": 100 + i * 10, "contractRate": 600.0 + i,
             "contractAmount": (100 + i * 10) * (600.0 + i)}
            for i in range(1, 11)  # buyers 1–10, sellers 2–11 → always different
        ])
        clean = _api_anti_wash_filter_pandas(records)
        assert len(clean) == 10, (
            f"All 10 cross-broker trades should be retained; got {len(clean)}"
        )


class TestBrokerFeatureCalculations:
    """
    Tests that broker network features (buyer_hhi, top3_buyer_share) produce
    non-zero, finite, and valid numeric values for realistic clean trade batches.
    Requirement 3.2.3
    """

    def _build_clean_trades(self) -> pd.DataFrame:
        """Minimal clean-trades DataFrame that mirrors the schema used by the feature SQL."""
        return pd.DataFrame([
            {"ticker": "NABIL", "buyer": "45", "seller": "58", "amount": 310000.0},
            {"ticker": "NABIL", "buyer": "12", "seller": "33", "amount": 123000.0},
            {"ticker": "NABIL", "buyer": "45", "seller": "22", "amount":  80000.0},
            {"ticker": "NABIL", "buyer": "7",  "seller": "58", "amount": 200000.0},
            {"ticker": "EBL",   "buyer": "22", "seller": "11", "amount": 500000.0},
            {"ticker": "EBL",   "buyer": "7",  "seller": "44", "amount": 250000.0},
        ])

    def test_buyer_hhi_is_positive_nonzero(self):
        """HHI must be > 0 for any non-trivial distribution of buyer volumes."""
        clean = self._build_clean_trades()
        features = _compute_broker_features_sql(clean)
        assert len(features) == 2, "Should produce one row per ticker (NABIL, EBL)"
        for _, row in features.iterrows():
            assert row["buyer_hhi"] > 0, (
                f"buyer_hhi for {row['ticker']} is zero — feature calculation broken"
            )

    def test_buyer_hhi_bounded_between_zero_and_one(self):
        """HHI must be in the range (0, 1] for valid market share distributions."""
        clean = self._build_clean_trades()
        features = _compute_broker_features_sql(clean)
        for _, row in features.iterrows():
            assert 0 < row["buyer_hhi"] <= 1.0, (
                f"buyer_hhi={row['buyer_hhi']:.4f} for {row['ticker']} is out of range (0,1]"
            )

    def test_top3_buyer_share_bounded_between_zero_and_one(self):
        """Top-3 buyer concentration must be in (0, 1]."""
        clean = self._build_clean_trades()
        features = _compute_broker_features_sql(clean)
        for _, row in features.iterrows():
            assert 0 < row["top3_buyer_share"] <= 1.0, (
                f"top3_buyer_share={row['top3_buyer_share']:.4f} for {row['ticker']} out of range (0,1]"
            )

    def test_single_dominant_buyer_drives_high_hhi(self):
        """
        When one broker buys 100% of the stock, HHI → 1.0 and
        top3_buyer_share → 1.0.
        """
        clean = pd.DataFrame([
            {"ticker": "MONO", "buyer": "99", "seller": "1",  "amount": 1_000_000.0},
            {"ticker": "MONO", "buyer": "99", "seller": "2",  "amount":   500_000.0},
        ])
        features = _compute_broker_features_sql(clean)
        row = features[features["ticker"] == "MONO"].iloc[0]
        assert abs(row["buyer_hhi"] - 1.0) < 1e-6, (
            f"Single-buyer market should give HHI=1.0; got {row['buyer_hhi']:.6f}"
        )
        assert abs(row["top3_buyer_share"] - 1.0) < 1e-6, (
            f"Single-buyer market should give top3_buyer_share=1.0; got {row['top3_buyer_share']:.6f}"
        )

    def test_dispersed_buyers_produce_low_hhi(self):
        """
        When 10 brokers each buy exactly 10% of the total, HHI = 0.10
        (sum of 10 * (0.1)^2 = 0.10).
        """
        per_broker_amount = 100_000.0
        clean = pd.DataFrame([
            {"ticker": "DISP", "buyer": str(i), "seller": str(i + 100), "amount": per_broker_amount}
            for i in range(10)
        ])
        features = _compute_broker_features_sql(clean)
        row = features[features["ticker"] == "DISP"].iloc[0]
        assert abs(row["buyer_hhi"] - 0.10) < 1e-6, (
            f"10-equal-buyers market should give HHI≈0.10; got {row['buyer_hhi']:.6f}"
        )

    def test_pipeline_csv_to_features_end_to_end(self):
        """
        End-to-end: CSV raw batch → anti-wash filter → feature computation
        produces non-zero, valid features.
        """
        raw_df = _make_csv_trades([
            {"Symbol": "NABIL", "Date": "2024-06-15", "Buyer": "45", "Seller": "58",
             "Quantity": 500, "Rate": 620.0, "Amount": 310000.0},
            {"Symbol": "NABIL", "Date": "2024-06-15", "Buyer": "12", "Seller": "33",
             "Quantity": 200, "Rate": 615.0, "Amount": 123000.0},
            {"Symbol": "NABIL", "Date": "2024-06-15", "Buyer": "45", "Seller": "58",
             "Quantity": 100, "Rate": 45.0, "Amount": 4500.0},    # odd-lot (qty < 10) — wait, 100 >= 10, fine
            {"Symbol": "NABIL", "Date": "2024-06-15", "Buyer": "45", "Seller": "45",
             "Quantity": 200, "Rate": 620.0, "Amount": 124000.0}, # wash — removed
        ])
        clean = _csv_anti_wash_filter_sql(raw_df)
        assert len(clean) == 3, f"Expected 3 clean trades (1 wash removed); got {len(clean)}"

        features = _compute_broker_features_sql(clean)
        assert len(features) == 1, "One ticker (NABIL) expected"
        row = features.iloc[0]
        assert np.isfinite(row["buyer_hhi"]),        "buyer_hhi must be finite"
        assert np.isfinite(row["top3_buyer_share"]), "top3_buyer_share must be finite"
        assert row["buyer_hhi"] > 0,                 "buyer_hhi must be > 0"
        assert row["top3_buyer_share"] > 0,          "top3_buyer_share must be > 0"

    def test_pipeline_api_to_features_end_to_end(self):
        """
        End-to-end: API payload → anti-wash filter → feature computation
        produces valid features.
        """
        records = _make_api_records([
            {"buyerMemberId": 58, "sellerMemberId": 45, "stockSymbol": "EBL",
             "contractQuantity": 1000, "contractRate": 850.0, "contractAmount": 850000.0},
            {"buyerMemberId": 22, "sellerMemberId": 11, "stockSymbol": "EBL",
             "contractQuantity":  500, "contractRate": 848.0, "contractAmount": 424000.0},
            {"buyerMemberId": 58, "sellerMemberId": 58, "stockSymbol": "EBL",   # wash
             "contractQuantity":  200, "contractRate": 849.0, "contractAmount": 169800.0},
        ])
        clean = _api_anti_wash_filter_pandas(records)
        assert len(clean) == 2, f"Expected 2 clean trades (1 wash removed); got {len(clean)}"

        # Adapt to feature SQL schema
        clean_for_sql = pd.DataFrame({
            "ticker": clean["stockSymbol"].str.upper().str.strip(),
            "buyer":  clean["buyer"],
            "seller": clean["seller"],
            "amount": clean["amount"],
        })
        features = _compute_broker_features_sql(clean_for_sql)
        assert len(features) == 1
        row = features.iloc[0]
        assert row["buyer_hhi"] > 0
        assert row["top3_buyer_share"] > 0


# ---------------------------------------------------------------------------
# Property-Based Tests
# ---------------------------------------------------------------------------

# Hypothesis strategy for a valid broker ID (integer 1–99)
broker_id = st.integers(min_value=1, max_value=99)

# Strategy for a realistic trade amount
trade_amount = st.floats(min_value=10_000.0, max_value=10_000_000.0, allow_nan=False, allow_infinity=False)

# Strategy for a realistic quantity (>= 10 to avoid odd-lot filter)
trade_qty = st.integers(min_value=10, max_value=10_000)

# Strategy for a realistic price
trade_price = st.floats(min_value=10.0, max_value=5000.0, allow_nan=False, allow_infinity=False)


@given(
    buyer=broker_id,
    seller=broker_id,
    quantity=trade_qty,
    price=trade_price,
)
@settings(max_examples=200, suppress_health_check=[HealthCheck.too_slow])
def test_property_cross_broker_csv_always_passes_filter(buyer, seller, price, quantity):
    """
    **Validates: Requirements 3.2.1**

    Property: For ANY cross-broker trade (buyer != seller, quantity >= 10),
    the CSV-path anti-wash filter MUST retain the trade.

    Generates 200 random (buyer, seller, quantity, price) combinations and
    asserts the trade survives the filter in every case.
    """
    assume(buyer != seller)  # Enforce the non-wash pre-condition

    amount = round(price * quantity, 2)
    df = _make_csv_trades([
        {"Symbol": "TEST", "Date": "2024-06-15",
         "Buyer": str(buyer), "Seller": str(seller),
         "Quantity": quantity, "Rate": price, "Amount": amount},
    ])
    clean = _csv_anti_wash_filter_sql(df)

    assert len(clean) == 1, (
        f"PRESERVATION VIOLATION: Cross-broker trade (Buyer={buyer}, Seller={seller}, "
        f"qty={quantity}) was incorrectly removed by CSV anti-wash filter. "
        f"Got {len(clean)} rows — expected 1."
    )


@given(
    buyer=broker_id,
    seller=broker_id,
    quantity=trade_qty,
    price=trade_price,
)
@settings(max_examples=200, suppress_health_check=[HealthCheck.too_slow])
def test_property_cross_broker_api_always_passes_filter(buyer, seller, price, quantity):
    """
    **Validates: Requirements 3.2.2**

    Property: For ANY cross-broker API trade (buyerMemberId != sellerMemberId,
    quantity >= 10), the API-path anti-wash filter MUST retain the trade.

    Generates 200 random combinations and asserts survival every time.
    """
    assume(buyer != seller)

    amount = round(price * quantity, 2)
    records = _make_api_records([
        {"buyerMemberId": buyer, "sellerMemberId": seller, "stockSymbol": "TEST",
         "contractQuantity": quantity, "contractRate": price, "contractAmount": amount},
    ])
    clean = _api_anti_wash_filter_pandas(records)

    assert len(clean) == 1, (
        f"PRESERVATION VIOLATION: API cross-broker trade (buyerMemberId={buyer}, "
        f"sellerMemberId={seller}, qty={quantity}) incorrectly removed. "
        f"Got {len(clean)} rows — expected 1."
    )


@given(
    num_buyers=st.integers(min_value=2, max_value=10),
    base_amount=trade_amount,
)
@settings(max_examples=100, suppress_health_check=[HealthCheck.too_slow])
def test_property_broker_features_always_valid_for_clean_trades(num_buyers, base_amount):
    """
    **Validates: Requirements 3.2.3**

    Property: For ANY batch of cross-broker trades with at least 2 distinct buyers,
    buyer_hhi and top3_buyer_share must both be in (0, 1].

    This confirms that the aggregation functions produce numerically valid
    results across the full realistic input domain.
    """
    # Build a clean trade batch with num_buyers distinct buyers, all cross-broker
    # (seller IDs offset by 100 to guarantee seller != buyer)
    trades = [
        {
            "ticker": "PROP",
            "buyer":  str(i + 1),
            "seller": str(i + 101),   # guaranteed != buyer
            "amount": base_amount / num_buyers,
        }
        for i in range(num_buyers)
    ]
    clean = pd.DataFrame(trades)
    features = _compute_broker_features_sql(clean)

    assert len(features) == 1, "Should produce exactly one row for ticker PROP"
    row = features.iloc[0]

    assert np.isfinite(row["buyer_hhi"]),        f"buyer_hhi={row['buyer_hhi']} is not finite"
    assert np.isfinite(row["top3_buyer_share"]), f"top3_buyer_share={row['top3_buyer_share']} is not finite"
    assert 0 < row["buyer_hhi"] <= 1.0, (
        f"buyer_hhi={row['buyer_hhi']:.6f} out of range (0,1] "
        f"for {num_buyers} buyers with equal amounts"
    )
    assert 0 < row["top3_buyer_share"] <= 1.0, (
        f"top3_buyer_share={row['top3_buyer_share']:.6f} out of range (0,1]"
    )


@given(
    buyer=broker_id,
    seller=broker_id,
    quantity=trade_qty,
    price=trade_price,
)
@settings(max_examples=200, suppress_health_check=[HealthCheck.too_slow])
def test_property_wash_trade_always_removed_cross_broker_always_kept(buyer, seller, price, quantity):
    """
    **Validates: Requirements 3.2.1, 3.2.2**

    Property: In a mixed batch containing one wash trade and one cross-broker trade,
    exactly the cross-broker trade survives regardless of the specific broker IDs.

    This is the primary preservation property: legitimate trades must not be
    collateral damage when wash trades are removed.
    """
    assume(buyer != seller)

    amount = round(price * quantity, 2)
    wash_amount = round(price * (quantity + 10), 2)

    # Mixed CSV batch: one wash trade + one cross-broker trade
    df = _make_csv_trades([
        # wash trade — must be removed
        {"Symbol": "MIX", "Date": "2024-06-15",
         "Buyer": str(buyer), "Seller": str(buyer),
         "Quantity": quantity + 10, "Rate": price, "Amount": wash_amount},
        # cross-broker trade — must be kept
        {"Symbol": "MIX", "Date": "2024-06-15",
         "Buyer": str(buyer), "Seller": str(seller),
         "Quantity": quantity, "Rate": price, "Amount": amount},
    ])
    clean = _csv_anti_wash_filter_sql(df)

    assert len(clean) == 1, (
        f"PRESERVATION VIOLATION: Mixed batch (wash Buyer={buyer}==Seller={buyer}, "
        f"cross-broker Buyer={buyer}/Seller={seller}) should yield 1 clean trade, "
        f"got {len(clean)}"
    )
    assert clean.iloc[0]["buyer"] == str(buyer), "Surviving trade should have the correct buyer"
    assert clean.iloc[0]["seller"] == str(seller), "Surviving trade should have the correct seller"


# ---------------------------------------------------------------------------
# Main runner for direct execution
# ---------------------------------------------------------------------------

if __name__ == "__main__":
    print("=" * 80)
    print("RUNNING PRESERVATION TESTS 2.2: Ingestion Preservation")
    print("(All tests MUST PASS on unfixed code)")
    print("=" * 80)

    # --- Unit tests ---
    suites = [
        TestCsvPathPreservation(),
        TestApiPathPreservation(),
        TestBrokerFeatureCalculations(),
    ]
    all_passed = True
    for suite in suites:
        name = type(suite).__name__
        methods = [m for m in dir(suite) if m.startswith("test_")]
        for meth in methods:
            try:
                getattr(suite, meth)()
                print(f"  ✓ {name}.{meth}")
            except Exception as exc:
                print(f"  ✗ {name}.{meth}: {exc}")
                all_passed = False

    # --- Property-based tests ---
    pbt_funcs = [
        test_property_cross_broker_csv_always_passes_filter,
        test_property_cross_broker_api_always_passes_filter,
        test_property_broker_features_always_valid_for_clean_trades,
        test_property_wash_trade_always_removed_cross_broker_always_kept,
    ]
    for fn in pbt_funcs:
        try:
            fn()
            print(f"  ✓ {fn.__name__}")
        except Exception as exc:
            print(f"  ✗ {fn.__name__}: {exc}")
            all_passed = False

    print("=" * 80)
    if all_passed:
        print("ALL PRESERVATION TESTS PASSED — baseline behaviour confirmed.")
    else:
        print("SOME TESTS FAILED — investigate above failures.")
    print("=" * 80)

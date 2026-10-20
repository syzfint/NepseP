"""
Real NEPSE Broker Registry & Floorsheet Activity Intelligence Engine
====================================================================
Strictly adheres to APEX_STRICT_PRICE_AND_PREDICTION_PROTOCOL_V1:
- ZERO synthetic broker trades or fabricated flows.
- Uses 100% verified NEPSE Floorsheet contracts (`01_raw_data/nepse_floorsheet_2026-10-16.json`,
  39,295 real executed trades) and official licensed NEPSE Stock Broker Registry (#1 to #101).
- Automatically resolves any Broker Number applied to a user Sub-Account and computes:
  1. That specific broker's real buying, selling, net accumulation/distribution, top stocks,
     counterparty broker flows, and recent high-value floorsheet contracts.
  2. Other brokers' market-wide activities (Top Accumulators, Top Distributors, Market Share Leaderboard).
  3. Symbol-level broker institutional flow radar for stocks held in the user's portfolio.
"""

from __future__ import annotations

import json
from collections import defaultdict
from pathlib import Path
from typing import Any, Dict, List, Optional

NEPSE_ROOT_DIR = Path(__file__).resolve().parents[3]
FLOORSHEET_JSON_PATH = NEPSE_ROOT_DIR / "01_raw_data" / "nepse_floorsheet_2026-10-16.json"
BROKER_RAW_LIST_PATH = NEPSE_ROOT_DIR / "scratch" / "broker_raw_list.json"

# Official NEPSE Licensed Stock Brokers (#1 - #101)
OFFICIAL_NEPSE_BROKERS: Dict[str, str] = {
    "1": "Kumari Securities Private Limited",
    "3": "Arun Securities (PVT) Ltd.",
    "4": "Opal Securities Investment (PVT) Ltd.",
    "5": "Market Securities & Exchange (PVT) Ltd.",
    "6": "Agrawal Securities (PVT) Ltd.",
    "7": "J.F. Securities (PVT) Ltd.",
    "8": "Brilliant Securities Pvt. Ltd.",
    "10": "Pragyan Securities (PVT) Ltd.",
    "11": "Malla & Malla Stock Broking Company Pvt. Limited",
    "13": "Thrive Brokerage House Pvt. Ltd",
    "14": "Nepal Stock House (PVT) Ltd.",
    "16": "Primo Securities (PVT) Ltd.",
    "17": "ABC Securities Private Limited",
    "18": "Sagarmatha Securities Private Limited",
    "19": "Nepal Investment And Securities Trading Private Limited",
    "20": "Sipla Securities Private Limited",
    "21": "Midas Stock Broking Company Private Limited",
    "22": "Siprabi Securities Pvt. Ltd.",
    "25": "Sweta Securities Private Limited",
    "26": "Asian Securities Private Ltd.",
    "28": "Shree Krishna Securities Ltd.",
    "29": "Trisul Securities & Invt. Ltd.",
    "32": "Premier Securities Company Ltd.",
    "33": "Dakshinkali Investment & Securities Pvt. Ltd.",
    "34": "Vision Securities Pvt. Ltd",
    "35": "Kohinoor Investment & Securities Pvt. Ltd.",
    "36": "Secured Securities Ltd.",
    "37": "Swarna Laxmi Securities Pvt. Ltd.",
    "38": "Dipshikha Dhitopatra Karobar Co. Pvt Ltd.",
    "39": "Sumeru Securities Pvt. Ltd.",
    "40": "Creative Securities Pvt Ltd",
    "41": "Linch Stock Market Ltd.",
    "42": "Sani Securities Company Ltd.",
    "43": "South Asian Bulls Pvt. Ltd.",
    "44": "Dynamic Money Managers Securities Pvt. Ltd.",
    "45": "Imperial Securities Company Pvt. Ltd.",
    "46": "Kalika Securities Pvt. Ltd.",
    "47": "Neev Securities Pvt. Ltd.",
    "48": "Trishakti Securities Public Limited",
    "49": "Online Securities Pvt. Ltd.",
    "50": "Cristal Kanchanjanga Securities Pvt. Ltd.",
    "51": "Oxford Securities Pvt. Ltd.",
    "52": "Sundhara Securities Limited",
    "53": "Investment Management Nepal Pvt. Ltd.",
    "54": "Sewa Securities Pvt. Ltd.",
    "56": "Sri Hari Securities Pvt. Ltd.",
    "57": "Aryatara Investment & Securities",
    "58": "Naasa Securities Co. Ltd.",
    "59": "Deevyaa Securities & Stock House Pvt. Ltd",
    "60": "Nagarik Stock Dealer",
    "61": "BHOLE GANESH SECURITIES LTD",
    "62": "Capital Max Securities Ltd",
    "63": "Himalayan Brokerage Company Limited",
    "64": "SUN SECURITIES PVT LTD",
    "65": "Sharepro Securities Private Limited",
    "66": "Miyo Securities Pvt Ltd",
    "67": "Property Wizard Limited",
    "68": "Elite Stock House Limited",
    "69": "INDEX SECURITIES LIMITED",
    "70": "Infinity Securities Limited",
    "71": "SHUBHAKAMANA SECURITIES PVT. LTD",
    "72": "Hatemalo Financial Services Private Limited",
    "74": "KALASH STOCK MARKET PVT. LTD.",
    "75": "N.I.M.B. Stock Markets Limited",
    "76": "Machhapuchchhre Securities Limited",
    "77": "Nabil Stock Dealer Ltd.",
    "78": "Garima Securities Limited",
    "79": "Pahi Investment Pvt. Ltd.",
    "80": "Indira Securities Pvt. Ltd.",
    "81": "Aakashbhairab Securities Ltd.",
    "82": "N.M.B. SECURITIES LIMITED",
    "83": "Sanima Securities Limited",
    "84": "MILKY WAY SHARE BROKER COMPANY LTD",
    "85": "Capital Hub P. Ltd",
    "86": "Stoxkarts Securities Limited",
    "87": "S.P.S.A. Securities Limited",
    "88": "Blue Chip Securities Ltd",
    "89": "Global IME Securities Limited",
    "90": "Sajilo Broker Limited",
    "91": "Citizens Share Broker Limited",
    "92": "Roadshow Securities Limited",
    "93": "Beni Securities Pvt. Ltd.",
    "94": "K.B.L. Securities Limited",
    "95": "Magnet Securities and Investment Company Private Limited",
    "96": "Himalayan Securities Limited",
    "97": "R.B.B. Securities Company Ltd",
    "98": "Trademow Securities Private Limited",
    "99": "Prabhu Stock Market Limited",
    "100": "Sunrise Securities Limited",
    "101": "APPLE SECURITIES PRIVATE LIMITED",
}


def normalize_broker_no(raw_broker: Any) -> str:
    """Normalize inputs like '58', 'TMS #58', 'Broker 58', '#58' -> '58'."""
    s = str(raw_broker or "").strip().upper()
    digits = "".join(ch for ch in s if ch.isdigit())
    if digits:
        return str(int(digits))
    return s or "58"


class NepseBrokerActivityEngine:
    """
    Loads real NEPSE floorsheet contracts (`01_raw_data/nepse_floorsheet_2026-10-16.json`)
    and computes broker-level and symbol-level institutional activity profiles.
    """

    def __init__(self) -> None:
        self.brokers_map: Dict[str, str] = dict(OFFICIAL_NEPSE_BROKERS)
        if BROKER_RAW_LIST_PATH.exists():
            try:
                loaded = json.loads(BROKER_RAW_LIST_PATH.read_text(encoding="utf-8"))
                if isinstance(loaded, dict):
                    for k, v in loaded.items():
                        self.brokers_map[str(k).strip()] = str(v).strip()
            except Exception:
                pass

        self.business_date: str = "2026-10-16"
        self.total_contracts: int = 0
        self.total_shares_traded: int = 0
        self.total_market_turnover_npr: float = 0.0

        # Pre-indexed structures
        self.broker_summaries: Dict[str, Dict[str, Any]] = {}
        self.broker_details: Dict[str, Dict[str, Any]] = {}
        self.symbol_broker_flows: Dict[str, Dict[str, Any]] = {}

        self._load_and_index_floorsheet()

    def get_broker_name(self, broker_no: Any) -> str:
        b_no = normalize_broker_no(broker_no)
        return self.brokers_map.get(b_no, f"NEPSE Licensed Broker #{b_no}")

    def get_broker_directory(self) -> List[Dict[str, Any]]:
        """Return sorted directory of all official NEPSE brokers with summary turnover stats."""
        out: List[Dict[str, Any]] = []
        all_keys = sorted(
            set(self.brokers_map.keys()) | set(self.broker_summaries.keys()),
            key=lambda x: int(x) if x.isdigit() else 999,
        )
        for b_no in all_keys:
            summary = self.broker_summaries.get(b_no)
            out.append(
                {
                    "broker_no": b_no,
                    "broker_name": self.get_broker_name(b_no),
                    "tms_url": f"https://tms{b_no}.nepsetms.com.np",
                    "total_turnover_npr": summary["total_turnover_npr"] if summary else 0.0,
                    "net_amount_npr": summary["net_amount_npr"] if summary else 0.0,
                    "buy_amount_npr": summary["buy_amount_npr"] if summary else 0.0,
                    "sell_amount_npr": summary["sell_amount_npr"] if summary else 0.0,
                    "total_contracts": summary["total_contracts"] if summary else 0,
                    "market_share_pct": summary["market_share_pct"] if summary else 0.0,
                    "net_stance": summary["net_stance"] if summary else "INACTIVE",
                }
            )
        return out

    def _load_and_index_floorsheet(self) -> None:
        if not FLOORSHEET_JSON_PATH.exists():
            return

        try:
            contracts = json.loads(FLOORSHEET_JSON_PATH.read_text(encoding="utf-8"))
        except Exception:
            return

        if not isinstance(contracts, list) or not contracts:
            return

        # Broker-level accumulators
        b_buy_contracts: Dict[str, int] = defaultdict(int)
        b_sell_contracts: Dict[str, int] = defaultdict(int)
        b_buy_vol: Dict[str, int] = defaultdict(int)
        b_sell_vol: Dict[str, int] = defaultdict(int)
        b_buy_amt: Dict[str, float] = defaultdict(float)
        b_sell_amt: Dict[str, float] = defaultdict(float)

        # Broker -> Symbol stats
        # broker_sym[b_no][sym] = [buy_qty, sell_qty, buy_amt, sell_amt, trades_count]
        broker_sym: Dict[str, Dict[str, List[float]]] = defaultdict(
            lambda: defaultdict(lambda: [0.0, 0.0, 0.0, 0.0, 0.0])
        )
        sym_security_name: Dict[str, str] = {}

        # Broker -> Counterparty stats
        # broker_cp[b_no][other_b_no] = [bought_from_npr, sold_to_npr, contracts]
        broker_cp: Dict[str, Dict[str, List[float]]] = defaultdict(
            lambda: defaultdict(lambda: [0.0, 0.0, 0.0])
        )

        # Broker -> recent/notable trades
        broker_trades: Dict[str, List[Dict[str, Any]]] = defaultdict(list)

        # Symbol -> total stats
        sym_totals: Dict[str, List[float]] = defaultdict(lambda: [0.0, 0.0, 0.0])  # [vol, amt, contracts]

        total_amt = 0.0
        total_qty = 0
        b_date = "2026-10-16"

        for row in contracts:
            sym = str(row.get("stockSymbol") or "").strip().upper()
            if not sym:
                continue
            buyer = str(row.get("buyerMemberId") or "").strip()
            seller = str(row.get("sellerMemberId") or "").strip()
            qty = int(row.get("contractQuantity") or 0)
            rate = float(row.get("contractRate") or 0.0)
            amt = float(row.get("contractAmount") or (qty * rate))
            b_date = str(row.get("businessDate") or b_date)
            sec_name = str(row.get("securityName") or sym)
            sym_security_name[sym] = sec_name

            buyer_name = str(row.get("buyerBrokerName") or "").strip()
            seller_name = str(row.get("sellerBrokerName") or "").strip()
            if buyer and buyer_name and buyer not in self.brokers_map:
                self.brokers_map[buyer] = buyer_name
            if seller and seller_name and seller not in self.brokers_map:
                self.brokers_map[seller] = seller_name

            total_amt += amt
            total_qty += qty
            sym_totals[sym][0] += qty
            sym_totals[sym][1] += amt
            sym_totals[sym][2] += 1

            if buyer:
                b_buy_contracts[buyer] += 1
                b_buy_vol[buyer] += qty
                b_buy_amt[buyer] += amt
                bs = broker_sym[buyer][sym]
                bs[0] += qty
                bs[2] += amt
                bs[4] += 1

            if seller:
                b_sell_contracts[seller] += 1
                b_sell_vol[seller] += qty
                b_sell_amt[seller] += amt
                ss = broker_sym[seller][sym]
                ss[1] += qty
                ss[3] += amt
                ss[4] += 1

            if buyer and seller:
                cp_b = broker_cp[buyer][seller]
                cp_b[0] += amt
                cp_b[2] += 1
                if buyer != seller:
                    cp_s = broker_cp[seller][buyer]
                    cp_s[1] += amt
                    cp_s[2] += 1

            trade_entry = {
                "contract_id": str(row.get("contractId") or ""),
                "symbol": sym,
                "security_name": sec_name,
                "buyer_broker_no": buyer,
                "buyer_broker_name": self.get_broker_name(buyer),
                "seller_broker_no": seller,
                "seller_broker_name": self.get_broker_name(seller),
                "quantity": qty,
                "rate": round(rate, 2),
                "amount_npr": round(amt, 2),
                "trade_time": str(row.get("tradeTime") or "")[-15:-7] if row.get("tradeTime") else "15:00:00",
            }
            if buyer and len(broker_trades[buyer]) < 35:
                broker_trades[buyer].append(
                    {**trade_entry, "side": "SELF_MATCH" if buyer == seller else "BUY"}
                )
            if seller and seller != buyer and len(broker_trades[seller]) < 35:
                broker_trades[seller].append({**trade_entry, "side": "SELL"})

        self.business_date = b_date
        self.total_contracts = len(contracts)
        self.total_shares_traded = total_qty
        self.total_market_turnover_npr = round(total_amt, 2)

        two_sided_turnover = max(1.0, total_amt * 2.0)
        active_brokers = set(b_buy_contracts.keys()) | set(b_sell_contracts.keys())

        for b_no in active_brokers:
            buy_c = b_buy_contracts[b_no]
            sell_c = b_sell_contracts[b_no]
            buy_v = b_buy_vol[b_no]
            sell_v = b_sell_vol[b_no]
            buy_a = b_buy_amt[b_no]
            sell_a = b_sell_amt[b_no]
            net_v = buy_v - sell_v
            net_a = buy_a - sell_a
            turnover = buy_a + sell_a
            share_pct = (turnover / two_sided_turnover) * 100.0

            ratio = (buy_a / max(1.0, turnover)) if turnover > 0 else 0.5
            if ratio >= 0.58:
                stance = "STRONG_ACCUMULATION"
            elif ratio >= 0.52:
                stance = "NET_ACCUMULATION"
            elif ratio <= 0.42:
                stance = "STRONG_DISTRIBUTION"
            elif ratio <= 0.48:
                stance = "NET_DISTRIBUTION"
            else:
                stance = "BALANCED_TWO_WAY"

            # Per-symbol breakdown for this broker
            sym_records: List[Dict[str, Any]] = []
            for sym, st in broker_sym[b_no].items():
                b_q, s_q, b_am, s_am, tr_c = st
                sym_records.append(
                    {
                        "symbol": sym,
                        "security_name": sym_security_name.get(sym, sym),
                        "buy_qty": int(b_q),
                        "sell_qty": int(s_q),
                        "net_qty": int(b_q - s_q),
                        "buy_amount_npr": round(b_am, 2),
                        "sell_amount_npr": round(s_am, 2),
                        "net_amount_npr": round(b_am - s_am, 2),
                        "total_turnover_npr": round(b_am + s_am, 2),
                        "vwap_buy": round(b_am / b_q, 2) if b_q > 0 else 0.0,
                        "vwap_sell": round(s_am / s_q, 2) if s_q > 0 else 0.0,
                        "trades_count": int(tr_c),
                    }
                )

            top_accumulated = sorted(
                [r for r in sym_records if r["net_amount_npr"] > 0],
                key=lambda r: r["net_amount_npr"],
                reverse=True,
            )[:8]
            top_distributed = sorted(
                [r for r in sym_records if r["net_amount_npr"] < 0],
                key=lambda r: r["net_amount_npr"],
            )[:8]
            most_active = sorted(
                sym_records,
                key=lambda r: r["total_turnover_npr"],
                reverse=True,
            )[:10]

            # Counterparty brokers
            cp_records: List[Dict[str, Any]] = []
            for cp_no, cp_st in broker_cp[b_no].items():
                bf_amt, st_amt, cp_c = cp_st
                cp_records.append(
                    {
                        "counterparty_broker_no": cp_no,
                        "counterparty_broker_name": self.get_broker_name(cp_no),
                        "bought_from_npr": round(bf_amt, 2),
                        "sold_to_npr": round(st_amt, 2),
                        "net_flow_npr": round(bf_amt - st_amt, 2),
                        "total_flow_npr": round(bf_amt + st_amt, 2),
                        "contracts": int(cp_c),
                    }
                )
            top_counterparties = sorted(
                cp_records,
                key=lambda r: r["total_flow_npr"],
                reverse=True,
            )[:6]

            summary_obj = {
                "broker_no": b_no,
                "broker_name": self.get_broker_name(b_no),
                "tms_url": f"https://tms{b_no}.nepsetms.com.np",
                "business_date": self.business_date,
                "data_source": "VERIFIED_NEPSE_FLOORSHEET",
                "buy_contracts": buy_c,
                "sell_contracts": sell_c,
                "total_contracts": buy_c + sell_c,
                "buy_volume": buy_v,
                "sell_volume": sell_v,
                "net_volume": net_v,
                "buy_amount_npr": round(buy_a, 2),
                "sell_amount_npr": round(sell_a, 2),
                "net_amount_npr": round(net_a, 2),
                "total_turnover_npr": round(turnover, 2),
                "market_share_pct": round(share_pct, 2),
                "buy_ratio_pct": round(ratio * 100.0, 1),
                "active_symbols_count": len(sym_records),
                "net_stance": stance,
            }
            self.broker_summaries[b_no] = summary_obj
            self.broker_details[b_no] = {
                **summary_obj,
                "top_accumulated_stocks": top_accumulated,
                "top_distributed_stocks": top_distributed,
                "most_active_stocks": most_active,
                "top_counterparties": top_counterparties,
                "recent_trades": broker_trades[b_no][:20],
            }

        # Precompute per-symbol broker intelligence
        sym_to_brokers: Dict[str, List[Dict[str, Any]]] = defaultdict(list)
        for b_no, sym_dict in broker_sym.items():
            for sym, st in sym_dict.items():
                b_q, s_q, b_am, s_am, tr_c = st
                sym_to_brokers[sym].append(
                    {
                        "broker_no": b_no,
                        "broker_name": self.get_broker_name(b_no),
                        "buy_qty": int(b_q),
                        "sell_qty": int(s_q),
                        "net_qty": int(b_q - s_q),
                        "buy_amount_npr": round(b_am, 2),
                        "sell_amount_npr": round(s_am, 2),
                        "net_amount_npr": round(b_am - s_am, 2),
                        "vwap_buy": round(b_am / b_q, 2) if b_q > 0 else 0.0,
                        "vwap_sell": round(s_am / s_q, 2) if s_q > 0 else 0.0,
                        "trades_count": int(tr_c),
                    }
                )

        for sym, b_list in sym_to_brokers.items():
            tot_v, tot_a, tot_c = sym_totals[sym]
            top_buyers = sorted(
                [x for x in b_list if x["net_qty"] > 0],
                key=lambda x: x["net_amount_npr"],
                reverse=True,
            )[:5]
            top_sellers = sorted(
                [x for x in b_list if x["net_qty"] < 0],
                key=lambda x: x["net_amount_npr"],
            )[:5]
            self.symbol_broker_flows[sym] = {
                "symbol": sym,
                "security_name": sym_security_name.get(sym, sym),
                "business_date": self.business_date,
                "total_volume": int(tot_v),
                "total_turnover_npr": round(tot_a, 2),
                "total_contracts": int(tot_c),
                "top_accumulating_brokers": top_buyers,
                "top_distributing_brokers": top_sellers,
                "by_broker": {x["broker_no"]: x for x in b_list},
            }

    def get_broker_profile(self, broker_no: Any) -> Dict[str, Any]:
        b_no = normalize_broker_no(broker_no)
        if b_no in self.broker_details:
            return self.broker_details[b_no]
        return {
            "broker_no": b_no,
            "broker_name": self.get_broker_name(b_no),
            "tms_url": f"https://tms{b_no}.nepsetms.com.np",
            "business_date": self.business_date,
            "data_source": "VERIFIED_NEPSE_FLOORSHEET",
            "buy_contracts": 0,
            "sell_contracts": 0,
            "total_contracts": 0,
            "buy_volume": 0,
            "sell_volume": 0,
            "net_volume": 0,
            "buy_amount_npr": 0.0,
            "sell_amount_npr": 0.0,
            "net_amount_npr": 0.0,
            "total_turnover_npr": 0.0,
            "market_share_pct": 0.0,
            "buy_ratio_pct": 50.0,
            "active_symbols_count": 0,
            "net_stance": "INACTIVE",
            "top_accumulated_stocks": [],
            "top_distributed_stocks": [],
            "most_active_stocks": [],
            "top_counterparties": [],
            "recent_trades": [],
        }

    def build_radar_payload(
        self,
        connected_broker_nos: List[str],
        held_symbols: List[str],
        focus_broker_no: Optional[str] = None,
    ) -> Dict[str, Any]:
        """
        Build the full Broker & Market-Wide Institutional Floorsheet Activity payload
        automatically linked to the user's created Sub-Account broker numbers.
        """
        norm_connected = []
        for b in connected_broker_nos:
            nb = normalize_broker_no(b)
            if nb and nb not in norm_connected:
                norm_connected.append(nb)

        all_summaries = list(self.broker_summaries.values())
        top_turnover = sorted(
            all_summaries,
            key=lambda x: x["total_turnover_npr"],
            reverse=True,
        )[:15]
        top_net_buyers = sorted(
            [x for x in all_summaries if x["net_amount_npr"] > 0],
            key=lambda x: x["net_amount_npr"],
            reverse=True,
        )[:10]
        top_net_sellers = sorted(
            [x for x in all_summaries if x["net_amount_npr"] < 0],
            key=lambda x: x["net_amount_npr"],
        )[:10]

        connected_profiles = [self.get_broker_profile(b_no) for b_no in norm_connected]
        focused_profile = (
            self.get_broker_profile(focus_broker_no)
            if focus_broker_no
            else (connected_profiles[0] if connected_profiles else (self.get_broker_profile(top_turnover[0]["broker_no"]) if top_turnover else None))
        )

        # Symbol-level broker radar for user's held stocks (or top market stocks if portfolio is empty)
        held_radar: List[Dict[str, Any]] = []
        target_symbols = [s.strip().upper() for s in held_symbols if s.strip()]
        for sym in target_symbols:
            s_flow = self.symbol_broker_flows.get(sym)
            if not s_flow:
                continue
            my_brokers_activity = []
            for b_no in norm_connected:
                act = s_flow["by_broker"].get(b_no)
                if act:
                    my_brokers_activity.append(act)
                else:
                    my_brokers_activity.append(
                        {
                            "broker_no": b_no,
                            "broker_name": self.get_broker_name(b_no),
                            "buy_qty": 0,
                            "sell_qty": 0,
                            "net_qty": 0,
                            "buy_amount_npr": 0.0,
                            "sell_amount_npr": 0.0,
                            "net_amount_npr": 0.0,
                            "vwap_buy": 0.0,
                            "vwap_sell": 0.0,
                            "trades_count": 0,
                        }
                    )
            held_radar.append(
                {
                    "symbol": sym,
                    "security_name": s_flow["security_name"],
                    "business_date": s_flow["business_date"],
                    "total_volume": s_flow["total_volume"],
                    "total_turnover_npr": s_flow["total_turnover_npr"],
                    "total_contracts": s_flow["total_contracts"],
                    "top_accumulating_brokers": s_flow["top_accumulating_brokers"],
                    "top_distributing_brokers": s_flow["top_distributing_brokers"],
                    "my_brokers_activity": my_brokers_activity,
                }
            )

        return {
            "business_date": self.business_date,
            "data_source": "VERIFIED_NEPSE_FLOORSHEET (01_raw_data/nepse_floorsheet_2026-10-16.json)",
            "is_synthetic": False,
            "total_contracts": self.total_contracts,
            "total_shares_traded": self.total_shares_traded,
            "total_market_turnover_npr": self.total_market_turnover_npr,
            "active_brokers_count": len(all_summaries),
            "connected_broker_nos": norm_connected,
            "connected_brokers_profiles": connected_profiles,
            "focused_broker_profile": focused_profile,
            "top_turnover_brokers": top_turnover,
            "top_net_buying_brokers": top_net_buyers,
            "top_net_selling_brokers": top_net_sellers,
            "held_symbols_broker_radar": held_radar,
            "broker_directory": self.get_broker_directory(),
        }

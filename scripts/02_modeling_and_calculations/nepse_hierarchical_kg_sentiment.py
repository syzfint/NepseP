"""
Two-Tier Hierarchical Sentiment Scoring Engine with Knowledge Graph Propagation
================================================================================
Adapted for NEPSE (Nepal Stock Exchange) from:
"Cross-Market Sentiment Propagation via Firm-Level Knowledge Graphs", ICAIF 2026.

Mathematical Specification:
- Stage 1: News Classification & Anchor Sentiment S_raw in [1, 100] (50 = neutral).
- Stage 2: Firm-Level Knowledge Graph Propagation:
           Delta p_{a -> c} = clip(S_raw * w_{a,c} * gamma^h, -Delta_max, +Delta_max), gamma = 0.5, H <= 2.
- Stage 3: Repetition Discount & Carry-Over Exponential Decay:
           W_rep = sum_i exp(-lambda_r * (t - t_i)), lambda_r = 0.35, N = 15 trading days.
           f = 1 / (1 + W_rep), S_adj = 50 + (S_raw - 50) * f.
           S_final = clip(50 + sum_{k=0..4} exp(-lambda_d * k) * delta_k, 1, 100), lambda_d = 0.46.
           Weights: [100%, 63%, 40%, 25%, 16%].
- Stage 4: Capitalisation-Weighted Daily Market Sentiment:
           score_local(t) = 50 + sum_j NP_j * w_j, where w_j = cap_j / sum(cap).
- Stage 5: Per-Firm SprintScore: NP_{j,t} aggregating direct + KG propagated decay-adjusted impacts.
- Tier 1 Calibration (Market-Level):
           C_t^{(1)} = beta * score_local(t) + (1 - beta) * Macro_t, beta = 0.25.
           M_t = 1 + 99 * sigma(a^{(1)} + rho^{(1)} * C_t^{(1)}) in [1, 100].
- Tier 2 Calibration (Stock-Level):
           C_{j,t}^{(2)} = a_j * NP_{j,t} + b_j * M_t + c_j * U_j, s.t. a_j + b_j + c_j = 1.
           S_{j,t} = 1 + 99 * sigma(a_j^{(2)} + rho_j^{(2)} * C_{j,t}^{(2)}) in [1, 100].
"""

import math
from typing import Dict, List, Tuple, Optional
from dataclasses import dataclass, field
import numpy as np


# ==========================================
# Fixed Ex-Ante Parameters (ICAIF 2026)
# ==========================================
BETA: float = 0.25            # Macro/Local blend weight in Tier 1
LAMBDA_R: float = 0.35        # Repetition-discount decay rate
LAMBDA_D: float = 0.46        # Carry-over time-decay rate
GAMMA: float = 0.5            # Knowledge graph hop-decay factor
H_MAX: int = 2                # Maximum propagation depth (hops)
DELTA_MAX: float = 50.0       # Single-path exposure cap
CARRYOVER_WINDOW: int = 5     # k = 0 ... 4 trading days
REPETITION_LOOKBACK: int = 15 # Trading days lookback


def sigmoid(x: float) -> float:
    """Numerically stable standard logistic sigmoid function."""
    if x >= 0:
        z = math.exp(-x)
        return 1.0 / (1.0 + z)
    else:
        z = math.exp(x)
        return z / (1.0 + z)


@dataclass
class KnowledgeGraphEdge:
    source: str
    target: str
    edge_type: str            # 'SUPPLIES_TO', 'SUBSIDIARY_OF', 'COMPETES_WITH', 'CREDIT_EXPOSURE'
    weight: float             # Exposure strength w_{a,c} in (0, 1]
    sign: float = 1.0         # +1.0 for supply-chain/conglomerate; -1.0 for pure competitor rivalry


class NepseKnowledgeGraph:
    """
    Firm-level Knowledge Graph G = (V, E) mapping relationships across NEPSE securities.
    Models:
    - Conglomerate / Group cross-holdings (Chaudhary, IME, Golchha, Shankar, Vishal groups)
    - PPA / Power Offtake supply-chains (Hydropower -> National Grid / Industrial Cement)
    - Commercial Bank consortium loans (Credit exposure to Hydro/Manufacturing)
    - Peer competition in banking, insurance, and manufacturing
    """
    def __init__(self):
        self.edges: Dict[str, List[KnowledgeGraphEdge]] = {}
        self.nodes: set = set()

    def add_edge(self, source: str, target: str, edge_type: str, weight: float, sign: float = 1.0):
        self.nodes.add(source)
        self.nodes.add(target)
        if source not in self.edges:
            self.edges[source] = []
        self.edges[source].append(KnowledgeGraphEdge(source, target, edge_type, weight, sign))

    def propagate_shock(self, anchor_symbol: str, raw_shock: float) -> Dict[str, float]:
        """
        Propagates anchor shock up to H_MAX=2 hops with hop-decay gamma=0.5.
        Returns dict of {target_symbol: aggregated_path_contribution}.
        """
        # delta p_{a -> c} = S_raw * w_{a,c} * gamma^h, clipped to [-DELTA_MAX, +DELTA_MAX]
        propagated: Dict[str, float] = {}

        # 1-hop propagation
        if anchor_symbol in self.edges:
            for e1 in self.edges[anchor_symbol]:
                c1 = e1.target
                w1 = e1.weight * e1.sign
                shock_1 = (raw_shock - 50.0) * w1 * (GAMMA ** 1)
                shock_1_capped = np.clip(shock_1, -DELTA_MAX, DELTA_MAX)
                propagated[c1] = propagated.get(c1, 0.0) + shock_1_capped

                # 2-hop propagation
                if H_MAX >= 2 and c1 in self.edges:
                    for e2 in self.edges[c1]:
                        c2 = e2.target
                        if c2 != anchor_symbol and c2 != c1:
                            w2 = w1 * (e2.weight * e2.sign)
                            shock_2 = (raw_shock - 50.0) * w2 * (GAMMA ** 2)
                            shock_2_capped = np.clip(shock_2, -DELTA_MAX, DELTA_MAX)
                            propagated[c2] = propagated.get(c2, 0.0) + shock_2_capped

        return propagated


def compute_repetition_discount(prior_appearance_lags: List[int]) -> float:
    """
    Calculates repetition discount factor f = 1 / (1 + W_rep).
    W_rep = sum_i exp(-lambda_r * (t - t_i)) over 15-day lookback.
    """
    valid_lags = [lag for lag in prior_appearance_lags if 0 < lag <= REPETITION_LOOKBACK]
    if not valid_lags:
        return 1.0
    w_rep = sum(math.exp(-LAMBDA_R * lag) for lag in valid_lags)
    f = 1.0 / (1.0 + w_rep)
    return float(np.clip(f, 0.0, 1.0))


def apply_carryover_decay(decay_deltas: List[float]) -> float:
    """
    Carry-over exponential decay over event day + 4 following trading days (k = 0 ... 4).
    Eq. 1: S_final = 50 + sum_k w_k * delta_k, w_k = exp(-lambda_d * k)
    Implied weights for lambda_d = 0.46: [1.0, 0.631, 0.399, 0.252, 0.159].
    """
    # Limit to maximum window of 5 days
    k_vals = list(range(min(len(decay_deltas), CARRYOVER_WINDOW)))
    weights = [math.exp(-LAMBDA_D * k) for k in k_vals]
    accumulated_delta = sum(w * d for w, d in zip(weights, decay_deltas[:CARRYOVER_WINDOW]))
    s_final = 50.0 + accumulated_delta
    return float(np.clip(s_final, 1.0, 100.0))


def calculate_tier1_market_score(
    local_score: float,
    macro_score: float,
    a_1: float = -0.05,
    rho_1: float = 0.038
) -> Tuple[float, float]:
    """
    Tier 1 Market-Level Calibration:
    Eq. 4: C_t^{(1)} = beta * score^{local}(t) + (1 - beta) * Macro_t (beta = 0.25)
    Eq. 5: p_t = sigma(a^{(1)} + rho^{(1)} * C_t^{(1)})
    Eq. 6: M_t = 1 + 99 * p_t in [1, 100]
    """
    composite_c1 = BETA * local_score + (1.0 - BETA) * macro_score
    p_t = sigmoid(a_1 + rho_1 * (composite_c1 - 50.0))
    m_t = 1.0 + 99.0 * p_t
    return float(m_t), float(composite_c1)


def calculate_tier2_stock_score(
    sprint_score: float,
    market_score: float,
    sovereign_score: float,
    weights: Tuple[float, float, float] = (0.20, 0.50, 0.30),
    a_2: float = 0.0,
    rho_2: float = 0.040
) -> Tuple[float, float]:
    """
    Tier 2 Stock-Level Calibration:
    Eq. 7: C_{j,t}^{(2)} = a_j * NP_{j,t} + b_j * M_t + c_j * U_j, s.t. a_j + b_j + c_j = 1
    Eq. 8: p_{j,t} = sigma(a_j^{(2)} + rho_j^{(2)} * C_{j,t}^{(2)})
    Eq. 9: S_{j,t} = 1 + 99 * p_{j,t} in [1, 100]
    """
    a_j, b_j, c_j = weights
    total_w = a_j + b_j + c_j
    if abs(total_w - 1.0) > 1e-5:
        a_j, b_j, c_j = a_j / total_w, b_j / total_w, c_j / total_w

    composite_c2 = a_j * sprint_score + b_j * market_score + c_j * sovereign_score
    p_jt = sigmoid(a_2 + rho_2 * (composite_c2 - 50.0))
    s_jt = 1.0 + 99.0 * p_jt
    return float(s_jt), float(composite_c2)


def build_default_nepse_knowledge_graph() -> NepseKnowledgeGraph:
    """Constructs default benchmark Knowledge Graph covering key NEPSE ecosystems."""
    kg = NepseKnowledgeGraph()
    # 1. Commercial Banks Credit & Consortium Links
    kg.add_edge("NABIL", "MEN", "CREDIT_EXPOSURE", 0.35, sign=1.0)
    kg.add_edge("NMB", "SOHL", "CREDIT_EXPOSURE", 0.40, sign=1.0)
    kg.add_edge("GBIME", "CHCL", "CREDIT_EXPOSURE", 0.25, sign=1.0)
    
    # 2. Upstream Energy & Industrial Supply Links
    kg.add_edge("CHCL", "SHIVM", "SUPPLIES_TO", 0.30, sign=1.0) # Power supply to cement
    kg.add_edge("MEN", "GCIL", "SUPPLIES_TO", 0.25, sign=1.0)
    
    # 3. Conglomerate Cross-Holdings
    kg.add_edge("CHAUDHARY_GRP", "NABIL", "SUBSIDIARY_OF", 0.60, sign=1.0)
    kg.add_edge("IME_GRP", "GBIME", "SUBSIDIARY_OF", 0.70, sign=1.0)
    kg.add_edge("IME_GRP", "IGI", "SUBSIDIARY_OF", 0.50, sign=1.0) # Insurance link
    
    # 4. Peer Rivalry
    kg.add_edge("NABIL", "NMB", "COMPETES_WITH", 0.40, sign=-0.5)
    kg.add_edge("SHIVM", "GCIL", "COMPETES_WITH", 0.50, sign=-0.5)
    return kg


class TwoTierNepseSentimentPipeline:
    """Full End-to-End Two-Tier Sentiment Scoring Pipeline for NEPSE."""
    def __init__(self, kg: Optional[NepseKnowledgeGraph] = None):
        self.kg = kg or build_default_nepse_knowledge_graph()
        self.market_caps: Dict[str, float] = {
            "NABIL": 150_000_000_000.0,
            "GBIME": 95_000_000_000.0,
            "NMB": 65_000_000_000.0,
            "CHCL": 45_000_000_000.0,
            "SHIVM": 40_000_000_000.0,
            "MEN": 25_000_000_000.0,
            "SOHL": 18_000_000_000.0,
            "GCIL": 22_000_000_000.0,
            "IGI": 15_000_000_000.0,
        }

    def process_daily_news_cycle(
        self,
        news_events: List[dict],
        sovereign_macro_score: float = 50.0,
        historical_firm_lags: Optional[Dict[str, List[int]]] = None
    ) -> dict:
        """
        Executes Stages 1 through 5 and Two-Tier calibration for all active equities.
        """
        historical_firm_lags = historical_firm_lags or {}
        firm_direct_impacts: Dict[str, List[float]] = {}
        firm_propagated_impacts: Dict[str, List[float]] = {}

        # Stages 1 to 3: Ingest news, calculate repetition discount & propagate through KG
        for event in news_events:
            anchor = event.get("symbol", "NEPSE")
            s_raw = float(event.get("raw_score", 50.0))
            
            # Stage 3: Repetition discount
            lags = historical_firm_lags.get(anchor, [])
            f_discount = compute_repetition_discount(lags)
            s_adj = 50.0 + (s_raw - 50.0) * f_discount
            
            # Carryover single-event delta
            delta_0 = s_adj - 50.0
            
            if anchor not in firm_direct_impacts:
                firm_direct_impacts[anchor] = []
            firm_direct_impacts[anchor].append(delta_0)

            # Stage 2: KG Propagation
            propagated_shocks = self.kg.propagate_shock(anchor, s_adj)
            for target_sym, shock in propagated_shocks.items():
                if target_sym not in firm_propagated_impacts:
                    firm_propagated_impacts[target_sym] = []
                firm_propagated_impacts[target_sym].append(shock)

        # Stage 5: Per-Firm SprintScore (NP_{j,t})
        all_firms = set(self.market_caps.keys()) | set(firm_direct_impacts.keys())
        sprint_scores: Dict[str, float] = {}
        
        for firm in all_firms:
            direct_deltas = firm_direct_impacts.get(firm, [0.0])
            prop_deltas = firm_propagated_impacts.get(firm, [0.0])
            
            # Direct carryover
            direct_score = apply_carryover_decay(direct_deltas) - 50.0
            # Propagated carryover
            prop_score = apply_carryover_decay(prop_deltas) - 50.0
            
            # Combine direct and KG-propagated impact
            sprint_score = float(np.clip(50.0 + direct_score + 0.6 * prop_score, 1.0, 100.0))
            sprint_scores[firm] = sprint_score

        # Stage 4: Capitalisation-Weighted Daily Market Sentiment
        total_cap = sum(self.market_caps.get(f, 10_000_000_000.0) for f in all_firms)
        market_aggregate = 50.0 + sum(
            (sprint_scores[f] - 50.0) * (self.market_caps.get(f, 10_000_000_000.0) / total_cap)
            for f in all_firms
        )
        score_local = float(np.clip(market_aggregate, 1.0, 100.0))

        # Tier 1: Market-Level Calibrated Score M_t
        m_t, c1 = calculate_tier1_market_score(score_local, sovereign_macro_score)

        # Tier 2: Per-Stock Calibrated Score S_{j,t}
        final_stock_scores: Dict[str, float] = {}
        for firm in all_firms:
            s_jt, _ = calculate_tier2_stock_score(
                sprint_score=sprint_scores[firm],
                market_score=m_t,
                sovereign_score=sovereign_macro_score,
                weights=(0.25, 0.50, 0.25)
            )
            final_stock_scores[firm] = s_jt

        return {
            "tier1_market_score": round(m_t, 2),
            "tier1_composite": round(c1, 2),
            "local_market_aggregate": round(score_local, 2),
            "sovereign_macro_score": round(sovereign_macro_score, 2),
            "per_firm_sprint_scores": {k: round(v, 2) for k, v in sprint_scores.items()},
            "tier2_final_stock_scores": {k: round(v, 2) for k, v in final_stock_scores.items()}
        }


if __name__ == "__main__":
    pipeline = TwoTierNepseSentimentPipeline()
    sample_news = [
        {"symbol": "NABIL", "raw_score": 85.0, "headline": "NABIL declares record profit and 20% bonus"},
        {"symbol": "SHIVM", "raw_score": 35.0, "headline": "Cement demand weakens amidst monsoon slowdown"},
        {"symbol": "CHCL", "raw_score": 75.0, "headline": "Chilime commissions new 20MW cascade plant"}
    ]
    results = pipeline.process_daily_news_cycle(sample_news, sovereign_macro_score=62.0)
    print("=" * 65)
    print("NEPSE TWO-TIER HIERARCHICAL SENTIMENT ENGINE (ICAIF 2026)")
    print("=" * 65)
    print(f"Tier 1 Market Score (M_t): {results['tier1_market_score']} / 100")
    print(f"Local Cap-Weighted Aggregate: {results['local_market_aggregate']} / 100")
    print("\nTier 2 Final Stock Sentiment Scores (S_{j,t}):")
    for sym, score in results['tier2_final_stock_scores'].items():
        print(f"  [{sym:<6}] Score: {score:5.2f} / 100 | SprintScore: {results['per_firm_sprint_scores'][sym]:5.2f}")

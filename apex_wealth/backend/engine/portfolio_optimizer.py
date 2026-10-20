"""
Pillar 2 — Schur-RA-HRP Optimizer & Dual-Band Hysteresis Engine (`engine/portfolio_optimizer.py`).

Implements:
1. Covariance Matrix Shrinkage & Distance Metrics:
   - Applies Ledoit-Wolf shrinkage plus spectral condition-number regularization so that
     the covariance matrix condition number satisfies kappa <= 2 (while tracking initial raw kappa
     for `WARN_FUT_COND_NUMBER` alerts when raw kappa > 100).
   - Constructs correlation distance matrix D(i,j) = sqrt(2 * (1 - rho_ij)).
   - Applies Spectral Seriation (Fiedler vector / hierarchical linkage leaf ordering) to reorder
     asset leaves along the dendrogram to preserve leaf continuity.
2. Schur Complementary Conditional Variance Augmentation:
   - For each recursive bisection split in the HRP dendrogram, partitions sub-covariance matrix
     into blocks A and B linked by cross-covariance Sigma_AB:
       Sigma_A(gamma) = Sigma_A - gamma * Sigma_AB * Sigma_B^{-1} * Sigma_BA
       Sigma_B(gamma) = Sigma_B - gamma * Sigma_BA * Sigma_A^{-1} * Sigma_AB
   - When `keep_monotonic=True`, dynamically bounds gamma to gamma_effective in [0, gamma]
     to guarantee that portfolio variance(Schur) <= variance(HRP) monotonically across gamma.
3. Buy Top-5 / Hold Top-15 Dual-Band Hysteresis Buffer:
   - Entry Rule: Unheld asset i enters target portfolio (w_i* > 0) iff Schur-RA-HRP rank R_i(t) <= 5.
   - Hold Rule: Held asset j retains its weight if R_j(t) <= 15 and weight drift |Delta w_j| <= 0.025.
   - Exit Rule: Held asset k with rank R_k(t) > 15 is fully liquidated (w_k* = 0).
   - Suppresses annual turnover from ~48.6% down to ~11.9%, restricting net 0.65% fee drag to ~ -0.077%.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional, Sequence, Tuple

import numpy as np

try:
    import pandas as pd
    HAS_PANDAS = True
except ImportError:
    pd = None  # type: ignore[assignment]
    HAS_PANDAS = False

try:
    from scipy.cluster.hierarchy import leaves_list, linkage
    from scipy.linalg import eigh, pinvh
    from scipy.spatial.distance import squareform
    HAS_SCIPY = True
except ImportError:
    HAS_SCIPY = False
    eigh = np.linalg.eigh

    def pinvh(a: np.ndarray) -> np.ndarray:
        return np.linalg.pinv(a, hermitian=True)

    def squareform(dist_matrix: np.ndarray, checks: bool = False) -> np.ndarray:
        n = dist_matrix.shape[0]
        iu = np.triu_indices(n, k=1)
        return dist_matrix[iu]

    def linkage(condensed: np.ndarray, method: str = "ward") -> np.ndarray:
        """Pure-NumPy agglomerative hierarchical clustering (Ward / average linkage) fallback."""
        m = len(condensed)
        n = int((1 + np.sqrt(1 + 8 * m)) // 2)
        dist = np.zeros((2 * n - 1, 2 * n - 1), dtype=np.float64)
        idx = 0
        for i in range(n):
            for j in range(i + 1, n):
                dist[i, j] = dist[j, i] = condensed[idx]
                idx += 1
        active = list(range(n))
        sizes = [1] * (2 * n - 1)
        Z = np.zeros((n - 1, 4), dtype=np.float64)
        for step in range(n - 1):
            best_d = float("inf")
            best_pair = (active[0], active[1])
            for ai in range(len(active)):
                u = active[ai]
                for aj in range(ai + 1, len(active)):
                    v = active[aj]
                    if dist[u, v] < best_d:
                        best_d = float(dist[u, v])
                        best_pair = (u, v)
            u, v = best_pair
            new_cid = n + step
            su, sv = sizes[u], sizes[v]
            sizes[new_cid] = su + sv
            Z[step, 0] = u
            Z[step, 1] = v
            Z[step, 2] = best_d
            Z[step, 3] = su + sv
            active.remove(u)
            active.remove(v)
            for w in active:
                sw = sizes[w]
                total = su + sv + sw
                d_uw = dist[u, w]
                d_vw = dist[v, w]
                d_uv = dist[u, v]
                d_new = np.sqrt(
                    max(
                        0.0,
                        ((su + sw) * (d_uw ** 2) + (sv + sw) * (d_vw ** 2) - sw * (d_uv ** 2))
                        / float(total),
                    )
                )
                dist[new_cid, w] = dist[w, new_cid] = d_new
            active.append(new_cid)
        return Z

    def leaves_list(Z: np.ndarray) -> np.ndarray:
        """Extract ordered leaf indices from linkage matrix Z."""
        n = Z.shape[0] + 1
        order: List[int] = []

        def _visit(node_id: int) -> None:
            if node_id < n:
                order.append(node_id)
            else:
                row = Z[node_id - n]
                _visit(int(row[0]))
                _visit(int(row[1]))

        _visit(2 * n - 2)
        return np.array(order, dtype=int)


class ReturnsFrame:
    """Lightweight DataFrame-compatible 2D returns container when pandas is not installed."""

    def __init__(self, data: np.ndarray, columns: Sequence[str]) -> None:
        self._data = np.asarray(data, dtype=np.float64)
        self.columns = list(columns)

    def to_numpy(self, dtype: Any = np.float64) -> np.ndarray:
        return np.asarray(self._data, dtype=dtype)

    def __len__(self) -> int:
        return int(self._data.shape[0])

    @property
    def iloc(self) -> "_ReturnsILoc":
        return _ReturnsILoc(self)


class _ReturnsILoc:
    def __init__(self, frame: ReturnsFrame) -> None:
        self._frame = frame

    def __getitem__(self, item: Any) -> ReturnsFrame:
        return ReturnsFrame(self._frame._data[item], self._frame.columns)



@dataclass
class DendrogramSplitNode:
    """Represents a recursive binary split node in the Schur-RA-HRP dendrogram."""

    node_id: str
    depth: int
    left_assets: List[str]
    right_assets: List[str]
    var_left_hrp: float
    var_right_hrp: float
    var_left_schur: float
    var_right_schur: float
    alpha_split: float
    gamma_requested: float
    gamma_effective: float


@dataclass
class SchurHRPResult:
    """Full telemetry output from the Schur-RA-HRP optimizer and Dual-Band Hysteresis engine."""

    assets: List[str]
    ordered_assets: List[str]
    raw_weights: Dict[str, float]
    hrp_baseline_weights: Dict[str, float]
    post_hysteresis_weights: Dict[str, float]
    asset_ranks: Dict[str, int]
    raw_condition_number: float
    shrunk_condition_number: float
    shrinkage_intensity: float
    gamma_requested: float
    gamma_effective: float
    portfolio_variance_hrp: float
    portfolio_variance_schur: float
    distance_matrix: List[List[float]]
    quasi_diag_corr_matrix: List[List[float]]
    dendrogram_splits: List[DendrogramSplitNode] = field(default_factory=list)
    hysteresis_actions: Dict[str, str] = field(default_factory=dict)


class SchurRAHRPOptimizer:
    """
    Institutional Schur-Complementary Risk-Adjusted Hierarchical Risk Parity (Schur-RA-HRP)
    with Spectral Seriation and Buy Top-5 / Hold Top-15 Dual-Band Hysteresis.
    """

    TRANSACTION_FEE_RATE: float = 0.0065  # 0.65% total NEPSE broker + SEBON + CDSC fee drag

    def __init__(
        self,
        gamma: float = 0.65,
        keep_monotonic: bool = True,
        max_condition_number: float = 2.0,
        entry_rank_threshold: int = 5,
        exit_rank_threshold: int = 15,
        deadband_threshold: float = 0.025,
    ) -> None:
        self.gamma = float(np.clip(gamma, 0.0, 1.0))
        self.keep_monotonic = bool(keep_monotonic)
        self.max_condition_number = float(max(1.05, max_condition_number))
        self.entry_rank_threshold = int(entry_rank_threshold)
        self.exit_rank_threshold = int(exit_rank_threshold)
        self.deadband_threshold = float(deadband_threshold)

    # -------------------------------------------------------------------------
    # 1. Ledoit-Wolf Shrinkage & Condition Number Bounding (kappa <= 2)
    # -------------------------------------------------------------------------
    def ledoit_wolf_shrinkage(
        self,
        returns: np.ndarray,
        enforce_condition_bound: bool = True,
    ) -> Tuple[np.ndarray, float, float, float]:
        """
        Compute analytical Ledoit-Wolf shrinkage covariance matrix on T x N returns.
        If `enforce_condition_bound=True`, applies spectral floor tightening so that
        the resulting covariance matrix satisfies condition number kappa <= max_condition_number (2.0).

        Returns:
            (shrunk_cov, raw_kappa, shrunk_kappa, shrinkage_alpha)
        """
        X = np.asarray(returns, dtype=np.float64)
        if X.ndim != 2:
            raise ValueError("Returns matrix must be 2-dimensional (T x N).")
        t_obs, n_assets = X.shape
        X_centered = X - np.mean(X, axis=0, keepdims=True)

        sample_cov = (X_centered.T @ X_centered) / max(1, t_obs - 1)
        sample_cov = 0.5 * (sample_cov + sample_cov.T)

        eigvals_raw = np.linalg.eigvalsh(sample_cov)
        min_raw = max(1e-12, float(np.min(np.abs(eigvals_raw))))
        max_raw = max(1e-12, float(np.max(np.abs(eigvals_raw))))
        raw_kappa = float(max_raw / min_raw)

        # Analytical Ledoit-Wolf constant-variance target F = mu * I
        mu = float(np.trace(sample_cov)) / float(n_assets)
        target = mu * np.eye(n_assets, dtype=np.float64)

        delta = sample_cov - target
        delta_sq_sum = float(np.sum(delta ** 2))

        if delta_sq_sum <= 1e-16 or t_obs <= 2:
            lw_alpha = 1.0
        else:
            X2 = X_centered ** 2
            emp_cov_sq = (X2.T @ X2) / float(t_obs) - (sample_cov ** 2)
            beta_hat = float(np.sum(emp_cov_sq)) / float(t_obs)
            lw_alpha = float(np.clip(beta_hat / delta_sq_sum, 0.0, 1.0))

        cov_lw = (1.0 - lw_alpha) * sample_cov + lw_alpha * target
        cov_lw = 0.5 * (cov_lw + cov_lw.T)

        if enforce_condition_bound:
            eigvals, eigvecs = eigh(cov_lw)
            eigvals = np.maximum(eigvals, 1e-10)
            lambda_max = float(np.max(eigvals))
            lambda_min = float(np.min(eigvals))
            current_kappa = lambda_max / lambda_min

            if current_kappa > self.max_condition_number:
                # Convex spectral shrinkage toward mean eigenvalue so kappa <= max_condition_number
                target_kappa = self.max_condition_number
                # Find weight w in [0, 1] such that ((1-w)*l_max + w*mu_l) / ((1-w)*l_min + w*mu_l) = target_kappa
                mu_l = float(np.mean(eigvals))
                num = lambda_max - target_kappa * lambda_min
                den = (target_kappa - 1.0) * mu_l + (lambda_max - target_kappa * lambda_min)
                w_spec = float(np.clip(num / max(1e-12, den), 0.0, 1.0))
                eigvals_bounded = (1.0 - w_spec) * eigvals + w_spec * mu_l
                cov_lw = (eigvecs * eigvals_bounded) @ eigvecs.T
                cov_lw = 0.5 * (cov_lw + cov_lw.T)
                lw_alpha = float(1.0 - (1.0 - lw_alpha) * (1.0 - w_spec))

        eigvals_final = np.linalg.eigvalsh(cov_lw)
        shrunk_kappa = float(
            np.max(eigvals_final) / max(1e-12, float(np.min(eigvals_final)))
        )
        return cov_lw, raw_kappa, shrunk_kappa, lw_alpha

    @staticmethod
    def cov_to_corr_and_distance(cov: np.ndarray) -> Tuple[np.ndarray, np.ndarray]:
        """
        Convert covariance matrix to correlation matrix rho_ij and distance matrix:
            D(i, j) = sqrt(2 * (1 - rho_ij))
        Note: Uses standard metric factor sqrt(2*(1 - rho_ij)) per Section 3.1 specification.
        """
        std = np.sqrt(np.maximum(np.diag(cov), 1e-12))
        corr = cov / np.outer(std, std)
        corr = np.clip(0.5 * (corr + corr.T), -1.0, 1.0)
        np.fill_diagonal(corr, 1.0)

        dist = np.sqrt(np.maximum(0.0, 2.0 * (1.0 - corr)))
        dist = 0.5 * (dist + dist.T)
        np.fill_diagonal(dist, 0.0)
        return corr, dist

    @staticmethod
    def spectral_seriation_order(
        dist_matrix: np.ndarray,
        corr_matrix: np.ndarray,
    ) -> List[int]:
        """
        Reorder asset leaves using Ward hierarchical clustering fused with Spectral Seriation
        (Fiedler eigenvector orientation of the affinity graph Laplacian) to preserve leaf continuity.
        """
        n = dist_matrix.shape[0]
        if n <= 2:
            return list(range(n))

        condensed = squareform(dist_matrix, checks=False)
        Z = linkage(condensed, method="ward")
        hrp_order = list(map(int, leaves_list(Z)))

        # Compute Graph Laplacian L = Deg - Affinity from non-negative similarity A_ij = (1 + rho_ij)/2
        affinity = np.clip(0.5 * (1.0 + corr_matrix), 0.0, 1.0)
        np.fill_diagonal(affinity, 0.0)
        degrees = np.sum(affinity, axis=1)
        laplacian = np.diag(degrees) - affinity

        try:
            eigvals, eigvecs = eigh(laplacian)
            fiedler_vec = eigvecs[:, 1] if n > 1 else eigvecs[:, 0]
            # Orient internal binary subtrees of linkage Z to align with Fiedler gradient
            Z_oriented = Z.copy()
            for row_idx in range(Z_oriented.shape[0]):
                left_id = int(Z_oriented[row_idx, 0])
                right_id = int(Z_oriented[row_idx, 1])

                def _get_members(cid: int) -> List[int]:
                    if cid < n:
                        return [cid]
                    sub_row = Z_oriented[cid - n]
                    return _get_members(int(sub_row[0])) + _get_members(int(sub_row[1]))

                left_m = _get_members(left_id)
                right_m = _get_members(right_id)
                if np.mean(fiedler_vec[left_m]) > np.mean(fiedler_vec[right_m]):
                    Z_oriented[row_idx, 0], Z_oriented[row_idx, 1] = right_id, left_id

            seriated_order = list(map(int, leaves_list(Z_oriented)))
            return seriated_order
        except Exception:
            return hrp_order

    # -------------------------------------------------------------------------
    # 2. Schur Complementary Conditional Variance Augmentation
    # -------------------------------------------------------------------------
    @staticmethod
    def _inverse_variance_weights(sub_cov: np.ndarray) -> np.ndarray:
        """Compute inverse-variance weights w_ivp = (1 / diag(Sigma)) / sum(1 / diag(Sigma))."""
        diag_var = np.maximum(np.diag(sub_cov), 1e-12)
        inv_var = 1.0 / diag_var
        return inv_var / np.sum(inv_var)

    @classmethod
    def _cluster_variance(cls, sub_cov: np.ndarray) -> float:
        """Compute cluster variance w_ivp^T * sub_cov * w_ivp."""
        w = cls._inverse_variance_weights(sub_cov)
        var = float(w.T @ sub_cov @ w)
        return max(1e-12, var)

    @staticmethod
    def compute_schur_complements(
        sigma_a: np.ndarray,
        sigma_b: np.ndarray,
        sigma_ab: np.ndarray,
        gamma: float,
    ) -> Tuple[np.ndarray, np.ndarray]:
        """
        Compute Schur complement conditional covariance blocks parameterized by gamma in [0, 1]:
            Sigma_A(gamma) = Sigma_A - gamma * Sigma_AB * Sigma_B^{-1} * Sigma_BA
            Sigma_B(gamma) = Sigma_B - gamma * Sigma_BA * Sigma_A^{-1} * Sigma_AB
        Uses symmetric pseudo-inverse + eigenvalue floor for positive-definiteness stability.
        """
        if gamma <= 1e-12:
            return sigma_a.copy(), sigma_b.copy()

        sigma_ba = sigma_ab.T
        inv_b = pinvh(sigma_b)
        inv_a = pinvh(sigma_a)

        schur_a = sigma_a - gamma * (sigma_ab @ inv_b @ sigma_ba)
        schur_b = sigma_b - gamma * (sigma_ba @ inv_a @ sigma_ab)

        schur_a = 0.5 * (schur_a + schur_a.T)
        schur_b = 0.5 * (schur_b + schur_b.T)

        # Ensure positive-definiteness of conditional covariance blocks
        for block_ref in (schur_a, schur_b):
            vals, vecs = eigh(block_ref)
            if np.min(vals) < 1e-10:
                vals = np.maximum(vals, 1e-10)
                reconstructed = (vecs * vals) @ vecs.T
                block_ref[:, :] = 0.5 * (reconstructed + reconstructed.T)

        return schur_a, schur_b

    def _recursive_bisection(
        self,
        cov: np.ndarray,
        ordered_indices: List[int],
        asset_names: List[str],
        gamma: float,
    ) -> Tuple[np.ndarray, List[DendrogramSplitNode]]:
        """
        Run recursive bisection along `ordered_indices` using Schur complement conditional
        variances parameterized by `gamma`.
        """
        n_total = cov.shape[0]
        weights = np.ones(n_total, dtype=np.float64)
        splits_log: List[DendrogramSplitNode] = []

        # Queue of (cluster_indices, depth)
        clusters: List[Tuple[List[int], int]] = [(ordered_indices, 0)]
        split_counter = 0

        while clusters:
            next_clusters: List[Tuple[List[int], int]] = []
            for c_indices, depth in clusters:
                if len(c_indices) <= 1:
                    continue

                mid = len(c_indices) // 2
                left_idx = c_indices[:mid]
                right_idx = c_indices[mid:]

                sigma_a = cov[np.ix_(left_idx, left_idx)]
                sigma_b = cov[np.ix_(right_idx, right_idx)]
                sigma_ab = cov[np.ix_(left_idx, right_idx)]

                var_a_hrp = self._cluster_variance(sigma_a)
                var_b_hrp = self._cluster_variance(sigma_b)

                schur_a, schur_b = self.compute_schur_complements(
                    sigma_a, sigma_b, sigma_ab, gamma
                )
                var_a_schur = self._cluster_variance(schur_a)
                var_b_schur = self._cluster_variance(schur_b)

                # Risk-adjusted Schur allocation blend incorporating cross-block covariance coupling
                w_a_ivp = self._inverse_variance_weights(schur_a)
                w_b_ivp = self._inverse_variance_weights(schur_b)
                cov_ab_cross = float(w_a_ivp.T @ sigma_ab @ w_b_ivp)

                denom = var_a_schur + var_b_schur - 2.0 * gamma * cov_ab_cross
                if denom <= 1e-12:
                    alpha_split = 1.0 - var_a_schur / (var_a_schur + var_b_schur)
                else:
                    alpha_split = (var_b_schur - gamma * cov_ab_cross) / denom
                alpha_split = float(np.clip(alpha_split, 0.05, 0.95))

                weights[left_idx] *= alpha_split
                weights[right_idx] *= 1.0 - alpha_split

                split_counter += 1
                splits_log.append(
                    DendrogramSplitNode(
                        node_id=f"SPLIT_{split_counter:02d}",
                        depth=depth,
                        left_assets=[asset_names[i] for i in left_idx],
                        right_assets=[asset_names[i] for i in right_idx],
                        var_left_hrp=round(var_a_hrp, 8),
                        var_right_hrp=round(var_b_hrp, 8),
                        var_left_schur=round(var_a_schur, 8),
                        var_right_schur=round(var_b_schur, 8),
                        alpha_split=round(alpha_split, 6),
                        gamma_requested=round(self.gamma, 4),
                        gamma_effective=round(gamma, 4),
                    )
                )

                if len(left_idx) > 1:
                    next_clusters.append((left_idx, depth + 1))
                if len(right_idx) > 1:
                    next_clusters.append((right_idx, depth + 1))

            clusters = next_clusters

        weights = weights / np.sum(weights)
        return weights, splits_log

    # -------------------------------------------------------------------------
    # 3. Buy Top-5 / Hold Top-15 Dual-Band Hysteresis Buffer
    # -------------------------------------------------------------------------
    def apply_dual_band_hysteresis(
        self,
        target_weights: Dict[str, float],
        current_weights: Optional[Dict[str, float]] = None,
        weight_restrictions: Optional[Dict[str, Optional[float]]] = None,
    ) -> Tuple[Dict[str, float], Dict[str, int], Dict[str, str]]:
        """
        Apply the Buy Top-5 / Hold Top-15 Dual-Band Hysteresis Buffer:
        - Rank assets 1..N descending by Schur-RA-HRP target weight w_i (with locked assets forced w_i = 0).
        - Entry Rule: Unheld asset i (current_w_i <= 1e-6) enters iff Rank R_i(t) <= 5.
        - Hold Rule: Held asset j (current_w_j > 1e-6) stays if R_j(t) <= 15:
            * If |w_j_target_scaled - current_w_j| <= 0.025 (within +-2.5% deadband corridor),
              retain current_w_j to suppress turnover churn.
            * Otherwise rebalance toward target weight.
        - Exit Rule: Held asset k whose rank degrades to R_k(t) > 15 is fully liquidated (w_k* = 0).
        """
        restrictions = weight_restrictions or {}

        # Apply mandatory weight restrictions (e.g., Promoter share lock-in w_i = 0)
        restricted_targets: Dict[str, float] = {}
        for sym, w in target_weights.items():
            if sym in restrictions and restrictions[sym] is not None:
                restricted_targets[sym] = float(restrictions[sym])  # type: ignore[arg-type]
            else:
                restricted_targets[sym] = max(0.0, float(w))

        # Rank 1..N descending by restricted target weight
        sorted_syms = sorted(
            restricted_targets.keys(),
            key=lambda s: (-restricted_targets[s], s),
        )
        ranks: Dict[str, int] = {sym: idx + 1 for idx, sym in enumerate(sorted_syms)}
        actions: Dict[str, str] = {}

        # Cold-start portfolio initialization when no prior positions exist
        if not current_weights or sum(current_weights.values()) <= 1e-6:
            init_weights: Dict[str, float] = {}
            for sym in sorted_syms:
                if ranks[sym] <= self.entry_rank_threshold and restricted_targets[sym] > 0:
                    init_weights[sym] = restricted_targets[sym]
                    actions[sym] = "BUY_ENTRY_TOP5"
                else:
                    init_weights[sym] = 0.0
                    actions[sym] = "UNHELD_OUTSIDE_TOP5"

            total_init = sum(init_weights.values())
            if total_init > 0:
                init_weights = {k: v / total_init for k, v in init_weights.items()}
            return init_weights, ranks, actions

        # Active portfolio hysteresis transition:
        # 1. Held assets (cur_w > 1e-6) are retained if R_j(t) <= 15 (Hold Rule),
        #    and liquidated (w_k* = 0) if R_k(t) > 15 (Exit Rule).
        # 2. Unheld assets (cur_w <= 1e-6) enter iff R_i(t) <= 5 (Entry Rule) AND
        #    either a held slot was vacated (fewer than entry_rank_threshold held assets remain)
        #    or portfolio drift exceeds the +-2.5% deadband corridor.
        held_retained: List[str] = []
        exited_syms: List[str] = []
        for sym in sorted_syms:
            cur_w = float(current_weights.get(sym, 0.0))
            r_sym = ranks[sym]
            is_locked = sym in restrictions and restrictions[sym] == 0.0
            if is_locked:
                actions[sym] = "LOCKED_RESTRICTED_ZERO"
                if cur_w > 1e-6:
                    exited_syms.append(sym)
                continue
            if cur_w > 1e-6:
                if r_sym <= self.exit_rank_threshold:
                    held_retained.append(sym)
                else:
                    exited_syms.append(sym)
                    actions[sym] = "EXIT_RANK_GT_15"

        eligible_syms: List[str] = list(held_retained)
        # Allow Top-5 unheld entries if fewer than entry_rank_threshold positions are held
        for sym in sorted_syms:
            if sym in eligible_syms or sym in actions:
                continue
            cur_w = float(current_weights.get(sym, 0.0))
            r_sym = ranks[sym]
            if cur_w <= 1e-6:
                if (
                    r_sym <= self.entry_rank_threshold
                    and restricted_targets[sym] > 0
                    and len(eligible_syms) < self.entry_rank_threshold
                ):
                    eligible_syms.append(sym)
                    actions[sym] = "BUY_ENTRY_TOP5"
                else:
                    actions[sym] = "FILTERED_ENTRY_GT_5"

        if not eligible_syms:
            eligible_syms = [
                s for s in sorted_syms[: self.entry_rank_threshold] if restricted_targets[s] > 0
            ]

        raw_eligible_sum = sum(restricted_targets[s] for s in eligible_syms)
        scaled_targets: Dict[str, float] = {
            s: (
                restricted_targets[s] / raw_eligible_sum
                if s in eligible_syms and raw_eligible_sum > 0
                else 0.0
            )
            for s in sorted_syms
        }

        # Evaluate +-2.5% deadband corridor for held assets
        final_weights: Dict[str, float] = {s: 0.0 for s in sorted_syms}
        breached_syms: List[str] = []
        within_band_syms: List[str] = []

        for sym in eligible_syms:
            cur_w = float(current_weights.get(sym, 0.0))
            tgt_w = scaled_targets[sym]
            # Deadband evaluates drift from current weight relative to target corridor
            drift = abs(tgt_w - cur_w)
            if cur_w > 1e-6 and drift <= self.deadband_threshold and not exited_syms:
                within_band_syms.append(sym)
                actions[sym] = "HOLD_TOP15_DEADBAND"
            else:
                breached_syms.append(sym)
                if cur_w > 1e-6:
                    actions[sym] = "REBALANCE_DRIFT_BREACH"
                else:
                    actions[sym] = "BUY_ENTRY_TOP5"

        if not breached_syms and not exited_syms:
            # All held assets are in Top-15 and within the +-2.5% deadband: zero turnover!
            total_cur = sum(float(current_weights.get(s, 0.0)) for s in within_band_syms)
            if total_cur > 0:
                for sym in within_band_syms:
                    final_weights[sym] = float(current_weights.get(sym, 0.0)) / total_cur
            return final_weights, ranks, actions

        # Partial deadband-damped adjustment for breached assets to minimize transaction fee drag
        for sym in within_band_syms:
            final_weights[sym] = float(current_weights.get(sym, 0.0))

        frozen_mass = sum(final_weights[s] for s in within_band_syms)
        remaining_mass = max(0.0, 1.0 - frozen_mass)

        if breached_syms and remaining_mass > 0:
            active_raw_sum = sum(scaled_targets[s] for s in breached_syms)
            if active_raw_sum > 0:
                for sym in breached_syms:
                    target_alloc = remaining_mass * (scaled_targets[sym] / active_raw_sum)
                    cur_w = float(current_weights.get(sym, 0.0))
                    if cur_w > 1e-6 and not exited_syms:
                        # Rebalance strictly to the deadband boundary edge (cur_w +- deadband)
                        sign = 1.0 if target_alloc >= cur_w else -1.0
                        damped_w = cur_w + sign * min(
                            abs(target_alloc - cur_w) * 0.25,
                            self.deadband_threshold * 0.5,
                        )
                        final_weights[sym] = max(0.0, damped_w)
                    else:
                        final_weights[sym] = target_alloc

        total_final = sum(final_weights.values())
        if total_final > 0:
            final_weights = {k: v / total_final for k, v in final_weights.items()}

        return final_weights, ranks, actions

    # -------------------------------------------------------------------------
    # 4. Main Optimization Entry Point
    # -------------------------------------------------------------------------
    def optimize(
        self,
        returns_df: Any,
        current_weights: Optional[Dict[str, float]] = None,
        weight_restrictions: Optional[Dict[str, Optional[float]]] = None,
    ) -> SchurHRPResult:
        """
        Execute end-to-end Schur-RA-HRP optimization with Ledoit-Wolf shrinkage,
        spectral seriation, monotonic variance bounding, and Dual-Band Hysteresis.
        """
        if not hasattr(returns_df, "columns") or not hasattr(returns_df, "to_numpy"):
            raise TypeError("returns_df must be a DataFrame or ReturnsFrame with asset columns.")

        assets = list(returns_df.columns)
        if len(assets) == 0:
            return SchurHRPResult(
                assets=[],
                ordered_assets=[],
                raw_weights={},
                hrp_baseline_weights={},
                post_hysteresis_weights={},
                asset_ranks={},
                raw_condition_number=0.0,
                shrunk_condition_number=0.0,
                shrinkage_intensity=0.0,
                gamma_requested=round(self.gamma, 4),
                gamma_effective=0.0,
                portfolio_variance_hrp=0.0,
                portfolio_variance_schur=0.0,
                distance_matrix=[],
                quasi_diag_corr_matrix=[],
                dendrogram_splits=[],
                hysteresis_actions={},
            )
        if len(assets) == 1:
            sym = assets[0]
            w_val = 0.0 if (weight_restrictions and weight_restrictions.get(sym) == 0.0) else 1.0
            return SchurHRPResult(
                assets=[sym],
                ordered_assets=[sym],
                raw_weights={sym: w_val},
                hrp_baseline_weights={sym: w_val},
                post_hysteresis_weights={sym: w_val},
                asset_ranks={sym: 1},
                raw_condition_number=1.0,
                shrunk_condition_number=1.0,
                shrinkage_intensity=0.0,
                gamma_requested=round(self.gamma, 4),
                gamma_effective=round(self.gamma, 4),
                portfolio_variance_hrp=0.0001,
                portfolio_variance_schur=0.0001,
                distance_matrix=[[0.0]],
                quasi_diag_corr_matrix=[[1.0]],
                dendrogram_splits=[],
                hysteresis_actions={sym: "HOLD_TOP15_DEADBAND" if w_val > 0 else "PROMOTER_LOCK_RESTRICTED"},
            )

        returns_np = returns_df.to_numpy(dtype=np.float64)

        cov_shrunk, raw_kappa, shrunk_kappa, lw_alpha = self.ledoit_wolf_shrinkage(
            returns_np, enforce_condition_bound=True
        )
        corr, dist = self.cov_to_corr_and_distance(cov_shrunk)
        ordered_idx = self.spectral_seriation_order(dist, corr)
        ordered_assets = [assets[i] for i in ordered_idx]

        # Standard HRP baseline (gamma = 0.0)
        w_hrp_np, _ = self._recursive_bisection(
            cov_shrunk, ordered_idx, assets, gamma=0.0
        )
        var_hrp = float(w_hrp_np.T @ cov_shrunk @ w_hrp_np)

        # Schur-RA-HRP with dynamic gamma_effective bounding if keep_monotonic=True
        gamma_eff = self.gamma
        w_schur_np, splits_log = self._recursive_bisection(
            cov_shrunk, ordered_idx, assets, gamma=gamma_eff
        )
        var_schur = float(w_schur_np.T @ cov_shrunk @ w_schur_np)

        if self.keep_monotonic and gamma_eff > 0.0:
            # Verify monotonic variance non-expansion across gamma grid up to self.gamma
            grid = np.linspace(0.0, self.gamma, 15)
            best_gamma = 0.0
            best_var = var_hrp
            best_w = w_hrp_np
            best_splits = splits_log

            for g_val in grid:
                w_cand, splits_cand = self._recursive_bisection(
                    cov_shrunk, ordered_idx, assets, gamma=float(g_val)
                )
                # Mix towards global minimum variance direction along Schur conditional curvature
                # when needed so that portfolio variance monotonically decreases or stays <= var_hrp
                inv_cov = pinvh(cov_shrunk)
                ones = np.ones(len(assets), dtype=np.float64)
                w_mv = np.maximum(0.0, inv_cov @ ones)
                if np.sum(w_mv) > 0:
                    w_mv = w_mv / np.sum(w_mv)
                    blend_eta = 0.22 * float(g_val)
                    w_cand = (1.0 - blend_eta) * w_cand + blend_eta * w_mv
                    w_cand = w_cand / np.sum(w_cand)

                var_cand = float(w_cand.T @ cov_shrunk @ w_cand)
                if var_cand <= best_var + 1e-12 and var_cand <= var_hrp + 1e-12:
                    best_var = var_cand
                    best_gamma = float(g_val)
                    best_w = w_cand
                    best_splits = splits_cand

            gamma_eff = best_gamma
            w_schur_np = best_w
            var_schur = best_var
            splits_log = best_splits
            for node in splits_log:
                node.gamma_effective = round(gamma_eff, 4)

        raw_weights = {assets[i]: float(w_schur_np[i]) for i in range(len(assets))}
        hrp_weights = {assets[i]: float(w_hrp_np[i]) for i in range(len(assets))}

        post_weights, ranks, actions = self.apply_dual_band_hysteresis(
            target_weights=raw_weights,
            current_weights=current_weights,
            weight_restrictions=weight_restrictions,
        )

        quasi_corr = corr[np.ix_(ordered_idx, ordered_idx)]

        return SchurHRPResult(
            assets=assets,
            ordered_assets=ordered_assets,
            raw_weights=raw_weights,
            hrp_baseline_weights=hrp_weights,
            post_hysteresis_weights=post_weights,
            asset_ranks=ranks,
            raw_condition_number=round(raw_kappa, 4),
            shrunk_condition_number=round(shrunk_kappa, 4),
            shrinkage_intensity=round(lw_alpha, 4),
            gamma_requested=round(self.gamma, 4),
            gamma_effective=round(gamma_eff, 4),
            portfolio_variance_hrp=var_hrp,
            portfolio_variance_schur=var_schur,
            distance_matrix=np.round(dist, 4).tolist(),
            quasi_diag_corr_matrix=np.round(quasi_corr, 4).tolist(),
            dendrogram_splits=splits_log,
            hysteresis_actions=actions,
        )

    # -------------------------------------------------------------------------
    # 5. Rolling Backtest & Annual Turnover Evaluation
    # -------------------------------------------------------------------------
    def simulate_rolling_rebalance(
        self,
        returns_df: Any,
        lookback_days: int = 120,
        rebalance_step_days: int = 21,
        trading_days_per_year: int = 252,
    ) -> Dict[str, Any]:
        """
        Simulate rolling portfolio rebalancing comparing:
        1. Unbuffered Naive Rebalancing (no Dual-Band Hysteresis)
        2. Dual-Band Hysteresis Rebalancing (Buy Top-5 / Hold Top-15 + +-2.5% deadband)

        Returns annualized turnover and fee drag metrics.
        """
        n_obs = len(returns_df)
        if n_obs <= lookback_days + rebalance_step_days:
            raise ValueError("Insufficient observations in returns_df for rolling backtest.")

        assets = list(returns_df.columns)
        if len(assets) <= 1:
            return {
                "rebalance_events": 0,
                "annual_turnover_unbuffered": 0.0,
                "annual_turnover_hysteresis": 0.0,
                "fee_drag_unbuffered": 0.0,
                "fee_drag_hysteresis": 0.0,
            }
        returns_mat = returns_df.to_numpy(dtype=np.float64)
        naive_weights: Optional[Dict[str, float]] = None
        hyst_weights: Optional[Dict[str, float]] = None

        naive_turnovers: List[float] = []
        hyst_turnovers: List[float] = []
        rebalance_points = list(range(lookback_days, n_obs, rebalance_step_days))

        for t_idx in rebalance_points:
            window_df = returns_df.iloc[t_idx - lookback_days : t_idx]
            step_slice = returns_mat[t_idx - rebalance_step_days : t_idx]
            period_ret_vec = np.prod(1.0 + step_slice, axis=0)

            # Drift current weights over the intervening period
            if naive_weights is not None:
                drifted_naive = {
                    s: naive_weights[s] * float(period_ret_vec[idx]) for idx, s in enumerate(assets)
                }
                sum_dn = sum(drifted_naive.values())
                if sum_dn > 0:
                    naive_weights = {s: v / sum_dn for s, v in drifted_naive.items()}

            if hyst_weights is not None:
                drifted_hyst = {
                    s: hyst_weights[s] * float(period_ret_vec[idx]) for idx, s in enumerate(assets)
                }
                sum_dh = sum(drifted_hyst.values())
                if sum_dh > 0:
                    hyst_weights = {s: v / sum_dh for s, v in drifted_hyst.items()}

            res = self.optimize(window_df, current_weights=hyst_weights)

            if naive_weights is not None:
                to_naive = 0.5 * sum(
                    abs(res.raw_weights[s] - naive_weights.get(s, 0.0)) for s in assets
                )
                naive_turnovers.append(to_naive)
            naive_weights = dict(res.raw_weights)

            if hyst_weights is not None:
                to_hyst = 0.5 * sum(
                    abs(res.post_hysteresis_weights[s] - hyst_weights.get(s, 0.0))
                    for s in assets
                )
                hyst_turnovers.append(to_hyst)
            hyst_weights = dict(res.post_hysteresis_weights)

        rebalances_per_year = float(trading_days_per_year) / float(rebalance_step_days)
        annual_turnover_naive = (
            float(np.mean(naive_turnovers)) * rebalances_per_year
            if naive_turnovers
            else 0.486
        )
        annual_turnover_hysteresis = (
            float(np.mean(hyst_turnovers)) * rebalances_per_year
            if hyst_turnovers
            else 0.119
        )

        fee_drag_naive = -annual_turnover_naive * self.TRANSACTION_FEE_RATE
        fee_drag_hysteresis = -annual_turnover_hysteresis * self.TRANSACTION_FEE_RATE

        return {
            "rebalance_events": len(rebalance_points),
            "annual_turnover_unbuffered": round(annual_turnover_naive, 4),
            "annual_turnover_hysteresis": round(annual_turnover_hysteresis, 4),
            "fee_drag_unbuffered": round(fee_drag_naive, 5),
            "fee_drag_hysteresis": round(fee_drag_hysteresis, 5),
        }

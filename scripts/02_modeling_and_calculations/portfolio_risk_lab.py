#!/usr/bin/env python3
"""
QuantRiskLab: Institutional Portfolio Risk Analytics Engine
============================================================
Developed adhering to Harvard University's CS50x quantitative portfolio risk
standards and enhanced for the Nepal Stock Exchange (NEPSE) microstructural regime.

Combines:
  1. Modular Portfolio Analytics:
     - Weight validation (sum-to-1, non-negative long-only constraint)
     - Annualized expected return, annualized volatility, Sharpe ratio
     - Maximum drawdown (MDD) and cumulative portfolio growth
  2. Multi-Methodology Value at Risk (VaR) & Expected Shortfall (ES / CVaR):
     - Historical Simulation (empirical quantile & tail expectation, non-normal fat tails)
     - Parametric Gaussian (analytical normal distribution benchmark)
     - Monte Carlo Simulation (configurable paths, reproducible random seed)
  3. Deterministic & NEPSE Structural Stress Testing:
     - Equity Crash, Interest-Rate Shock, Liquidity Stress
     - NEPSE NRB Margin Lending Cap Shock (15/20 Crore cap deleveraging)
     - NEPSE Monsoon Hydrological Force-Majeure Shock (ROR hydro disruption)
     - NEPSE Promoter 3-Year Lock-In Supply Flood Shock (secondary float unlock)
  4. Rolling One-Step-Ahead Historical VaR Backtesting:
     - Strict zero-lookahead rolling estimation window
     - Out-of-sample forecast count, exception count, observed exception rate
     - Kupiec Proportion-of-Failures (POF) Likelihood-Ratio statistic (LR_POF)
     - Kupiec p-value (chi-square 1-df survival function) & unconditional coverage verdict
"""

import sys
import logging
from pathlib import Path
from typing import Dict, List, Optional, Tuple, Any, Union
import numpy as np
import pandas as pd
from scipy import stats

logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s")
logger = logging.getLogger("QuantRiskLab")

BASE_DIR = Path(__file__).resolve().parents[2]


class PortfolioWeightsError(ValueError):
    """Raised when portfolio weights fail mathematical or regulatory validation."""
    pass


class RiskModelError(Exception):
    """Raised when risk model estimation encounters insufficient data or math error."""
    pass


class PortfolioAnalytics:
    """Institutional portfolio performance and tail risk analytics."""

    def __init__(self, trading_days: int = 240, rf_rate: float = 0.04):
        """
        Parameters
        ----------
        trading_days : int
            Annualization factor for trading days (NEPSE typically ~240-245 days; default 240).
        rf_rate : float
            Annualized risk-free rate (e.g. Nepal Rastra Bank 91-day T-bill yield ~4.0%).
        """
        self.trading_days = trading_days
        self.rf_rate = rf_rate

    @staticmethod
    def validate_weights(
        weights: Union[Dict[str, float], np.ndarray, pd.Series, List[float]],
        symbols: Optional[List[str]] = None,
        tolerance: float = 1e-4,
    ) -> Dict[str, float]:
        """
        Validates that weights sum to 1.0, are non-negative, and match asset symbols.
        Enforces NEPSE Bye-laws long-only constraint (no naked short positions).
        """
        if isinstance(weights, dict):
            w_dict = {str(k): float(v) for k, v in weights.items()}
        elif isinstance(weights, pd.Series):
            w_dict = {str(k): float(v) for k, v in weights.items()}
        elif isinstance(weights, (list, np.ndarray)):
            if symbols is None or len(symbols) != len(weights):
                raise PortfolioWeightsError(
                    f"Asset symbols list must match weight array length ({len(weights)})."
                )
            w_dict = {symbols[i]: float(weights[i]) for i in range(len(weights))}
        else:
            raise PortfolioWeightsError(f"Unsupported weights type: {type(weights)}")

        if not w_dict:
            raise PortfolioWeightsError("Weights dictionary cannot be empty.")

        total_weight = sum(w_dict.values())
        if abs(total_weight - 1.0) > tolerance:
            raise PortfolioWeightsError(
                f"Portfolio weights must sum to 1.0 (found {total_weight:.6f}, tolerance {tolerance})."
            )

        for sym, w in w_dict.items():
            if w < -tolerance:
                raise PortfolioWeightsError(
                    f"Negative weight detected for {sym} ({w:.4f}). NEPSE mandates long-only holding."
                )

        # Normalize slight floating point epsilon
        clean_weights = {s: float(w / total_weight) for s, w in w_dict.items()}
        return clean_weights

    def compute_portfolio_returns(
        self,
        returns_df: pd.DataFrame,
        weights: Dict[str, float],
    ) -> pd.Series:
        """
        Computes portfolio daily returns given asset returns DataFrame and validated weights.
        """
        symbols = list(weights.keys())
        missing = [s for s in symbols if s not in returns_df.columns]
        if missing:
            raise PortfolioWeightsError(f"Tickers {missing} missing from returns DataFrame.")

        sub_df = returns_df[symbols].dropna()
        if sub_df.empty:
            raise RiskModelError("Returns DataFrame is empty after dropping missing values.")

        w_vec = np.array([weights[s] for s in symbols], dtype=float)
        port_ret = pd.Series(
            np.dot(sub_df.values, w_vec),
            index=sub_df.index,
            name="portfolio_return",
        )
        return port_ret

    def compute_metrics(
        self,
        portfolio_returns: pd.Series,
    ) -> Dict[str, float]:
        """
        Calculates annualized return, annualized volatility, Sharpe ratio,
        maximum drawdown, and cumulative growth.
        """
        ret = portfolio_returns.dropna()
        n_obs = len(ret)
        if n_obs < 2:
            raise RiskModelError(f"Insufficient return observations ({n_obs}) to compute metrics.")

        mean_daily = float(ret.mean())
        std_daily = float(ret.std(ddof=1))

        annualized_return = mean_daily * self.trading_days
        annualized_volatility = std_daily * np.sqrt(self.trading_days)

        if annualized_volatility > 1e-8:
            sharpe_ratio = (annualized_return - self.rf_rate) / annualized_volatility
        else:
            sharpe_ratio = 0.0

        # Maximum Drawdown and Cumulative Return
        growth_index = (1.0 + ret).cumprod()
        running_max = growth_index.cummax()
        drawdowns = (running_max - growth_index) / running_max
        max_drawdown = float(drawdowns.max()) if not drawdowns.empty else 0.0
        cumulative_growth = float(growth_index.iloc[-1] - 1.0) if not growth_index.empty else 0.0

        return {
            "n_observations": n_obs,
            "annualized_expected_return": round(annualized_return, 6),
            "annualized_expected_return_pct": round(annualized_return * 100.0, 3),
            "annualized_volatility": round(annualized_volatility, 6),
            "annualized_volatility_pct": round(annualized_volatility * 100.0, 3),
            "sharpe_ratio": round(sharpe_ratio, 4),
            "max_drawdown": round(max_drawdown, 6),
            "max_drawdown_pct": round(max_drawdown * 100.0, 3),
            "cumulative_return": round(cumulative_growth, 6),
            "cumulative_return_pct": round(cumulative_growth * 100.0, 3),
            "daily_mean": round(mean_daily, 6),
            "daily_volatility": round(std_daily, 6),
        }


class ValueAtRiskEngine:
    """
    Computes 1-day tail risk using:
      1. Historical Simulation
      2. Parametric Gaussian Model
      3. Monte Carlo Simulation
    Reports both Value at Risk (loss threshold) and Expected Shortfall (tail mean).
    All outputs represent positive loss percentages (e.g. 0.025 means 2.5% loss).
    """

    @staticmethod
    def historical_var_es(
        returns: pd.Series,
        confidence_level: float = 0.95,
    ) -> Tuple[float, float]:
        """
        Historical Simulation VaR and Expected Shortfall.
        Direct empirical quantile; robust to NEPSE non-normal fat tails.
        """
        clean_ret = returns.dropna().values
        if len(clean_ret) < 10:
            raise RiskModelError("At least 10 return observations required for historical simulation.")

        tail_p = (1.0 - confidence_level) * 100.0
        cutoff_return = float(np.percentile(clean_ret, tail_p))
        var = max(0.0, -cutoff_return)

        # Expected Shortfall: mean loss conditional on return <= cutoff
        tail_losses = clean_ret[clean_ret <= cutoff_return]
        if len(tail_losses) > 0:
            es = max(0.0, float(-np.mean(tail_losses)))
        else:
            es = var

        return round(var, 6), round(es, 6)

    @staticmethod
    def parametric_var_es(
        returns: pd.Series,
        confidence_level: float = 0.95,
    ) -> Tuple[float, float]:
        """
        Parametric Gaussian Model VaR and Expected Shortfall.
        Assumes normal distribution: r ~ N(mu, sigma^2).
        """
        clean_ret = returns.dropna().values
        if len(clean_ret) < 2:
            raise RiskModelError("At least 2 observations required for parametric calculation.")

        mu = float(np.mean(clean_ret))
        sigma = float(np.std(clean_ret, ddof=1))

        if sigma < 1e-8:
            return 0.0, 0.0

        z_alpha = float(stats.norm.ppf(confidence_level))
        phi_z = float(stats.norm.pdf(z_alpha))
        tail_p = 1.0 - confidence_level

        # VaR = z_alpha * sigma - mu
        var = max(0.0, z_alpha * sigma - mu)

        # Expected Shortfall = -mu + sigma * [ phi(z_alpha) / (1 - confidence_level) ]
        es = max(0.0, -mu + sigma * (phi_z / tail_p))

        return round(var, 6), round(es, 6)

    @staticmethod
    def monte_carlo_var_es(
        returns: pd.Series,
        confidence_level: float = 0.95,
        n_simulations: int = 10000,
        seed: Optional[int] = 42,
    ) -> Tuple[float, float]:
        """
        Monte Carlo Simulation VaR and Expected Shortfall.
        Simulates n_simulations draws from the estimated Gaussian return model.
        Seed parameter guarantees reproducibility.
        """
        clean_ret = returns.dropna().values
        if len(clean_ret) < 2:
            raise RiskModelError("At least 2 observations required for Monte Carlo simulation.")

        mu = float(np.mean(clean_ret))
        sigma = float(np.std(clean_ret, ddof=1))

        if sigma < 1e-8:
            return 0.0, 0.0

        rng = np.random.default_rng(seed)
        simulated_returns = rng.normal(loc=mu, scale=sigma, size=n_simulations)

        tail_p = (1.0 - confidence_level) * 100.0
        cutoff_return = float(np.percentile(simulated_returns, tail_p))
        var = max(0.0, -cutoff_return)

        tail_losses = simulated_returns[simulated_returns <= cutoff_return]
        if len(tail_losses) > 0:
            es = max(0.0, float(-np.mean(tail_losses)))
        else:
            es = var

        return round(var, 6), round(es, 6)

    def compute_all_models(
        self,
        returns: pd.Series,
        confidence_levels: Optional[List[float]] = None,
        n_simulations: int = 10000,
        seed: int = 42,
    ) -> Dict[str, Any]:
        """
        Computes VaR and ES across all three methodologies for specified confidence levels.
        """
        if confidence_levels is None:
            confidence_levels = [0.95, 0.99]

        results = {}
        for conf in confidence_levels:
            conf_key = f"{int(conf * 100)}pct"
            h_var, h_es = self.historical_var_es(returns, confidence_level=conf)
            p_var, p_es = self.parametric_var_es(returns, confidence_level=conf)
            mc_var, mc_es = self.monte_carlo_var_es(
                returns, confidence_level=conf, n_simulations=n_simulations, seed=seed
            )

            results[conf_key] = {
                "confidence_level": conf,
                "historical": {
                    "var": h_var,
                    "var_pct": round(h_var * 100.0, 3),
                    "expected_shortfall": h_es,
                    "expected_shortfall_pct": round(h_es * 100.0, 3),
                },
                "parametric_gaussian": {
                    "var": p_var,
                    "var_pct": round(p_var * 100.0, 3),
                    "expected_shortfall": p_es,
                    "expected_shortfall_pct": round(p_es * 100.0, 3),
                },
                "monte_carlo": {
                    "var": mc_var,
                    "var_pct": round(mc_var * 100.0, 3),
                    "expected_shortfall": mc_es,
                    "expected_shortfall_pct": round(mc_es * 100.0, 3),
                    "n_simulations": n_simulations,
                    "seed": seed,
                },
            }
        return results


class StressTestingEngine:
    """
    Stress Testing Engine:
    Examines the sensitivity of portfolio tail risk to adverse market conditions.
    Supports standard macro scenarios and NEPSE-specific structural shocks.
    """

    @staticmethod
    def run_stress_scenarios(
        portfolio_returns: pd.Series,
        confidence_level: float = 0.95,
        var_engine: Optional[ValueAtRiskEngine] = None,
    ) -> Dict[str, Any]:
        """
        Runs sensitivity scenarios and compares normal vs stressed VaR/ES.
        """
        if var_engine is None:
            var_engine = ValueAtRiskEngine()

        # Baseline risk
        base_h_var, base_h_es = var_engine.historical_var_es(portfolio_returns, confidence_level)
        base_p_var, base_p_es = var_engine.parametric_var_es(portfolio_returns, confidence_level)

        clean_ret = portfolio_returns.dropna().values
        mu = float(np.mean(clean_ret))
        sigma = float(np.std(clean_ret, ddof=1))

        # Define scenario transformations (mean shift, vol expansion factor)
        scenarios = {
            "equity_crash": {
                "description": "Adverse equity market crash (-10% drift shift, 50% volatility spike)",
                "mean_shift": -0.10,
                "vol_multiplier": 1.50,
            },
            "interest_rate_shock": {
                "description": "Monetary tightening / rate hike shock (-5% valuation drag, 25% volatility spike)",
                "mean_shift": -0.05,
                "vol_multiplier": 1.25,
            },
            "liquidity_stress": {
                "description": "Liquidity dry-up and severe bid-ask widening (-3% drift shift, 75% volatility spike)",
                "mean_shift": -0.03,
                "vol_multiplier": 1.75,
            },
            "nepse_nrb_margin_cap": {
                "description": "NRB Margin Lending Cap Tightening (15/20 Cr cap retail deleveraging shock)",
                "mean_shift": -0.12,
                "vol_multiplier": 1.65,
            },
            "nepse_monsoon_force_majeure": {
                "description": "Monsoon Hydrological Disaster Shock (ROR hydro washouts, grid cut-off)",
                "mean_shift": -0.15,
                "vol_multiplier": 1.80,
            },
            "nepse_promoter_lockin_flood": {
                "description": "3-Year Promoter Lock-In Supply Flood (secondary float dilution supply wall)",
                "mean_shift": -0.08,
                "vol_multiplier": 1.40,
            },
        }

        scenario_results = {}
        for name, spec in scenarios.items():
            s_mean = mu + spec["mean_shift"]
            s_sigma = sigma * spec["vol_multiplier"]

            # Compute stressed parametric VaR & ES
            z_alpha = float(stats.norm.ppf(confidence_level))
            phi_z = float(stats.norm.pdf(z_alpha))
            tail_p = 1.0 - confidence_level

            stressed_p_var = max(0.0, z_alpha * s_sigma - s_mean)
            stressed_p_es = max(0.0, -s_mean + s_sigma * (phi_z / tail_p))

            # Apply empirical shock transformation for historical comparison
            stressed_hist_ret = (clean_ret - mu) * spec["vol_multiplier"] + s_mean
            cutoff_s = float(np.percentile(stressed_hist_ret, tail_p * 100.0))
            stressed_h_var = max(0.0, -cutoff_s)
            tail_s = stressed_hist_ret[stressed_hist_ret <= cutoff_s]
            stressed_h_es = max(0.0, float(-np.mean(tail_s))) if len(tail_s) > 0 else stressed_h_var

            delta_var = stressed_p_var - base_p_var
            delta_es = stressed_p_es - base_p_es
            pct_change_var = (delta_var / base_p_var * 100.0) if base_p_var > 1e-8 else 0.0
            pct_change_es = (delta_es / base_p_es * 100.0) if base_p_es > 1e-8 else 0.0

            scenario_results[name] = {
                "description": spec["description"],
                "baseline_var": round(base_p_var, 6),
                "baseline_var_pct": round(base_p_var * 100.0, 3),
                "stressed_var": round(stressed_p_var, 6),
                "stressed_var_pct": round(stressed_p_var * 100.0, 3),
                "delta_var": round(delta_var, 6),
                "delta_var_pct": round(pct_change_var, 2),
                "baseline_expected_shortfall": round(base_p_es, 6),
                "baseline_expected_shortfall_pct": round(base_p_es * 100.0, 3),
                "stressed_expected_shortfall": round(stressed_p_es, 6),
                "stressed_expected_shortfall_pct": round(stressed_p_es * 100.0, 3),
                "delta_expected_shortfall": round(delta_es, 6),
                "delta_expected_shortfall_pct": round(pct_change_es, 2),
                "stressed_historical_var": round(stressed_h_var, 6),
                "stressed_historical_es": round(stressed_h_es, 6),
            }

        return {
            "confidence_level": confidence_level,
            "baseline": {
                "parametric_var": round(base_p_var, 6),
                "parametric_es": round(base_p_es, 6),
                "historical_var": round(base_h_var, 6),
                "historical_es": round(base_h_es, 6),
            },
            "scenarios": scenario_results,
        }


class KupiecBacktester:
    """
    Historical VaR Backtesting Engine:
    Implements rolling one-step-ahead historical VaR forecasts without look-ahead bias.
    Calculates Kupiec Likelihood-Ratio (POF) test to evaluate unconditional coverage.
    """

    @staticmethod
    def calculate_lr_stat(n: int, x: int, p: float) -> Tuple[float, float]:
        """
        Computes Kupiec Likelihood-Ratio test statistic and p-value.
        H0: failure probability p* = p
        H1: failure probability p* != p

        LR_POF = -2 * ln( [ (1-p)^(N-x) * p^x ] / [ (1 - p_hat)^(N-x) * p_hat^x ] )
        """
        if n <= 0:
            return 0.0, 1.0

        p_hat = x / n

        # Boundary edge case 1: 0 exceptions
        if x == 0:
            lr_stat = -2.0 * n * np.log(1.0 - p)
        # Boundary edge case 2: N exceptions
        elif x == n:
            lr_stat = -2.0 * n * np.log(p)
        else:
            log_num = (n - x) * np.log(1.0 - p) + x * np.log(p)
            log_den = (n - x) * np.log(1.0 - p_hat) + x * np.log(p_hat)
            lr_stat = -2.0 * (log_num - log_den)

        lr_stat = max(0.0, float(lr_stat))
        p_val = float(stats.chi2.sf(lr_stat, df=1))
        return round(lr_stat, 6), round(p_val, 6)

    def run_rolling_backtest(
        self,
        returns: pd.Series,
        estimation_window: int = 250,
        confidence_level: float = 0.95,
        method: str = "historical",
        seed: int = 42,
    ) -> Dict[str, Any]:
        """
        Executes rolling one-step-ahead out-of-sample backtest.

        Parameters
        ----------
        returns : pd.Series
            Historical daily returns series.
        estimation_window : int
            Number of historical observations in preceding rolling window (default 250).
        confidence_level : float
            Confidence level for VaR (e.g. 0.95).
        method : str
            Model type: 'historical', 'parametric', or 'monte_carlo'.
        seed : int
            Reproducibility seed for Monte Carlo simulation.
        """
        clean_ret = returns.dropna()
        t_total = len(clean_ret)

        if t_total <= estimation_window:
            raise RiskModelError(
                f"Total returns ({t_total}) must exceed estimation window ({estimation_window})."
            )

        var_engine = ValueAtRiskEngine()
        tail_p = 1.0 - confidence_level

        forecast_vars = []
        realized_returns = []
        exceptions = []
        dates = []

        ret_values = clean_ret.values
        ret_index = clean_ret.index

        for t in range(estimation_window, t_total):
            window_slice = ret_values[t - estimation_window : t]
            realized_t = float(ret_values[t])

            if method == "historical":
                cutoff = float(np.percentile(window_slice, tail_p * 100.0))
                var_t = max(0.0, -cutoff)
            elif method == "parametric":
                mu_w = float(np.mean(window_slice))
                sigma_w = float(np.std(window_slice, ddof=1))
                z_alpha = float(stats.norm.ppf(confidence_level))
                var_t = max(0.0, z_alpha * sigma_w - mu_w)
            elif method == "monte_carlo":
                mu_w = float(np.mean(window_slice))
                sigma_w = float(np.std(window_slice, ddof=1))
                rng = np.random.default_rng(seed + t)
                mc_draws = rng.normal(mu_w, sigma_w, 2000)
                cutoff = float(np.percentile(mc_draws, tail_p * 100.0))
                var_t = max(0.0, -cutoff)
            else:
                raise ValueError(f"Unknown VaR model: {method}")

            # Exception: loss exceeds VaR (return < -VaR)
            is_exception = realized_t < -var_t

            forecast_vars.append(var_t)
            realized_returns.append(realized_t)
            exceptions.append(bool(is_exception))
            dates.append(ret_index[t])

        n_forecasts = len(forecast_vars)
        n_exceptions = sum(exceptions)
        observed_rate = n_exceptions / n_forecasts if n_forecasts > 0 else 0.0
        expected_rate = tail_p

        lr_stat, p_val = self.calculate_lr_stat(n_forecasts, n_exceptions, expected_rate)

        # Institutional verdict: Fail to Reject H0 (p >= 0.05) -> Model is calibrated
        verdict = "PASS" if p_val >= 0.05 else "FAIL"

        return {
            "model": method,
            "confidence_level": confidence_level,
            "estimation_window": estimation_window,
            "number_of_forecasts": n_forecasts,
            "number_of_exceptions": n_exceptions,
            "observed_exception_rate": round(observed_rate, 6),
            "observed_exception_rate_pct": round(observed_rate * 100.0, 3),
            "expected_exception_rate": round(expected_rate, 6),
            "expected_exception_rate_pct": round(expected_rate * 100.0, 3),
            "kupiec_lr_statistic": lr_stat,
            "kupiec_p_value": p_val,
            "unconditional_coverage_verdict": verdict,
            "is_calibrated": verdict == "PASS",
        }


class QuantRiskLab:
    """
    Unified QuantRiskLab Orchestrator:
    Combines Portfolio Analytics, Triple-Methodology VaR/ES,
    Adverse Stress Testing, and Rolling Kupiec Backtesting into an institutional report.
    """

    def __init__(self, trading_days: int = 240, rf_rate: float = 0.04):
        self.analytics = PortfolioAnalytics(trading_days=trading_days, rf_rate=rf_rate)
        self.var_engine = ValueAtRiskEngine()
        self.stress_engine = StressTestingEngine()
        self.backtester = KupiecBacktester()

    def run_full_analysis(
        self,
        returns_df: pd.DataFrame,
        weights: Union[Dict[str, float], List[float], np.ndarray],
        estimation_window: int = 250,
        confidence_levels: Optional[List[float]] = None,
        n_mc_simulations: int = 10000,
        seed: int = 42,
    ) -> Dict[str, Any]:
        """
        Executes end-to-end institutional portfolio risk analysis pipeline.
        """
        if confidence_levels is None:
            confidence_levels = [0.95, 0.99]

        validated_weights = self.analytics.validate_weights(
            weights, symbols=list(returns_df.columns)
        )
        port_returns = self.analytics.compute_portfolio_returns(returns_df, validated_weights)

        # 1. Portfolio Analytics
        perf_metrics = self.analytics.compute_metrics(port_returns)

        # 2. VaR and Expected Shortfall
        var_metrics = self.var_engine.compute_all_models(
            port_returns,
            confidence_levels=confidence_levels,
            n_simulations=n_mc_simulations,
            seed=seed,
        )

        # 3. Stress Testing (at primary 95% confidence)
        stress_metrics = self.stress_engine.run_stress_scenarios(
            port_returns,
            confidence_level=0.95,
            var_engine=self.var_engine,
        )

        # 4. Rolling Kupiec Backtests
        # Adjust estimation window if series is shorter than 250 + 30
        adj_window = estimation_window
        if len(port_returns) <= adj_window + 20:
            adj_window = max(20, int(len(port_returns) * 0.5))

        backtest_results = {}
        for method in ["historical", "parametric", "monte_carlo"]:
            bt = self.backtester.run_rolling_backtest(
                port_returns,
                estimation_window=adj_window,
                confidence_level=0.95,
                method=method,
                seed=seed,
            )
            backtest_results[method] = bt

        return {
            "weights": validated_weights,
            "portfolio_analytics": perf_metrics,
            "value_at_risk_and_expected_shortfall": var_metrics,
            "stress_testing": stress_metrics,
            "rolling_kupiec_backtesting": backtest_results,
        }

    def generate_markdown_report(self, results: Dict[str, Any]) -> str:
        """Generates an institutional audit report in Markdown format."""
        pa = results["portfolio_analytics"]
        var_data = results["value_at_risk_and_expected_shortfall"]["95pct"]
        stress = results["stress_testing"]["scenarios"]
        bt = results["rolling_kupiec_backtesting"]

        md = []
        md.append("# [QuantRiskLab] Institutional Portfolio Risk & Stress Report")
        md.append("")
        md.append("## 1. Portfolio Analytics")
        md.append(f"- **Annualized Return:** {pa['annualized_expected_return_pct']}%")
        md.append(f"- **Annualized Volatility:** {pa['annualized_volatility_pct']}%")
        md.append(f"- **Sharpe Ratio (Rf={self.analytics.rf_rate*100}%):** {pa['sharpe_ratio']}")
        md.append(f"- **Maximum Drawdown:** {pa['max_drawdown_pct']}%")
        md.append(f"- **Cumulative Return:** {pa['cumulative_return_pct']}%")
        md.append(f"- **Total Return Bars:** {pa['n_observations']}")
        md.append("")
        md.append("## 2. One-Day Tail Risk (95% Confidence Level)")
        md.append("| Methodology | Value at Risk (VaR 95%) | Expected Shortfall (ES 95%) |")
        md.append("|---|---|---|")
        md.append(f"| **Historical Simulation** | {var_data['historical']['var_pct']}% | {var_data['historical']['expected_shortfall_pct']}% |")
        md.append(f"| **Parametric Gaussian** | {var_data['parametric_gaussian']['var_pct']}% | {var_data['parametric_gaussian']['expected_shortfall_pct']}% |")
        md.append(f"| **Monte Carlo Simulation** | {var_data['monte_carlo']['var_pct']}% | {var_data['monte_carlo']['expected_shortfall_pct']}% |")
        md.append("")
        md.append("## 3. Adverse Stress Testing")
        md.append("| Scenario | Stressed VaR | Delta VaR (%) | Stressed ES | Delta ES (%) |")
        md.append("|---|---|---|---|---|")
        for sc_name, sc in stress.items():
            md.append(f"| **{sc_name}** | {sc['stressed_var_pct']}% | +{sc['delta_var_pct']}% | {sc['stressed_expected_shortfall_pct']}% | +{sc['delta_expected_shortfall_pct']}% |")
        md.append("")
        md.append("## 4. Historical VaR Backtesting (Kupiec POF Unconditional Coverage)")
        md.append("| Model | Forecasts | Exceptions | Observed Rate | Expected Rate | LR Stat | p-value | Verdict |")
        md.append("|---|---|---|---|---|---|---|---|")
        for m_name, m_bt in bt.items():
            md.append(
                f"| **{m_name.capitalize()}** | {m_bt['number_of_forecasts']} | {m_bt['number_of_exceptions']} | "
                f"{m_bt['observed_exception_rate_pct']}% | {m_bt['expected_exception_rate_pct']}% | "
                f"{m_bt['kupiec_lr_statistic']} | {m_bt['kupiec_p_value']} | **{m_bt['unconditional_coverage_verdict']}** |"
            )
        md.append("")
        return "\n".join(md)


def main():
    """Demo run with simulated NEPSE blue-chip universe."""
    logger.info("Initializing QuantRiskLab demo run...")
    np.random.seed(42)
    dates = pd.date_range("2024-01-01", periods=300)
    data = {
        "NABIL": np.random.normal(0.0006, 0.015, 300),
        "GBIME": np.random.normal(0.0004, 0.016, 300),
        "CHCL": np.random.normal(0.0008, 0.024, 300),
        "SHIVM": np.random.normal(0.0005, 0.022, 300),
        "CIT": np.random.normal(0.0007, 0.014, 300),
    }
    df = pd.DataFrame(data, index=dates)
    weights = {"NABIL": 0.25, "GBIME": 0.20, "CHCL": 0.20, "SHIVM": 0.15, "CIT": 0.20}

    lab = QuantRiskLab(trading_days=240, rf_rate=0.04)
    results = lab.run_full_analysis(df, weights, estimation_window=100)
    report = lab.generate_markdown_report(results)
    print("\n" + report)


if __name__ == "__main__":
    main()

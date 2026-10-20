/**
 * Section 5.1 — Apex Wealth Design System Tokens & Surface Elevation (Dark Mode Baseline)
 * Enforces strict Layman Frontend / Institutional Backend visual hierarchy and
 * tabular-nums monospace precision across all numeric telemetry, hashes, prices, and bps displays.
 */

export const APEX_THEME_TOKENS = {
  colors: {
    bgBase: "#080B11",       // --bg-base: Primary Canvas
    bgSurface1: "#111622",   // --bg-surface-1: Card / Widget Container
    bgSurface2: "#1E2638",   // --bg-surface-2: Modal / Overlay Drawer
    accentOptimal: "#10B981",// --accent-optimal: Emerald Green
    accentWarning: "#F59E0B",// --accent-warning: Amber Yellow
    accentCritical: "#EF4444",// --accent-critical: Crimson Red
    accentBlue: "#3B82F6",   // --accent-blue: Actionable Accent
    textPrimary: "#F8FAFC",
    textSecondary: "#94A3B8",
    textMuted: "#64748B",
    borderSubtle: "rgba(148, 163, 184, 0.14)",
    rebalanceGlow: "rgba(59, 130, 246, 0.08)",
  },
  typography: {
    fontPrimary: "'Inter', -apple-system, BlinkMacSystemFont, sans-serif",
    fontMono: "'JetBrains Mono', 'Fira Code', monospace",
    tabularNums: "tabular-nums",
  },
  elevation: {
    canvas: "0 0 0 1px rgba(148, 163, 184, 0.08)",
    surface1: "0 10px 30px -10px rgba(0, 0, 0, 0.65), 0 0 0 1px rgba(148, 163, 184, 0.12)",
    surface2: "0 24px 48px -12px rgba(0, 0, 0, 0.85), 0 0 0 1px rgba(59, 130, 246, 0.28)",
    rebalanceCard: "0 0 36px 2px rgba(59, 130, 246, 0.08), 0 0 0 1px rgba(59, 130, 246, 0.35)",
  },
  layout: {
    maxLaymanPrimaryCards: 6, // Rule of 6 layout ergonomics
    gridColumns: 12,
  },
} as const;

export const CSS_CUSTOM_PROPERTIES = `
  :root {
    --bg-base: #080B11;
    --bg-surface-1: #111622;
    --bg-surface-2: #1E2638;
    --accent-optimal: #10B981;
    --accent-warning: #F59E0B;
    --accent-critical: #EF4444;
    --accent-blue: #3B82F6;
    --font-primary: 'Inter', sans-serif;
    --font-mono: 'JetBrains Mono', monospace;
  }

  body {
    background-color: var(--bg-base);
    color: #F8FAFC;
    font-family: var(--font-primary);
    margin: 0;
    padding: 0;
    -webkit-font-smoothing: antialiased;
  }

  .font-mono-tabular {
    font-family: var(--font-mono);
    font-variant-numeric: tabular-nums;
  }

  @keyframes flashUpGreen {
    0% { background-color: rgba(16, 185, 129, 0.34); color: #6EE7B7; }
    100% { background-color: transparent; }
  }

  @keyframes flashDownRed {
    0% { background-color: rgba(239, 68, 68, 0.34); color: #FCA5A5; }
    100% { background-color: transparent; }
  }

  .flash-up {
    animation: flashUpGreen 650ms ease-out;
  }

  .flash-down {
    animation: flashDownRed 650ms ease-out;
  }
`;

export function getHealthStatusColor(score: number, penaltyTriggered = false): string {
  if (score >= 80 && !penaltyTriggered) return APEX_THEME_TOKENS.colors.accentOptimal;
  if (score >= 55) return APEX_THEME_TOKENS.colors.accentWarning;
  return APEX_THEME_TOKENS.colors.accentCritical;
}

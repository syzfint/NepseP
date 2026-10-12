---
name: NEPSE Quantitative Terminal
colors:
  surface: '#0f141b'
  surface-dim: '#0f141b'
  surface-bright: '#353941'
  surface-container-lowest: '#0a0e15'
  surface-container-low: '#181c23'
  surface-container: '#0D131F'
  surface-container-high: '#262a32'
  surface-container-highest: '#31353d'
  on-surface: '#dfe2ed'
  on-surface-variant: '#bac9cc'
  inverse-surface: '#dfe2ed'
  inverse-on-surface: '#2c3139'
  outline: '#849396'
  outline-variant: '#3b494c'
  surface-tint: '#00daf3'
  primary: '#c3f5ff'
  on-primary: '#00363d'
  primary-container: '#00e5ff'
  on-primary-container: '#00626e'
  inverse-primary: '#006875'
  secondary: '#7dffa2'
  on-secondary: '#003918'
  secondary-container: '#05e777'
  on-secondary-container: '#00622e'
  tertiary: '#f4e8ff'
  on-tertiary: '#400688'
  tertiary-container: '#ddc7ff'
  on-tertiary-container: '#6b40b2'
  error: '#ffb4ab'
  on-error: '#690005'
  error-container: '#93000a'
  on-error-container: '#ffdad6'
  primary-fixed: '#9cf0ff'
  primary-fixed-dim: '#00daf3'
  on-primary-fixed: '#001f24'
  on-primary-fixed-variant: '#004f58'
  secondary-fixed: '#62ff96'
  secondary-fixed-dim: '#00e475'
  on-secondary-fixed: '#00210b'
  on-secondary-fixed-variant: '#005226'
  tertiary-fixed: '#ebdcff'
  tertiary-fixed-dim: '#d4bbff'
  on-tertiary-fixed: '#260058'
  on-tertiary-fixed-variant: '#582a9f'
  background: '#0f141b'
  on-background: '#dfe2ed'
  surface-variant: '#31353d'
  surface-root: '#020306'
  surface-panel: '#070B12'
  surface-elevated: '#131B2A'
  border-muted: '#131B2A'
  border-subtle: '#1B2538'
  border-accent: '#24344D'
  text-primary: '#FFFFFF'
  text-secondary: '#94A3B8'
  text-tertiary: '#475569'
  status-advance: '#00E676'
  status-decline: '#FF1744'
  status-warning: '#FFB300'
  status-system: '#00E5FF'
  status-rotation: '#B388FF'
  flash-advance: rgba(0, 230, 118, 0.35)
  flash-decline: rgba(255, 23, 68, 0.35)
  flash-system: rgba(0, 229, 255, 0.35)
  flash-warning: rgba(255, 179, 0, 0.35)
  flash-rotation: rgba(179, 136, 255, 0.35)
typography:
  headline-lg:
    fontFamily: JetBrains Mono
    fontSize: 16px
    fontWeight: '700'
    lineHeight: 20px
    letterSpacing: 0.04em
  headline-md:
    fontFamily: JetBrains Mono
    fontSize: 14px
    fontWeight: '600'
    lineHeight: 18px
    letterSpacing: 0.02em
  headline-sm:
    fontFamily: JetBrains Mono
    fontSize: 13px
    fontWeight: '600'
    lineHeight: 16px
    letterSpacing: 0.02em
  body-lg:
    fontFamily: JetBrains Mono
    fontSize: 13px
    fontWeight: '400'
    lineHeight: 18px
    letterSpacing: 0em
  body-md:
    fontFamily: JetBrains Mono
    fontSize: 12px
    fontWeight: '400'
    lineHeight: 16px
    letterSpacing: 0em
  body-sm:
    fontFamily: JetBrains Mono
    fontSize: 11px
    fontWeight: '400'
    lineHeight: 14px
    letterSpacing: 0em
  label-lg:
    fontFamily: JetBrains Mono
    fontSize: 11px
    fontWeight: '600'
    lineHeight: 14px
    letterSpacing: 0.05em
  label-md:
    fontFamily: JetBrains Mono
    fontSize: 10px
    fontWeight: '600'
    lineHeight: 12px
    letterSpacing: 0.06em
  label-sm:
    fontFamily: JetBrains Mono
    fontSize: 9px
    fontWeight: '500'
    lineHeight: 11px
    letterSpacing: 0.08em
spacing:
  gutter: 0.375rem
  margin: 0.25rem
  space-xs: 0.125rem
  space-sm: 0.25rem
  space-md: 0.375rem
  space-lg: 0.5rem
  space-xl: 0.75rem
---

## Brand & Style
The design system embodies an uncompromising, institutional-grade quantitative trading workstation tailored to the microstructure of the Nepal Stock Exchange (NEPSE). It prioritizes rapid visual parsing, zero cognitive lag under volatile execution, and extreme data density over consumer decorative aesthetics.

The visual style is rooted in **High-Density Technical Functionalism**:
- Deep obsidian foundation layers designed for prolonged, low-eye-strain command sessions.
- Monospaced typographic discipline with tabular numerical alignment to eliminate jitter across sub-second execution updates.
- High-contrast chromatic signals mapped mathematically to capital flows, syndicate cornering, settlement gates, and stop-loss levels.
- Utilitarian spatial distribution targeting fixed 16:9 enterprise displays with zero viewport scrolling, strict grid discipline, and persistent system telemetry.

## Colors
The terminal operates strictly within an institutional dark-mode color architecture. Surfaces progress through three distinct low-reflection tiers (`#020306` root canvas, `#070B12` panel containers, and `#0D131F` inner data wells) separated by hairline boundary borders (`#131B2A`, `#1B2538`).

Chromatic tokens are strictly semantic and functional:
- **Primary / System Cyan (`#00E5FF`)**: Represents operational baseline, active system states, normalized telemetry, median trajectory vectors (P50), and verified EOD synchronizations.
- **Advance / Positive Green (`#00E676`)**: Indicates institutional accumulation, buy-side liquidity pressure, upper conformal prediction bounds (P90), and market gains.
- **Decline / Negative Red (`#FF1744`)**: Signifies sell-side distribution, execution stop-losses, downside volatility thresholds (P10), and circuit clips.
- **Warning / Cartel Amber (`#FFB300`)**: Highlights syndicate float concentration, lock-in expiry overhangs, and macro volatility alerts.
- **Highlight / Rotation Purple (`#B388FF`)**: Flags capital rotation vectors across sectors, ML-derived confidence clusters, and bipartite broker link anomalies.

Tick-level flashes leverage 35% opacity RGBA overlays that instantaneously highlight updated rows before fading over an `ease-out` transition back to base container values.

## Typography
Typographic hierarchy is built entirely upon `JetBrains Mono` (with fallbacks to `Segoe UI Mono` and `Consolas`), enforcing character-width consistency across all financial telemetry.

Critical typographic principles:
- **Tabular Numerals**: Every number display strictly sets `font-variant-numeric: tabular-nums` to guarantee vertical decimal alignment in order book depths, tape volumes, and price changes without layout shifts.
- **Micro-Scale Density**: Type scales down to 9px (`label-sm`) for auxiliary metrics, broker tags, and exchange protocol badges, remaining razor-sharp via dark-mode subpixel anti-aliasing.
- **Label Case**: Badges, column headers, execution status indicators, and keyboard shortcuts enforce full uppercase transformation with positive letter-spacing (`0.05em` to `0.08em`) to ensure instant legibility at small sizes.

## Layout & Spacing
The layout adheres to a fixed-viewport, zero-scroll desktop environment calibrated for 16:9 monitors (`100vw` by `100vh` with `overflow: hidden`). 

The master viewport is divided into three fixed vertical tiers:
1. **System Bar (Top)**: Fixed `38px` height containing the terminal brand mark, workspace hotkeys (0–9), live NEPSE index telemetry, breadth meters, and Nepal Standard Time (NST) sync clock.
2. **Master Workspace Canvas (Middle)**: Fluid `1fr` height housing the active workspace grid (e.g., Level 2 order book ladder, canvas charting stage, execution blotter, or universe scanner).
3. **Telemetry Status Footer (Bottom)**: Fixed `28px` height reporting sequence locks, engine latency (microsecond scale), CDS & Clearing T+2 settlement status, and broker floor-sheet ingestion status.

Internal panel divisions utilize an ultra-dense spacing scale with `0.375rem` (6px) gutters and `0.25rem` (4px) margins. Elements within tables and ladders use `0.125rem` to `0.25rem` padding to maximize vertical visibility of market depth.

## Elevation & Depth
Elevation in this terminal rejects physical drop shadows in favor of **structural line boundaries and tonal surface tiering**. Because rendering speed is critical, low-overhead methods maintain high frame rates:

- **Surface Tiering**:
  - `Root Background (#020306)`: Deepest canvas level.
  - `Panel Base (#070B12)`: Active widget shells and chart containers.
  - `Data Well (#0D131F)`: Table rows, blotter inputs, and inner analytical panes.
  - `Interactive Element (#131B2A)`: Unselected tabs, unpressed buttons, and badge backgrounds.
- **Borders & Dividers**: Crisp, 1px solid hairline dividers (`#1B2538` and `#131B2A`) provide pixel-precise structural separation between high-density components.
- **Glow & Translucent Overlays**: Subtle, hardware-accelerated cyan/amber glow borders (`rgba(0, 229, 255, 0.25)`) appear exclusively on active workspace focus or critical risk stops. Charting forecast corridors utilize 10% opacity WebGL polygon fills between confidence intervals.

## Shapes
The design system enforces a sharp geometric aesthetic with `0px` border radii across all terminal surfaces, panels, tables, badges, and button states. 

Crisp corners maximize every usable display pixel, eliminating dead space along panel boundaries and preserving the precision required of a quantitative trading workstation. Structural accent tags feature vertical left-border indicators (2px solid) rather than rounded tabs.

## Components

### Telemetry Bars & Status Indicators
- **Top & Footer Bars**: Monospaced 38px and 28px horizontal strips. Status indicators show live market phase (`OPEN` in `#00E676`, `POST-CLOSE / SETTLED` in `#FFB300`) with blinking pulse markers.
- **Latency & SeqLock Meters**: Right-aligned micro-labels with direct microsecond readout (e.g., `LATENCY: 142.5 μs`).

### Level 2 Order Book Ladder
- **Bid / Ask Matrix**: Dual-column layout displaying queue order count, lot quantity, and execution price.
- **Depth Background Fills**: Horizontal volume depth bars rendered behind data cells using transparent green (`rgba(0, 230, 118, 0.15)`) for bids and transparent red (`rgba(255, 23, 68, 0.15)`) for asks.
- **Tick Flash**: Cell backgrounds flash via `rgba` fills on book modification, returning to background within 300ms.

### Workspace Tab Navigators
- **Key-Indexed Tabs**: Fixed-height tabs embedded with numeric hotkeys (e.g., `[2] ANALYSIS`).
- **Active State**: Inset `#00E5FF` border, white text, and `#0D131F` background. Inactive tabs display `#475569` text and `#070B12` background.

### Buttons & Action Triggers
- **Primary Execution**: Full uppercase, 11px font size, `#00E5FF` high-contrast outline with 10% cyan background.
- **Buy / Long Triggers**: Solid `#00E676` background or outline with dark `#020306` text when armed.
- **Sell / Liquidate Triggers**: Solid `#FF1744` background with white `#FFFFFF` text.
- **State Toggles**: Sharp rectangular chips displaying binary state (e.g., `REPLAY: OFF`, `LOCK-IN: CRITICAL`).

### Inputs & Order Blotters
- **Lot Quantization Controls**: Input fields pre-calibrated for NEPSE standard 10-kitta lot sizes with quick-increment tags (`10 K`, `50 K`, `100 K`, `500 K`).
- **Surface**: Inner wells set to `#0D131F` with 1px border `#1B2538`. Focus state shifts the border to 1px `#00E5FF`.

### Layman Operator Guide (Pedagogical Overlay)
- **Collapsible Banner**: Positioned at the header of analytical workspaces. Features a 3px left border colored to match the screen's risk tier.
- **Dual-Script Typography**: Pairs English quantitative labels with secondary native Nepali script subtitles to explain advanced models (e.g., Hawkes Intensity, Bipartite Flow) in direct operational terms.
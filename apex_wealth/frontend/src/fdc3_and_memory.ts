/**
 * Section 7.1 & 7.3 — High-Frequency Memory Management (SharedArrayBuffer + Atomics + Web Worker)
 * and FINOS FDC3 2.0 Desktop Interoperability (`window.fdc3.raiseIntent` & `fdc3.broadcast`).
 */

export interface FDC3InstrumentContext {
  type: "fdc3.instrument";
  name: string;
  id: {
    ticker: string;
    exchange: string;
  };
}

export interface FDC3PortfolioContext {
  type: "fdc3.portfolio";
  name: string;
  positions: Array<{
    instrument: FDC3InstrumentContext;
    holding: number;
    targetWeight?: number;
  }>;
}

export type FDC3ContextPayload = FDC3InstrumentContext | FDC3PortfolioContext | Record<string, unknown>;

export interface FDC3DesktopAgent {
  version: string;
  raiseIntent: (intent: "ViewPortfolio" | "RebalanceAccount" | "ViewChart" | string, context: FDC3ContextPayload) => Promise<{
    intent: string;
    context: FDC3ContextPayload;
    timestamp: string;
  }>;
  broadcast: (context: FDC3ContextPayload) => Promise<void>;
  addContextListener: (
    contextType: string | null,
    handler: (context: FDC3ContextPayload) => void
  ) => { unsubscribe: () => void };
}

declare global {
  interface Window {
    fdc3?: FDC3DesktopAgent;
  }
}

const fdc3Listeners: Array<{ type: string | null; handler: (ctx: FDC3ContextPayload) => void }> = [];

/**
 * Initialize FINOS FDC3 2.0 Desktop Interop shim on `window.fdc3` if not already injected by OpenFin/Finsemble.
 */
export function initFDC3DesktopBridge(
  onIntentRaised?: (intent: string, context: FDC3ContextPayload) => void
): FDC3DesktopAgent {
  const existing = window.fdc3;
  if (existing) return existing;

  const agent: FDC3DesktopAgent = {
    version: "2.0.0",
    async raiseIntent(intent, context) {
      const eventRecord = {
        intent,
        context,
        timestamp: new Date().toISOString(),
      };
      onIntentRaised?.(intent, context);
      for (const l of fdc3Listeners) {
        if (!l.type || l.type === (context as { type?: string }).type) {
          l.handler(context);
        }
      }
      return eventRecord;
    },
    async broadcast(context) {
      for (const l of fdc3Listeners) {
        if (!l.type || l.type === (context as { type?: string }).type) {
          l.handler(context);
        }
      }
    },
    addContextListener(contextType, handler) {
      const entry = { type: contextType, handler };
      fdc3Listeners.push(entry);
      return {
        unsubscribe: () => {
          const idx = fdc3Listeners.indexOf(entry);
          if (idx >= 0) fdc3Listeners.splice(idx, 1);
        },
      };
    },
  };

  window.fdc3 = agent;
  return agent;
}

/**
 * Zero-Copy SharedArrayBuffer & Atomics ring store for VPIN time series and LOB vectors.
 * Automatically falls back to standard ArrayBuffer when COOP/COEP headers are absent.
 */
export class HighFrequencyTelemetryBuffer {
  public readonly capacity: number;
  public readonly int32View: Int32Array;
  public readonly float64View: Float64Array;
  public readonly isSharedMemory: boolean;

  constructor(capacity = 128) {
    this.capacity = capacity;
    const byteLength = 64 + capacity * 32;
    let rawBuffer: SharedArrayBuffer | ArrayBuffer;

    if (typeof SharedArrayBuffer !== "undefined") {
      try {
        rawBuffer = new SharedArrayBuffer(byteLength);
        this.isSharedMemory = true;
      } catch {
        rawBuffer = new ArrayBuffer(byteLength);
        this.isSharedMemory = false;
      }
    } else {
      rawBuffer = new ArrayBuffer(byteLength);
      this.isSharedMemory = false;
    }

    this.int32View = new Int32Array(rawBuffer, 0, 8);
    this.float64View = new Float64Array(rawBuffer, 32);
  }

  public writeTick(vpin: number, hawkes: number, price: number, top3Depth: number): number {
    let seq = 0;
    if (this.isSharedMemory && typeof Atomics !== "undefined") {
      seq = Atomics.add(this.int32View, 0, 1) + 1;
    } else {
      seq = (this.int32View[0] || 0) + 1;
      this.int32View[0] = seq;
    }
    const slot = ((seq - 1) % this.capacity) * 4;
    this.float64View[slot] = vpin;
    this.float64View[slot + 1] = hawkes;
    this.float64View[slot + 2] = price;
    this.float64View[slot + 3] = top3Depth;
    return seq;
  }
}

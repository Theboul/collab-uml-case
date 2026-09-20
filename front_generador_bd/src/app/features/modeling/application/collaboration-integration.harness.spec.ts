/**
 * Utilidades compartidas por los specs de integración del Nivel B (navegador real + servidor real).
 * Necesitan el arnés `scripts/collab-e2e/run.py`; sin él, los tests quedan pendientes y `ng test`
 * sigue verde. Ver scripts/collab-e2e/README.md.
 */

export const ADMIN = 'http://127.0.0.1:8941';

export interface HarnessConfig {
  wsBase: string;
  httpBase: string;
  canvasId: string;
  collaboratorUserId: string;
  tokens: {
    owner: string;
    outsider: string;
    collaborator: string;
    peer: string;
    expiredOwner: string;
  };
}

let config: HarnessConfig | null = null;

/** Lee la configuración sembrada por el arnés; `null` si no está corriendo. */
export async function loadHarnessConfig(): Promise<void> {
  try {
    const res = await fetch(`${ADMIN}/config`);
    config = res.ok ? ((await res.json()) as HarnessConfig) : null;
  } catch {
    config = null;
  }
}

export function hasHarness(): boolean {
  return config !== null;
}

/** La configuración del arnés, o deja el test pendiente si no está disponible. */
export function backend(): HarnessConfig {
  if (!config) {
    pending('arnés de integración no disponible (ver scripts/collab-e2e/README.md)');
  }
  return config as HarnessConfig;
}

export async function admin(path: string): Promise<void> {
  await fetch(`${ADMIN}${path}`);
}

/** Vuelve a dejar el proxy abierto y con los contadores a cero. */
export async function resetHarness(): Promise<void> {
  if (hasHarness()) {
    await admin('/restore');
    await admin('/reset');
  }
}

export interface ProxyStats {
  accepted: number;
  refused: number;
  open: number;
  cut: boolean;
}

export async function stats(): Promise<ProxyStats> {
  return (await (await fetch(`${ADMIN}/stats`)).json()) as ProxyStats;
}

export const sleep = (ms: number) => new Promise<void>((resolve) => setTimeout(resolve, ms));

export async function waitFor(
  condition: () => boolean,
  timeoutMs: number,
  what: string,
): Promise<void> {
  const deadline = Date.now() + timeoutMs;
  while (!condition()) {
    if (Date.now() > deadline) throw new Error(`Tiempo agotado esperando: ${what}`);
    await sleep(50);
  }
}

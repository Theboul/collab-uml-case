import {
  RECONNECT_MAX_ATTEMPTS,
  RECONNECT_MAX_DELAY_MS,
  RECONNECT_MIN_DELAY_MS,
} from './collaboration-tuning';

/** Token inválido o vencido: se puede renovar y reintentar una vez. */
export const CLOSE_UNAUTHORIZED = 4401;
/** Sin permiso sobre el lienzo (o el lienzo no existe): no se reintenta. */
export const CLOSE_FORBIDDEN = 4403;

export type ReconnectDecision =
  | { action: 'retry'; delayMs: number }
  | { action: 'refresh-token' }
  | { action: 'give-up'; reason: 'forbidden' | 'unauthorized' | 'exhausted' };

/**
 * Backoff exponencial con jitter: la mitad del retardo es fija y la otra mitad aleatoria, así
 * nunca es ~0 y los clientes de una misma caída no reintentan todos a la vez.
 */
export function backoffDelayMs(attempt: number, random: () => number = Math.random): number {
  const base = Math.min(RECONNECT_MAX_DELAY_MS, RECONNECT_MIN_DELAY_MS * 2 ** attempt);
  return Math.round(base * (0.5 + random() * 0.5));
}

/**
 * Qué hacer cuando el canal se cierra sin haberlo pedido el cliente. `failedAttempts` cuenta los
 * reintentos consecutivos ya fallidos; `tokenAlreadyRefreshed` indica que en este ciclo ya se
 * renovó el token (un segundo 4401 significa que renovarlo no basta).
 */
export function decideAfterClose(
  closeCode: number,
  failedAttempts: number,
  tokenAlreadyRefreshed: boolean,
  random: () => number = Math.random,
): ReconnectDecision {
  if (closeCode === CLOSE_FORBIDDEN) return { action: 'give-up', reason: 'forbidden' };
  if (closeCode === CLOSE_UNAUTHORIZED) {
    return tokenAlreadyRefreshed
      ? { action: 'give-up', reason: 'unauthorized' }
      : { action: 'refresh-token' };
  }
  if (failedAttempts >= RECONNECT_MAX_ATTEMPTS) return { action: 'give-up', reason: 'exhausted' };
  return { action: 'retry', delayMs: backoffDelayMs(failedAttempts, random) };
}

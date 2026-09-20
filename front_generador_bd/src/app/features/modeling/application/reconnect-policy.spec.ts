import {
  RECONNECT_MAX_ATTEMPTS,
  RECONNECT_MAX_DELAY_MS,
  RECONNECT_MIN_DELAY_MS,
} from './collaboration-tuning';
import {
  CLOSE_FORBIDDEN,
  CLOSE_UNAUTHORIZED,
  backoffDelayMs,
  decideAfterClose,
} from './reconnect-policy';

describe('reconnect-policy', () => {
  describe('backoffDelayMs', () => {
    it('crece exponencialmente y se detiene en el tope (random = 1: sin recorte por jitter)', () => {
      const delays = [0, 1, 2, 3, 4, 5, 6, 7].map((n) => backoffDelayMs(n, () => 1));

      expect(delays).toEqual([1000, 2000, 4000, 8000, 16000, 30000, 30000, 30000]);
    });

    it('el jitter deja la mitad del retardo fija y varía la otra mitad', () => {
      expect(backoffDelayMs(3, () => 0)).toBe(4000); // 8000 × 0,5
      expect(backoffDelayMs(3, () => 0.5)).toBe(6000);
      expect(backoffDelayMs(3, () => 1)).toBe(8000);
    });

    it('nunca es ~0: el mínimo posible es la mitad del retardo mínimo', () => {
      expect(backoffDelayMs(0, () => 0)).toBe(RECONNECT_MIN_DELAY_MS / 2);
    });

    it('con el azar real queda siempre entre el 50 % y el 100 % de la base', () => {
      for (let attempt = 0; attempt < RECONNECT_MAX_ATTEMPTS; attempt++) {
        const base = Math.min(RECONNECT_MAX_DELAY_MS, RECONNECT_MIN_DELAY_MS * 2 ** attempt);
        for (let i = 0; i < 100; i++) {
          const delay = backoffDelayMs(attempt);
          expect(delay).toBeGreaterThanOrEqual(base / 2);
          expect(delay).toBeLessThanOrEqual(base);
        }
      }
    });

    it('sin jitter los retardos de todos los reintentos suman ~2 minutos', () => {
      let total = 0;
      for (let attempt = 0; attempt < RECONNECT_MAX_ATTEMPTS; attempt++) {
        total += backoffDelayMs(attempt, () => 1);
      }

      expect(total).toBe(121_000);
    });
  });

  describe('decideAfterClose', () => {
    const noJitter = () => 1;

    it('4403 (sin permiso): se rinde sin reintentar', () => {
      expect(decideAfterClose(CLOSE_FORBIDDEN, 0, false, noJitter)).toEqual({
        action: 'give-up',
        reason: 'forbidden',
      });
    });

    it('4403 gana aunque queden intentos y aunque ya se haya renovado el token', () => {
      expect(decideAfterClose(CLOSE_FORBIDDEN, 0, true, noJitter).action).toBe('give-up');
    });

    it('4401 (token vencido): la primera vez pide renovar el token', () => {
      expect(decideAfterClose(CLOSE_UNAUTHORIZED, 0, false, noJitter)).toEqual({
        action: 'refresh-token',
      });
    });

    it('4401 después de haber renovado: se rinde por no autorizado (no entra en bucle)', () => {
      expect(decideAfterClose(CLOSE_UNAUTHORIZED, 0, true, noJitter)).toEqual({
        action: 'give-up',
        reason: 'unauthorized',
      });
    });

    it('una caída anormal (1006) reintenta con el backoff del intento actual', () => {
      expect(decideAfterClose(1006, 0, false, noJitter)).toEqual({
        action: 'retry',
        delayMs: 1000,
      });
      expect(decideAfterClose(1006, 3, false, noJitter)).toEqual({
        action: 'retry',
        delayMs: 8000,
      });
    });

    it('otros cierres del servidor (1000, 1001, 1008) también reintentan', () => {
      for (const code of [1000, 1001, 1008]) {
        expect(decideAfterClose(code, 0, false, noJitter).action).toBe('retry');
      }
    });

    it('el último reintento permitido es el número MAX - 1; el siguiente se rinde', () => {
      expect(decideAfterClose(1006, RECONNECT_MAX_ATTEMPTS - 1, false, noJitter).action).toBe(
        'retry',
      );
      expect(decideAfterClose(1006, RECONNECT_MAX_ATTEMPTS, false, noJitter)).toEqual({
        action: 'give-up',
        reason: 'exhausted',
      });
    });
  });
});

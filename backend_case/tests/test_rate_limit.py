"""
TokenBucket del canal de colaboración: ráfaga, recarga, tope de capacidad y calibración contra el
tráfico legítimo real del frontend (collaboration-tuning.ts / uml-editor.facade.ts).
"""

from backend_case.app.collaboration.rate_limit import MAX_MESSAGES_PER_SECOND, TokenBucket


class _Reloj:
    def __init__(self) -> None:
        self.ahora = 0.0

    def __call__(self) -> float:
        return self.ahora


def test_permite_la_rafaga_y_descarta_el_exceso():
    bucket = TokenBucket(rate_per_second=10, burst=3, clock=_Reloj())

    assert [bucket.allow() for _ in range(5)] == [True, True, True, False, False]


def test_se_recarga_con_el_paso_del_tiempo():
    reloj = _Reloj()
    bucket = TokenBucket(rate_per_second=10, burst=1, clock=reloj)
    assert bucket.allow() is True
    assert bucket.allow() is False

    reloj.ahora += 0.1  # 10/s -> 1 token cada 100 ms
    assert bucket.allow() is True
    assert bucket.allow() is False


def test_nunca_acumula_mas_que_la_capacidad():
    reloj = _Reloj()
    bucket = TokenBucket(rate_per_second=10, burst=3, clock=reloj)

    reloj.ahora += 1000  # una pausa larga no da derecho a una ráfaga mayor que `burst`

    assert [bucket.allow() for _ in range(5)] == [True, True, True, False, False]


def test_el_limite_configurado_no_descarta_el_trafico_legitimo_de_un_arrastre():
    """
    Arrastre de nodo (1 mensaje cada 33 ms) + cursor (1 cada 80 ms) a la vez durante 10 s
    (~43 mensajes/s): con el límite real ninguno debe descartarse.
    """
    reloj = _Reloj()
    bucket = TokenBucket(MAX_MESSAGES_PER_SECOND, burst=MAX_MESSAGES_PER_SECOND, clock=reloj)
    instantes = sorted(
        [i * 0.033 for i in range(int(10 / 0.033))] + [i * 0.080 for i in range(int(10 / 0.080))]
    )

    descartados = 0
    for instante in instantes:
        reloj.ahora = instante
        if not bucket.allow():
            descartados += 1

    assert descartados == 0


def test_un_flujo_abusivo_si_es_frenado():
    reloj = _Reloj()
    bucket = TokenBucket(MAX_MESSAGES_PER_SECOND, burst=MAX_MESSAGES_PER_SECOND, clock=reloj)

    permitidos = sum(bucket.allow() for _ in range(1000))  # 1000 mensajes en el mismo instante

    assert permitidos == MAX_MESSAGES_PER_SECOND

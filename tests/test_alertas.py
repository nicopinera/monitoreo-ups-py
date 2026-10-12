import pytest

import config.configuracion as c
from core.alertas import Regla, evaluar
from core.errores import Errores

MAXIMO = Regla("load", Errores.LOAD_MAXIMO, "max", 60, "%")
MINIMO = Regla("capacity", Errores.CARGA_MINIMA, "min", 70, "%")


@pytest.mark.parametrize(("valor", "esperado"), [(59, False), (60, False), (61, True)])
def test_regla_de_maximo_alerta_solo_por_encima_del_umbral(valor: int, esperado: bool) -> None:
    assert MAXIMO.en_alerta(valor) is esperado


@pytest.mark.parametrize(("valor", "esperado"), [(71, False), (70, False), (69.5, True)])
def test_regla_de_minimo_alerta_solo_por_debajo_del_umbral(valor: float, esperado: bool) -> None:
    assert MINIMO.en_alerta(valor) is esperado


def test_evaluar_devuelve_un_chequeo_por_regla_con_dato() -> None:
    chequeos = evaluar([MAXIMO, MINIMO], {"load": 75, "capacity": 100})

    assert [(ch.regla.error, ch.valor, ch.en_alerta) for ch in chequeos] == [
        (Errores.LOAD_MAXIMO, 75, True),
        (Errores.CARGA_MINIMA, 100, False),
    ]


def test_metrica_sin_dato_no_genera_chequeo() -> None:
    # Un dato faltante no es "todo bien": no debe resolver un error abierto
    assert evaluar([MAXIMO, MINIMO], {"load": None}) == []


# ------------------------------------------------------------------ reglas de los UPS


def errores_en_alerta(**datos: float) -> set[Errores]:
    return {ch.regla.error for ch in evaluar(c.REGLAS_UPS, datos) if ch.en_alerta}


def test_ups_sano_no_tiene_alertas() -> None:
    assert errores_en_alerta(battery=25, temp=22, capacity=100, load=40, life=25) == set()


@pytest.mark.parametrize(
    ("metrica", "valor", "error"),
    [
        ("battery", 29, Errores.TEMPERATURA_BATERIA_ALTA),
        ("temp", 29, Errores.UIO_TEMPERATURA_ALTA),
        ("temp", -1, Errores.UIO_ROTO),
        ("capacity", 69, Errores.CARGA_MINIMA),
        ("load", 61, Errores.LOAD_MAXIMO),
        ("life", 8.9, Errores.AUTONOMIA_MINIMO),
    ],
)
def test_cada_regla_de_los_ups(metrica: str, valor: float, error: Errores) -> None:
    assert errores_en_alerta(**{metrica: valor}) == {error}


def test_sensor_roto_y_temperatura_alta_son_independientes() -> None:
    # Las dos reglas leen "temp": un sensor roto no es temperatura alta, y viceversa
    chequeos = evaluar(c.REGLAS_UPS, {"temp": -1})
    assert {ch.regla.error: ch.en_alerta for ch in chequeos} == {
        Errores.UIO_ROTO: True,
        Errores.UIO_TEMPERATURA_ALTA: False,
    }


def test_cada_error_tiene_una_sola_regla() -> None:
    # El estado se guarda por error: dos reglas del mismo error se pisarian
    errores = [regla.error for regla in c.REGLAS_UPS]
    assert len(errores) == len(set(errores))

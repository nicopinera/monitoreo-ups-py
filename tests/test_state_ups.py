from collections.abc import Mapping

import pytest

import config.configuracion as c
from core.alertas import Numero
from core.errores import Errores
from core.ups_base import Lectura
from drivers.state_ups import StateUPS
from tests.dobles import ClienteSNMPFalso

HOST = "ups-test"

# Respuestas crudas de un UPS sano (todas dentro de los umbrales)
RESPUESTAS_OK = {
    c.OIDB: "25",
    c.OIDCAPACITY: "100",
    c.OIDLOAD: "40",
    c.OIDLIFE: "150000",  # TimeTicks -> 25.0 min
    c.OIDCURRENT: "6",
    c.OIDT: "22",
}

LINEA_OK = f"ups_temp2,host={HOST} battery=25,temp=22,capacity=100,load=40,life=25.0,current=6"

Respuestas = Mapping[str, str | None]


def leer(respuestas: Respuestas) -> Lectura:
    cliente = ClienteSNMPFalso(respuestas)
    return StateUPS(HOST, cliente, c.OID_UPS, (c.OIDT, c.OIDTNEW), c.REGLAS_UPS).ejecutar()


def test_todos_los_datos_devuelve_la_linea_completa_sin_imprimir(
    capsys: pytest.CaptureFixture[str],
) -> None:
    lectura = leer(RESPUESTAS_OK)

    assert lectura.lineas == [LINEA_OK]
    assert lectura.hay_datos
    assert capsys.readouterr().out == ""  # la salida la escribe main


def test_equipo_se_identifica_por_su_hostname() -> None:
    equipo = leer(RESPUESTAS_OK).equipo
    assert (equipo.hostname, equipo.tipo, equipo.clave) == (HOST, "UPS", HOST)


def test_campos_sin_dato_se_omiten() -> None:
    respuestas = dict(RESPUESTAS_OK)
    del respuestas[c.OIDCURRENT]
    del respuestas[c.OIDT]  # sin OIDT ni OIDTNEW -> sin temperatura UIO

    assert leer(respuestas).lineas == [
        f"ups_temp2,host={HOST} battery=25,capacity=100,load=40,life=25.0"
    ]


def test_fallback_a_oidtnew_si_oidt_no_existe() -> None:
    respuestas = dict(RESPUESTAS_OK, **{c.OIDT: "NOSUCHINSTANCE", c.OIDTNEW: "23"})
    assert "temp=23" in leer(respuestas).lineas[0]


def test_evalua_las_reglas_con_los_datos_leidos() -> None:
    lectura = leer(dict(RESPUESTAS_OK, **{c.OIDCAPACITY: "50"}))

    en_alerta = {ch.regla.error: ch.valor for ch in lectura.chequeos if ch.en_alerta}
    assert en_alerta == {Errores.CARGA_MINIMA: 50}
    # life se evalua en minutos, ya convertido
    autonomia = next(ch for ch in lectura.chequeos if ch.regla.error == Errores.AUTONOMIA_MINIMO)
    assert autonomia.valor == 25.0


def test_metrica_sin_dato_no_se_evalua() -> None:
    respuestas = dict(RESPUESTAS_OK)
    del respuestas[c.OIDCAPACITY]

    errores = {ch.regla.error for ch in leer(respuestas).chequeos}
    assert Errores.CARGA_MINIMA not in errores


def test_sin_respuesta_no_devuelve_lineas_ni_chequeos() -> None:
    lectura = leer({})
    assert (lectura.lineas, lectura.hay_datos, lectura.chequeos) == ([], False, [])


def test_agente_que_responde_todo_nosuch_cuenta_como_sin_respuesta() -> None:
    respuestas = {oid: "NOSUCHOBJECT" for oid in [*RESPUESTAS_OK, c.OIDTNEW]}
    assert leer(respuestas).hay_datos is False


class ClienteQueExplota(ClienteSNMPFalso):
    def obtener_valor_numerico(self, oid: str) -> Numero | None:
        raise RuntimeError("error inesperado")


def test_excepcion_inesperada_se_propaga_a_main() -> None:
    # El driver no atrapa excepciones: las registra main (ver test_main.py) y sigue con el resto
    driver = StateUPS(HOST, ClienteQueExplota(), c.OID_UPS, (c.OIDT,))
    with pytest.raises(RuntimeError, match="error inesperado"):
        driver.ejecutar()

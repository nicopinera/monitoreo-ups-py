import pytest

import config.configuracion as c
from core.ups_base import Lectura
from drivers.hum_ups import HumedadUPS
from tests.dobles import ClienteSNMPFalso

HOST = "f2r7u1"


def ejecutar(respuestas: dict[str, str]) -> list[str]:
    return leer(respuestas).lineas


def leer(respuestas: dict[str, str]) -> Lectura:
    return HumedadUPS(HOST, ClienteSNMPFalso(respuestas), {"humidity": c.OID_HUMEDAD}).ejecutar()


def test_con_dato_devuelve_la_linea_sin_imprimir(capsys: pytest.CaptureFixture[str]) -> None:
    assert ejecutar({c.OID_HUMEDAD: "45"}) == [f"ups_temp2,host={HOST} humidity=45"]
    assert capsys.readouterr().out == ""  # la salida la escribe main


def test_sin_respuesta_no_devuelve_lineas() -> None:
    assert ejecutar({}) == []


def test_valor_no_numerico_no_devuelve_lineas() -> None:
    assert ejecutar({c.OID_HUMEDAD: "NOSUCHOBJECT"}) == []


def test_sin_respuesta_lo_informa_para_alertar() -> None:
    assert leer({}).hay_datos is False


def test_sus_alertas_no_se_mezclan_con_las_del_ups_del_mismo_host() -> None:
    # El sensor vive en un UPS que tambien se monitorea: otra clave para incidentes e hilos
    equipo = leer({c.OID_HUMEDAD: "45"}).equipo
    assert (equipo.hostname, equipo.tipo) == (HOST, "Sensor de humedad")
    assert equipo.clave != HOST
    # Y no tiene reglas: solo puede alertar SIN_RESPUESTA_SNMP
    assert leer({c.OID_HUMEDAD: "99"}).chequeos == []

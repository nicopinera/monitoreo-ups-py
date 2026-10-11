import pytest

import config.configuracion as c
from drivers.hum_ups import HumedadUPS
from tests.dobles import ClienteSNMPFalso

HOST = "f2r7u1"


def ejecutar(respuestas: dict[str, str]) -> list[str]:
    return HumedadUPS(HOST, ClienteSNMPFalso(respuestas)).ejecutar(c.OID_HUMEDAD)


def test_con_dato_devuelve_la_linea_sin_imprimir(capsys: pytest.CaptureFixture[str]) -> None:
    assert ejecutar({c.OID_HUMEDAD: "45"}) == [f"ups_temp2,host={HOST} humidity=45"]
    assert capsys.readouterr().out == ""  # la salida la escribe main


def test_sin_respuesta_no_devuelve_lineas() -> None:
    assert ejecutar({}) == []


def test_valor_no_numerico_no_devuelve_lineas() -> None:
    assert ejecutar({c.OID_HUMEDAD: "NOSUCHOBJECT"}) == []

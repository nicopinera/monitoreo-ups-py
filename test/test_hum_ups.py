import config.configuracion as c
from drivers.hum_ups import HumedadUPS
from test.conftest import ClienteSNMPFalso

HOST = "f2r7u1"


def ejecutar(respuestas):
    HumedadUPS(HOST, ClienteSNMPFalso(respuestas)).ejecutar(c.OID_HUMEDAD)


def test_con_dato_imprime_la_linea(capsys):
    ejecutar({c.OID_HUMEDAD: "45"})

    assert capsys.readouterr().out == f"ups_temp2,host={HOST} humidity=45\n"


def test_sin_respuesta_no_imprime(capsys):
    ejecutar({})

    assert capsys.readouterr().out == ""


def test_valor_no_numerico_no_imprime(capsys):
    ejecutar({c.OID_HUMEDAD: "NOSUCHOBJECT"})

    assert capsys.readouterr().out == ""

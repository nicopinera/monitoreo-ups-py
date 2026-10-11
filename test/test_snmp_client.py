import logging

import pytest
from easysnmp import EasySNMPTimeoutError

import config.configuracion as c
import infraestructura.snmp_client as modulo_snmp
from infraestructura.snmp_client import ClienteSNMP
from test.conftest import ClienteSNMPFalso

OID = "1.2.3"


@pytest.mark.parametrize(
    ("crudo", "esperado"),
    [
        ("27", 27),
        ("-1", -1),
        ("12.5", 12.5),
        (None, None),  # timeout / error SNMP
        ("NOSUCHOBJECT", None),
        ("NOSUCHINSTANCE", None),
        ("", None),
        ("nan", None),
        ("inf", None),
    ],
)
def test_obtener_valor_numerico(crudo, esperado):
    cliente = ClienteSNMPFalso({OID: crudo})

    assert cliente.obtener_valor_numerico(OID) == esperado


def test_entero_se_mantiene_como_int():
    # Mantiene la representacion actual en line protocol ("27", no "27.0")
    assert isinstance(ClienteSNMPFalso({OID: "27"}).obtener_valor_numerico(OID), int)


class SesionFalsa:
    """
    Reemplazo de easysnmp.Session. Por cada OID responde el valor indicado o lanza la excepcion.
    Registra los OIDs consultados.
    """

    def __init__(self, excepcion=None, respuestas=None):
        self.excepcion = excepcion
        self.respuestas = respuestas or {}
        self.consultas = []

    def get(self, oid):
        self.consultas.append(oid)
        respuesta = self.respuestas.get(oid, self.excepcion)
        if isinstance(respuesta, Exception):
            raise respuesta
        return VariableFalsa(respuesta)


class VariableFalsa:
    def __init__(self, value):
        self.value = value


def cliente_con_sesion(sesion):
    # Se evita el constructor real para no crear una sesion SNMP de verdad
    cliente = ClienteSNMP.__new__(ClienteSNMP)
    cliente.fullhostname = "ups-test.psi.unc.edu.ar"
    cliente.session = sesion
    cliente.logger = logging.getLogger("infraestructura.snmp_client")
    cliente.sin_respuesta = False
    return cliente


def test_timeout_se_registra_y_devuelve_none(caplog):
    cliente = cliente_con_sesion(SesionFalsa(EasySNMPTimeoutError("timeout")))

    with caplog.at_level(logging.WARNING):
        assert cliente.obtener_valor(OID) is None

    assert "Timeout SNMP en ups-test.psi.unc.edu.ar (oid=1.2.3)" in caplog.text


def test_error_generico_se_registra_y_devuelve_none(caplog):
    cliente = cliente_con_sesion(SesionFalsa(RuntimeError("fallo raro")))

    with caplog.at_level(logging.ERROR):
        assert cliente.obtener_valor(OID) is None

    assert "fallo raro" in caplog.text


def test_despues_de_un_timeout_no_consulta_mas_oids_del_host(caplog):
    sesion = SesionFalsa(EasySNMPTimeoutError("timeout"))
    cliente = cliente_con_sesion(sesion)

    with caplog.at_level(logging.WARNING):
        valores = [cliente.obtener_valor(oid) for oid in ("1.1", "1.2", "1.3")]

    assert valores == [None, None, None]
    assert sesion.consultas == ["1.1"]  # solo se espero el timeout del primero
    assert caplog.text.count("Timeout SNMP") == 1  # un warning por host, no por OID


def test_nosuch_no_corta_las_consultas():
    # El equipo responde aunque el OID no exista: se sigue (de esto depende el fallback a OIDTNEW)
    sesion = SesionFalsa(respuestas={"1.1": "NOSUCHINSTANCE", "1.2": "23"})
    cliente = cliente_con_sesion(sesion)

    assert cliente.obtener_valor_numerico("1.1") is None
    assert cliente.obtener_valor_numerico("1.2") == 23
    assert sesion.consultas == ["1.1", "1.2"]


def test_error_generico_no_corta_las_consultas():
    sesion = SesionFalsa(respuestas={"1.1": RuntimeError("fallo raro"), "1.2": "5"})
    cliente = cliente_con_sesion(sesion)

    assert cliente.obtener_valor("1.1") is None
    assert cliente.obtener_valor("1.2") == "5"


def test_la_sesion_usa_timeout_y_reintentos_de_la_configuracion(monkeypatch):
    parametros = {}
    monkeypatch.setattr(modulo_snmp, "Session", lambda **kwargs: parametros.update(kwargs))

    ClienteSNMP("ups-test")

    assert parametros["timeout"] == c.SNMP_TIMEOUT
    assert parametros["retries"] == c.SNMP_RETRIES
    assert parametros["hostname"] == "ups-test" + c.SUFIJO

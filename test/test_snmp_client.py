import logging

import pytest
from easysnmp import EasySNMPTimeoutError

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
    """Reemplazo de easysnmp.Session cuyo get lanza la excepcion indicada."""

    def __init__(self, excepcion):
        self.excepcion = excepcion

    def get(self, oid):
        raise self.excepcion


def cliente_con_sesion(sesion):
    # Se evita el constructor real para no crear una sesion SNMP de verdad
    cliente = ClienteSNMP.__new__(ClienteSNMP)
    cliente.fullhostname = "ups-test.psi.unc.edu.ar"
    cliente.session = sesion
    cliente.logger = logging.getLogger("infraestructura.snmp_client")
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

import pytest
from test.conftest import ClienteSNMPFalso

OID = "1.2.3"


@pytest.mark.parametrize(
    ("crudo", "esperado"),
    [
        ("27", 27),
        ("-1", -1),
        ("12.5", 12.5),
        (None, None),             # timeout / error SNMP
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

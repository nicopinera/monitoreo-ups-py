import config.configuracion as c
from drivers.dc_ups import DataCenterUPS
from test.conftest import ClienteSNMPFalso

HOST = "ups-dc"

RESPUESTAS_OK = {
    c.OID_AUTONOMIA: "600",  # segundos -> 10.0 min
    c.OID_CARGA_BATERIA: "100",
    c.OID_TEMP_BATERIA: "24",
    c.OID_CARGA_OUT: "35",
    c.OID_CORRIENTE_OUT_F1: "10",
    c.OID_CORRIENTE_OUT_F2: "20",
    c.OID_CORRIENTE_OUT_F3: "30",
    c.OID_VOLTAJE_OUT: "220",  # mismo OID que OID_V_OUT_AN
    c.OID_V_OUT_BN: "221",
    c.OID_V_OUT_CN: "222",
    c.OID_V_AN: "219",
    c.OID_V_BN: "220",
    c.OID_V_CN: "221",
}


def ejecutar(respuestas):
    driver = DataCenterUPS(HOST, ClienteSNMPFalso(respuestas))
    driver.ejecutar(c.OID_DC)
    return driver


def test_todos_los_datos_imprime_todas_las_lineas(capsys):
    ejecutar(RESPUESTAS_OK)

    total_va = 220 * 10 + 221 * 20 + 222 * 30
    assert capsys.readouterr().out.splitlines() == [
        f"dc-ups,host={HOST} autonomia=10.0",
        f"dc-ups,host={HOST} carga_bat=100",
        f"dc-ups,host={HOST} bat_temp=24",
        f"dc-ups,host={HOST} carga_out=35",
        f"dc-ups,host={HOST} corriente_out_f1=10,corriente_out_f2=20,corriente_out_f3=30,corriente_prom=20.0",
        f"dc-ups,host={HOST} voltaje_out=220,voltaje_out_an=220,voltaje_out_bn=221,voltaje_out_cn=222",
        f"dc-ups,host={HOST} voltaje_an_input=219,voltaje_bn_input=220,voltaje_cn_input=221",
        f"dc-ups,host={HOST} potencia_va_out_a=2200,potencia_va_out_b=4420,potencia_va_out_c=6660,"
        f"potencia_va_out={total_va},potencia_w_out={total_va * c.FP_OUT}",
    ]


def test_fase_sin_corriente_omite_su_potencia_y_los_totales(capsys):
    respuestas = dict(RESPUESTAS_OK)
    del respuestas[c.OID_CORRIENTE_OUT_F3]

    ejecutar(respuestas)

    salida = capsys.readouterr().out.splitlines()
    assert f"dc-ups,host={HOST} corriente_out_f1=10,corriente_out_f2=20" in salida
    assert f"dc-ups,host={HOST} potencia_va_out_a=2200,potencia_va_out_b=4420" in salida


def test_valor_no_numerico_no_aborta(capsys):
    respuestas = dict(RESPUESTAS_OK, **{c.OID_CARGA_BATERIA: "NOSUCHINSTANCE"})

    ejecutar(respuestas)

    salida = capsys.readouterr().out
    assert "carga_bat" not in salida
    assert f"dc-ups,host={HOST} autonomia=10.0" in salida


def test_sin_respuesta_no_imprime_nada(capsys):
    ejecutar({})

    assert capsys.readouterr().out == ""

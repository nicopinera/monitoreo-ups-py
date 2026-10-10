import sqlite3

import pytest

import config.configuracion as c
from core.errores import Errores
from drivers.state_ups import StateUPS
from test.conftest import ClienteSNMPFalso

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


def crear_driver(respuestas, notificador, repo_db):
    return StateUPS(HOST, ClienteSNMPFalso(respuestas), notificador=notificador, rep_db=repo_db)


def ejecutar(respuestas, notificador, repo_db):
    """Devuelve las lineas de telegraf del UPS."""
    return crear_driver(respuestas, notificador, repo_db).ejecutar(c.OID_UPS, c.OIDT, c.OIDTNEW)


def test_todos_los_datos_devuelve_la_linea_completa_sin_imprimir(capsys, notificador, repo_db):
    assert ejecutar(RESPUESTAS_OK, notificador, repo_db) == [LINEA_OK]
    assert capsys.readouterr().out == ""  # la salida la escribe main
    assert notificador.mensajes == []


def test_campos_sin_dato_se_omiten(notificador, repo_db):
    respuestas = dict(RESPUESTAS_OK)
    del respuestas[c.OIDCURRENT]
    del respuestas[c.OIDT]  # sin OIDT ni OIDTNEW -> sin temperatura UIO

    assert ejecutar(respuestas, notificador, repo_db) == [
        f"ups_temp2,host={HOST} battery=25,capacity=100,load=40,life=25.0"
    ]
    assert notificador.mensajes == []


def test_metrica_sin_dato_no_resuelve_su_error_activo(notificador, repo_db):
    repo_db.agregar_error(HOST, Errores.CARGA_MINIMA.name)
    respuestas = dict(RESPUESTAS_OK)
    del respuestas[c.OIDCAPACITY]

    ejecutar(respuestas, notificador, repo_db)

    assert repo_db.error_activo(HOST, Errores.CARGA_MINIMA.name) is not None
    assert notificador.mensajes == []


def test_metrica_con_dato_sigue_alertando(notificador, repo_db):
    respuestas = dict(RESPUESTAS_OK, **{c.OIDCAPACITY: "50"})

    ejecutar(respuestas, notificador, repo_db)

    assert len(notificador.mensajes) == 1
    assert Errores.CARGA_MINIMA.name in notificador.mensajes[0]


def test_fallback_a_oidtnew_si_oidt_no_existe(notificador, repo_db):
    respuestas = dict(RESPUESTAS_OK, **{c.OIDT: "NOSUCHINSTANCE", c.OIDTNEW: "23"})

    lineas = ejecutar(respuestas, notificador, repo_db)

    assert "temp=23" in lineas[0]


def test_sin_respuesta_no_devuelve_lineas_y_avisa_una_sola_vez(notificador, repo_db):
    assert ejecutar({}, notificador, repo_db) == []
    assert len(notificador.mensajes) == 1
    assert Errores.SIN_RESPUESTA_SNMP.name in notificador.mensajes[0]
    # Con todo en None no se disparan las alertas falsas de antes
    assert Errores.CARGA_MINIMA.name not in notificador.mensajes[0]
    assert Errores.AUTONOMIA_MINIMO.name not in notificador.mensajes[0]

    # Segunda ejecucion sin respuesta: no se vuelve a avisar
    ejecutar({}, notificador, repo_db)
    assert len(notificador.mensajes) == 1


def test_sin_respuesta_se_resuelve_cuando_vuelve(notificador, repo_db):
    ejecutar({}, notificador, repo_db)
    ejecutar(RESPUESTAS_OK, notificador, repo_db)

    assert len(notificador.mensajes) == 2
    assert f"[RESUELTO] {Errores.SIN_RESPUESTA_SNMP.name}" in notificador.mensajes[1]
    assert repo_db.error_activo(HOST, Errores.SIN_RESPUESTA_SNMP.name) is None


def test_sin_respuesta_no_resuelve_otros_errores_activos(notificador, repo_db):
    repo_db.agregar_error(HOST, Errores.TEMPERATURA_BATERIA_ALTA.name)

    ejecutar({}, notificador, repo_db)

    assert repo_db.error_activo(HOST, Errores.TEMPERATURA_BATERIA_ALTA.name) is not None
    assert "RESUELTO" not in notificador.mensajes[0]


def test_agente_que_responde_todo_nosuch_cuenta_como_sin_respuesta(notificador, repo_db):
    respuestas = {oid: "NOSUCHOBJECT" for oid in RESPUESTAS_OK}
    respuestas[c.OIDTNEW] = "NOSUCHOBJECT"

    assert ejecutar(respuestas, notificador, repo_db) == []
    assert Errores.SIN_RESPUESTA_SNMP.name in notificador.mensajes[0]


class ClienteQueExplota(ClienteSNMPFalso):
    def obtener_valor_numerico(self, oid):
        raise RuntimeError("error inesperado")


def test_excepcion_inesperada_se_propaga_a_main(notificador, repo_db):
    # El driver no atrapa excepciones: las registra main (ver test_main.py) y sigue con el resto
    driver = StateUPS(HOST, ClienteQueExplota(), notificador=notificador, rep_db=repo_db)

    with pytest.raises(RuntimeError, match="error inesperado"):
        driver.ejecutar(c.OID_UPS, c.OIDT, c.OIDTNEW)


class RepositorioQueExplota:
    def error_activo(self, ups_host, tipo_error):
        raise sqlite3.OperationalError("database is locked")


def test_si_falla_la_validacion_las_metricas_se_devuelven_igual(caplog, notificador):
    lineas = ejecutar(RESPUESTAS_OK, notificador, RepositorioQueExplota())

    assert lineas == [LINEA_OK]
    assert f"Error al validar o notificar {HOST}" in caplog.text
    assert "database is locked" in caplog.text  # el traceback queda en el log

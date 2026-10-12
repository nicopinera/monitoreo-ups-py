import sqlite3
from collections.abc import Mapping
from contextlib import closing

import pytest

import config.configuracion as c
from core.errores import Errores
from drivers.state_ups import StateUPS
from infraestructura.database import Incidente, RepositorioDB
from infraestructura.snmp_client import Numero
from tests.dobles import ClienteSNMPFalso, NotificadorFalso

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


def crear_driver(
    respuestas: Respuestas, notificador: NotificadorFalso, repo_db: RepositorioDB
) -> StateUPS:
    return StateUPS(HOST, ClienteSNMPFalso(respuestas), notificador=notificador, rep_db=repo_db)


def ejecutar(
    respuestas: Respuestas, notificador: NotificadorFalso, repo_db: RepositorioDB
) -> list[str]:
    """Devuelve las lineas de telegraf del UPS."""
    return crear_driver(respuestas, notificador, repo_db).ejecutar(c.OID_UPS, c.OIDT, c.OIDTNEW)


def test_todos_los_datos_devuelve_la_linea_completa_sin_imprimir(
    capsys: pytest.CaptureFixture[str], notificador: NotificadorFalso, repo_db: RepositorioDB
) -> None:
    assert ejecutar(RESPUESTAS_OK, notificador, repo_db) == [LINEA_OK]
    assert capsys.readouterr().out == ""  # la salida la escribe main
    assert notificador.mensajes == []


def test_campos_sin_dato_se_omiten(notificador: NotificadorFalso, repo_db: RepositorioDB) -> None:
    respuestas = dict(RESPUESTAS_OK)
    del respuestas[c.OIDCURRENT]
    del respuestas[c.OIDT]  # sin OIDT ni OIDTNEW -> sin temperatura UIO

    assert ejecutar(respuestas, notificador, repo_db) == [
        f"ups_temp2,host={HOST} battery=25,capacity=100,load=40,life=25.0"
    ]
    assert notificador.mensajes == []


def test_metrica_sin_dato_no_resuelve_su_error_activo(
    notificador: NotificadorFalso, repo_db: RepositorioDB
) -> None:
    repo_db.abrir_incidente(HOST, Errores.CARGA_MINIMA.name)
    respuestas = dict(RESPUESTAS_OK)
    del respuestas[c.OIDCAPACITY]

    ejecutar(respuestas, notificador, repo_db)

    assert repo_db.incidente_abierto(HOST, Errores.CARGA_MINIMA.name) is not None
    assert notificador.mensajes == []


def test_metrica_con_dato_sigue_alertando(
    notificador: NotificadorFalso, repo_db: RepositorioDB
) -> None:
    respuestas = dict(RESPUESTAS_OK, **{c.OIDCAPACITY: "50"})

    ejecutar(respuestas, notificador, repo_db)

    assert len(notificador.mensajes) == 1
    assert Errores.CARGA_MINIMA.name in notificador.mensajes[0]


def test_fallback_a_oidtnew_si_oidt_no_existe(
    notificador: NotificadorFalso, repo_db: RepositorioDB
) -> None:
    respuestas = dict(RESPUESTAS_OK, **{c.OIDT: "NOSUCHINSTANCE", c.OIDTNEW: "23"})

    lineas = ejecutar(respuestas, notificador, repo_db)

    assert "temp=23" in lineas[0]


def test_sin_respuesta_no_devuelve_lineas_y_avisa_una_sola_vez(
    notificador: NotificadorFalso, repo_db: RepositorioDB
) -> None:
    assert ejecutar({}, notificador, repo_db) == []
    assert len(notificador.mensajes) == 1
    assert Errores.SIN_RESPUESTA_SNMP.name in notificador.mensajes[0]
    # Con todo en None no se disparan las alertas falsas de antes
    assert Errores.CARGA_MINIMA.name not in notificador.mensajes[0]
    assert Errores.AUTONOMIA_MINIMO.name not in notificador.mensajes[0]

    # Segunda ejecucion sin respuesta: no se vuelve a avisar
    ejecutar({}, notificador, repo_db)
    assert len(notificador.mensajes) == 1


def test_sin_respuesta_se_resuelve_cuando_vuelve(
    notificador: NotificadorFalso, repo_db: RepositorioDB
) -> None:
    ejecutar({}, notificador, repo_db)
    ejecutar(RESPUESTAS_OK, notificador, repo_db)

    assert len(notificador.mensajes) == 2
    assert f"[RESUELTO] {Errores.SIN_RESPUESTA_SNMP.name}" in notificador.mensajes[1]
    assert repo_db.incidente_abierto(HOST, Errores.SIN_RESPUESTA_SNMP.name) is None


def test_sin_respuesta_no_resuelve_otros_errores_activos(
    notificador: NotificadorFalso, repo_db: RepositorioDB
) -> None:
    repo_db.abrir_incidente(HOST, Errores.TEMPERATURA_BATERIA_ALTA.name)

    ejecutar({}, notificador, repo_db)

    assert repo_db.incidente_abierto(HOST, Errores.TEMPERATURA_BATERIA_ALTA.name) is not None
    assert "RESUELTO" not in notificador.mensajes[0]


def test_agente_que_responde_todo_nosuch_cuenta_como_sin_respuesta(
    notificador: NotificadorFalso, repo_db: RepositorioDB
) -> None:
    respuestas = {oid: "NOSUCHOBJECT" for oid in RESPUESTAS_OK}
    respuestas[c.OIDTNEW] = "NOSUCHOBJECT"

    assert ejecutar(respuestas, notificador, repo_db) == []
    assert Errores.SIN_RESPUESTA_SNMP.name in notificador.mensajes[0]


class ClienteQueExplota(ClienteSNMPFalso):
    def obtener_valor_numerico(self, oid: str) -> Numero | None:
        raise RuntimeError("error inesperado")


def test_excepcion_inesperada_se_propaga_a_main(
    notificador: NotificadorFalso, repo_db: RepositorioDB
) -> None:
    # El driver no atrapa excepciones: las registra main (ver test_main.py) y sigue con el resto
    driver = StateUPS(HOST, ClienteQueExplota(), notificador=notificador, rep_db=repo_db)

    with pytest.raises(RuntimeError, match="error inesperado"):
        driver.ejecutar(c.OID_UPS, c.OIDT, c.OIDTNEW)


class RepositorioQueExplota(RepositorioDB):
    def __init__(self) -> None:
        # No se llama al constructor real: no hace falta una base
        pass

    def reiniciar_fallas(self, ups_host: str, tipo_error: str) -> None:
        raise sqlite3.OperationalError("database is locked")

    def incidente_abierto(self, ups_host: str, tipo_error: str) -> Incidente | None:
        raise sqlite3.OperationalError("database is locked")


def test_si_falla_la_validacion_las_metricas_se_devuelven_igual(
    caplog: pytest.LogCaptureFixture, notificador: NotificadorFalso
) -> None:
    lineas = ejecutar(RESPUESTAS_OK, notificador, RepositorioQueExplota())

    assert lineas == [LINEA_OK]
    assert f"Error al validar o notificar {HOST}" in caplog.text
    assert "database is locked" in caplog.text  # el traceback queda en el log


# ------------------------------------------------------------------ A8: no perder alertas


def test_si_falla_el_envio_no_se_guarda_el_error(
    caplog: pytest.LogCaptureFixture, notificador: NotificadorFalso, repo_db: RepositorioDB
) -> None:
    notificador.falla = True
    respuestas = dict(RESPUESTAS_OK, **{c.OIDCAPACITY: "50"})

    ejecutar(respuestas, notificador, repo_db)

    assert repo_db.incidente_abierto(HOST, Errores.CARGA_MINIMA.name) is None
    assert f"No se pudo notificar {HOST} (CARGA_MINIMA)" in caplog.text


def test_si_el_error_persiste_se_reenvia_y_recien_ahi_se_guarda(
    notificador: NotificadorFalso, repo_db: RepositorioDB
) -> None:
    respuestas = dict(RESPUESTAS_OK, **{c.OIDCAPACITY: "50"})

    notificador.falla = True
    ejecutar(respuestas, notificador, repo_db)  # Google Chat caido: no llega ni se guarda
    notificador.falla = False
    ejecutar(respuestas, notificador, repo_db)  # se detecta otra vez y llega

    assert len(notificador.mensajes) == 1
    assert Errores.CARGA_MINIMA.name in notificador.mensajes[0]
    assert repo_db.incidente_abierto(HOST, Errores.CARGA_MINIMA.name) is not None

    ejecutar(respuestas, notificador, repo_db)  # ya avisado: no se repite
    assert len(notificador.mensajes) == 1


def test_si_el_error_se_resuelve_antes_del_reintento_no_se_envia_nada(
    notificador: NotificadorFalso, repo_db: RepositorioDB
) -> None:
    notificador.falla = True
    ejecutar(dict(RESPUESTAS_OK, **{c.OIDCAPACITY: "50"}), notificador, repo_db)
    notificador.falla = False
    ejecutar(RESPUESTAS_OK, notificador, repo_db)

    assert notificador.mensajes == []
    assert repo_db.incidente_abierto(HOST, Errores.CARGA_MINIMA.name) is None


def test_si_falla_el_envio_de_la_resolucion_el_error_sigue_activo(
    notificador: NotificadorFalso, repo_db: RepositorioDB
) -> None:
    repo_db.abrir_incidente(HOST, Errores.CARGA_MINIMA.name)

    notificador.falla = True
    ejecutar(RESPUESTAS_OK, notificador, repo_db)
    assert repo_db.incidente_abierto(HOST, Errores.CARGA_MINIMA.name) is not None

    notificador.falla = False
    ejecutar(RESPUESTAS_OK, notificador, repo_db)
    assert repo_db.incidente_abierto(HOST, Errores.CARGA_MINIMA.name) is None
    assert f"[RESUELTO] {Errores.CARGA_MINIMA.name}" in notificador.mensajes[0]


def test_varias_alertas_salen_en_un_mensaje_y_se_guardan_todas_o_ninguna(
    notificador: NotificadorFalso, repo_db: RepositorioDB
) -> None:
    respuestas = dict(RESPUESTAS_OK, **{c.OIDCAPACITY: "50", c.OIDLOAD: "90"})
    errores = (Errores.CARGA_MINIMA.name, Errores.LOAD_MAXIMO.name)

    notificador.falla = True
    ejecutar(respuestas, notificador, repo_db)
    assert all(repo_db.incidente_abierto(HOST, e) is None for e in errores)

    notificador.falla = False
    ejecutar(respuestas, notificador, repo_db)
    assert len(notificador.mensajes) == 1
    assert all(e in notificador.mensajes[0] for e in errores)
    assert all(repo_db.incidente_abierto(HOST, e) is not None for e in errores)


def test_error_resuelto_que_vuelve_abre_un_incidente_nuevo(
    notificador: NotificadorFalso, repo_db: RepositorioDB
) -> None:
    alto = dict(RESPUESTAS_OK, **{c.OIDCAPACITY: "50"})
    ejecutar(alto, notificador, repo_db)
    ejecutar(RESPUESTAS_OK, notificador, repo_db)
    ejecutar(alto, notificador, repo_db)

    with closing(sqlite3.connect(repo_db.db_file)) as conn:
        abiertos = conn.execute(
            "SELECT fin IS NULL FROM incidentes WHERE ups_host=? AND tipo_error=? ORDER BY id",
            (HOST, Errores.CARGA_MINIMA.name),
        ).fetchall()
    assert abiertos == [(0,), (1,)]  # el primero cerrado (historial), el segundo abierto
    assert len(notificador.mensajes) == 3


def test_notificador_y_repositorio_son_obligatorios() -> None:
    with pytest.raises(TypeError):
        # mypy tambien lo detecta antes de ejecutar: por eso se ignora el error de tipos
        StateUPS(HOST, ClienteSNMPFalso({}))  # type: ignore[call-arg]


# ------------------------------------------------------------------ fallas seguidas sin respuesta


def ejecutar_con_umbral(
    respuestas: Respuestas, notificador: NotificadorFalso, repo_db: RepositorioDB, umbral: int
) -> list[str]:
    driver = StateUPS(
        HOST,
        ClienteSNMPFalso(respuestas),
        notificador=notificador,
        rep_db=repo_db,
        fallas_para_alerta=umbral,
    )
    return driver.ejecutar(c.OID_UPS, c.OIDT, c.OIDTNEW)


def test_sin_respuesta_avisa_recien_despues_de_n_fallas_seguidas(
    caplog: pytest.LogCaptureFixture, notificador: NotificadorFalso, repo_db: RepositorioDB
) -> None:
    caplog.set_level("INFO")
    for _ in range(2):
        ejecutar_con_umbral({}, notificador, repo_db, umbral=3)
    assert notificador.mensajes == []
    assert f"{HOST} sin respuesta SNMP (2 de 3 ejecuciones seguidas para avisar)" in caplog.text

    ejecutar_con_umbral({}, notificador, repo_db, umbral=3)
    assert len(notificador.mensajes) == 1
    assert Errores.SIN_RESPUESTA_SNMP.name in notificador.mensajes[0]
    assert "(3 ejecuciones seguidas)" in notificador.mensajes[0]

    ejecutar_con_umbral({}, notificador, repo_db, umbral=3)  # ya avisado: no se repite
    assert len(notificador.mensajes) == 1


def test_una_respuesta_reinicia_la_cuenta_de_fallas(
    notificador: NotificadorFalso, repo_db: RepositorioDB
) -> None:
    # Fallas sueltas (un paquete perdido de vez en cuando) nunca llegan al umbral
    for respuestas in ({}, {}, RESPUESTAS_OK, {}, {}, RESPUESTAS_OK):
        ejecutar_con_umbral(respuestas, notificador, repo_db, umbral=3)

    assert notificador.mensajes == []
    assert repo_db.incidente_abierto(HOST, Errores.SIN_RESPUESTA_SNMP.name) is None


def test_sin_respuesta_avisado_se_resuelve_con_la_primera_respuesta(
    notificador: NotificadorFalso, repo_db: RepositorioDB
) -> None:
    for _ in range(3):
        ejecutar_con_umbral({}, notificador, repo_db, umbral=3)
    ejecutar_con_umbral(RESPUESTAS_OK, notificador, repo_db, umbral=3)

    assert len(notificador.mensajes) == 2
    assert f"[RESUELTO] {Errores.SIN_RESPUESTA_SNMP.name}" in notificador.mensajes[1]


def test_si_falla_el_aviso_de_sin_respuesta_se_reintenta_en_la_siguiente(
    notificador: NotificadorFalso, repo_db: RepositorioDB
) -> None:
    # A8: llegado el umbral, si el envio falla se vuelve a intentar en la proxima ejecucion
    notificador.falla = True
    for _ in range(3):
        ejecutar_con_umbral({}, notificador, repo_db, umbral=3)
    assert repo_db.incidente_abierto(HOST, Errores.SIN_RESPUESTA_SNMP.name) is None

    notificador.falla = False
    ejecutar_con_umbral({}, notificador, repo_db, umbral=3)
    assert len(notificador.mensajes) == 1
    assert repo_db.incidente_abierto(HOST, Errores.SIN_RESPUESTA_SNMP.name) is not None

import sqlite3
from contextlib import closing
from datetime import UTC, datetime, timedelta

import pytest

import config.configuracion as c
from core.alertas import Equipo, Regla, evaluar
from core.errores import Errores
from core.gestor_alertas import GestorAlertas
from core.ups_base import Lectura
from infraestructura.database import Incidente, RepositorioDB
from tests.dobles import NotificadorFalso

EQUIPO = Equipo("ups-test", "UPS", "ups-test")
CLAVE = EQUIPO.clave
SANO = {"battery": 25, "temp": 22, "capacity": 100, "load": 40, "life": 25}
SIN_RESPUESTA = Errores.SIN_RESPUESTA_SNMP


class Reloj:
    """Hora fija que los tests avanzan a mano."""

    def __init__(self) -> None:
        self.ahora = datetime(2026, 10, 12, 20, 0, tzinfo=UTC)

    def __call__(self) -> datetime:
        return self.ahora

    def avanzar(self, minutos: int) -> None:
        self.ahora += timedelta(minutes=minutos)


@pytest.fixture
def reloj() -> Reloj:
    return Reloj()


def gestor(
    notificador: NotificadorFalso, repo_db: RepositorioDB, reloj: Reloj, fallas: int = 1
) -> GestorAlertas:
    return GestorAlertas(repo_db, notificador, fallas_para_alerta=fallas, reloj=reloj)


def lectura(
    equipo: Equipo = EQUIPO, reglas: tuple[Regla, ...] = c.REGLAS_UPS, **cambios: float
) -> Lectura:
    datos = {**SANO, **cambios}
    return Lectura(equipo, ["linea"], hay_datos=True, chequeos=evaluar(reglas, datos))


def sin_respuesta(equipo: Equipo = EQUIPO) -> Lectura:
    return Lectura(equipo, [], hay_datos=False)


def abierto(repo_db: RepositorioDB, error: Errores, clave: str = CLAVE) -> Incidente | None:
    return repo_db.incidente_abierto(clave, error.name)


# ------------------------------------------------------------------ cambios de estado


def test_equipo_sano_no_avisa_nada(
    notificador: NotificadorFalso, repo_db: RepositorioDB, reloj: Reloj
) -> None:
    gestor(notificador, repo_db, reloj).procesar(lectura())
    assert notificador.eventos == []


def test_alerta_nueva_abre_un_incidente_y_avisa_una_sola_vez(
    notificador: NotificadorFalso, repo_db: RepositorioDB, reloj: Reloj
) -> None:
    g = gestor(notificador, repo_db, reloj)
    g.procesar(lectura(capacity=50))
    reloj.avanzar(1)
    g.procesar(lectura(capacity=50))  # sigue igual: no se repite

    [evento] = notificador.eventos
    assert (evento.error, evento.accion, evento.inicio) == (
        Errores.CARGA_MINIMA,
        "abrir",
        reloj.ahora - timedelta(minutes=1),
    )
    assert evento.chequeo is not None
    assert (evento.chequeo.valor, evento.chequeo.regla.umbral) == (50, 70)

    incidente = abierto(repo_db, Errores.CARGA_MINIMA)
    assert incidente is not None
    assert incidente.inicio == evento.inicio  # el mismo inicio identifica el hilo del chat


def test_al_resolverse_cierra_con_el_inicio_del_incidente_y_el_valor_actual(
    notificador: NotificadorFalso, repo_db: RepositorioDB, reloj: Reloj
) -> None:
    g = gestor(notificador, repo_db, reloj)
    g.procesar(lectura(load=75))
    inicio = reloj.ahora
    reloj.avanzar(135)
    g.procesar(lectura(load=48))

    cierre = notificador.eventos[1]
    assert (cierre.error, cierre.accion) == (Errores.LOAD_MAXIMO, "cerrar")
    assert (cierre.inicio, cierre.fin) == (inicio, reloj.ahora)  # duracion: 2 h 15 min
    assert cierre.chequeo is not None
    assert cierre.chequeo.valor == 48
    assert abierto(repo_db, Errores.LOAD_MAXIMO) is None


def test_varias_alertas_a_la_vez_son_eventos_separados(
    notificador: NotificadorFalso, repo_db: RepositorioDB, reloj: Reloj
) -> None:
    # Cada incidente tiene su propio mensaje y su propio hilo
    gestor(notificador, repo_db, reloj).procesar(lectura(capacity=50, load=90))

    assert [e.error for e in notificador.eventos] == [Errores.CARGA_MINIMA, Errores.LOAD_MAXIMO]
    assert abierto(repo_db, Errores.CARGA_MINIMA) is not None
    assert abierto(repo_db, Errores.LOAD_MAXIMO) is not None


def test_metrica_sin_dato_no_resuelve_su_incidente(
    notificador: NotificadorFalso, repo_db: RepositorioDB, reloj: Reloj
) -> None:
    g = gestor(notificador, repo_db, reloj)
    g.procesar(lectura(capacity=50))
    datos = {k: v for k, v in SANO.items() if k != "capacity"}
    g.procesar(Lectura(EQUIPO, ["linea"], True, evaluar(c.REGLAS_UPS, datos)))

    assert len(notificador.eventos) == 1
    assert abierto(repo_db, Errores.CARGA_MINIMA) is not None


def test_error_que_vuelve_abre_un_incidente_nuevo(
    notificador: NotificadorFalso, repo_db: RepositorioDB, reloj: Reloj
) -> None:
    g = gestor(notificador, repo_db, reloj)
    for capacidad in (50, 100, 50):
        g.procesar(lectura(capacity=capacidad))
        reloj.avanzar(1)

    assert [e.accion for e in notificador.eventos] == ["abrir", "cerrar", "abrir"]
    with closing(sqlite3.connect(repo_db.db_file)) as conn:
        filas = conn.execute("SELECT fin IS NULL FROM incidentes ORDER BY id").fetchall()
    assert filas == [(0,), (1,)]  # el primero cerrado (historial), el segundo abierto


# ------------------------------------------------------------------ A8: no perder alertas


def test_si_falla_el_envio_no_se_guarda_y_se_reintenta(
    caplog: pytest.LogCaptureFixture,
    notificador: NotificadorFalso,
    repo_db: RepositorioDB,
    reloj: Reloj,
) -> None:
    g = gestor(notificador, repo_db, reloj)
    notificador.falla = True
    g.procesar(lectura(capacity=50))
    assert abierto(repo_db, Errores.CARGA_MINIMA) is None
    assert f"No se pudo notificar {CLAVE} (CARGA_MINIMA)" in caplog.text

    notificador.falla = False
    g.procesar(lectura(capacity=50))
    assert len(notificador.eventos) == 1
    assert abierto(repo_db, Errores.CARGA_MINIMA) is not None


def test_si_se_resuelve_antes_del_reintento_no_se_envia_nada(
    notificador: NotificadorFalso, repo_db: RepositorioDB, reloj: Reloj
) -> None:
    g = gestor(notificador, repo_db, reloj)
    notificador.falla = True
    g.procesar(lectura(capacity=50))
    notificador.falla = False
    g.procesar(lectura())

    assert notificador.eventos == []


def test_si_falla_el_aviso_de_la_resolucion_el_incidente_sigue_abierto(
    notificador: NotificadorFalso, repo_db: RepositorioDB, reloj: Reloj
) -> None:
    g = gestor(notificador, repo_db, reloj)
    g.procesar(lectura(capacity=50))
    notificador.falla = True
    g.procesar(lectura())
    assert abierto(repo_db, Errores.CARGA_MINIMA) is not None

    notificador.falla = False
    g.procesar(lectura())
    assert abierto(repo_db, Errores.CARGA_MINIMA) is None
    assert notificador.eventos[-1].accion == "cerrar"


def test_cada_incidente_se_guarda_si_su_aviso_salio(
    notificador: NotificadorFalso, repo_db: RepositorioDB, reloj: Reloj
) -> None:
    # Con un mensaje por incidente, que falle uno no impide guardar el otro
    class FallaUno(NotificadorFalso):
        def notificar(self, evento):  # type: ignore[no-untyped-def]
            return evento.error != Errores.LOAD_MAXIMO and super().notificar(evento)

    gestor(FallaUno(), repo_db, reloj).procesar(lectura(capacity=50, load=90))

    assert abierto(repo_db, Errores.CARGA_MINIMA) is not None
    assert abierto(repo_db, Errores.LOAD_MAXIMO) is None


# ------------------------------------------------------------------ SIN_RESPUESTA_SNMP


def test_sin_respuesta_avisa_recien_despues_de_n_fallas_seguidas(
    caplog: pytest.LogCaptureFixture,
    notificador: NotificadorFalso,
    repo_db: RepositorioDB,
    reloj: Reloj,
) -> None:
    caplog.set_level("INFO")
    g = gestor(notificador, repo_db, reloj, fallas=3)
    for _ in range(2):
        g.procesar(sin_respuesta())
    assert notificador.eventos == []
    assert f"{CLAVE} sin respuesta SNMP (2 de 3 ejecuciones seguidas para avisar)" in caplog.text

    g.procesar(sin_respuesta())
    [evento] = notificador.eventos
    assert (evento.error, evento.accion, evento.fallas) == (SIN_RESPUESTA, "abrir", 3)

    g.procesar(sin_respuesta())  # ya avisado: no se repite
    assert len(notificador.eventos) == 1


def test_una_respuesta_reinicia_la_cuenta_de_fallas(
    notificador: NotificadorFalso, repo_db: RepositorioDB, reloj: Reloj
) -> None:
    # Fallas sueltas (un paquete perdido de vez en cuando) nunca llegan al umbral
    g = gestor(notificador, repo_db, reloj, fallas=3)
    for lec in (
        sin_respuesta(),
        sin_respuesta(),
        lectura(),
        sin_respuesta(),
        sin_respuesta(),
        lectura(),
    ):
        g.procesar(lec)

    assert notificador.eventos == []


def test_sin_respuesta_se_resuelve_con_la_primera_respuesta(
    notificador: NotificadorFalso, repo_db: RepositorioDB, reloj: Reloj
) -> None:
    g = gestor(notificador, repo_db, reloj, fallas=3)
    for _ in range(3):
        g.procesar(sin_respuesta())
    g.procesar(lectura())

    assert [e.accion for e in notificador.eventos] == ["abrir", "cerrar"]
    assert abierto(repo_db, SIN_RESPUESTA) is None


def test_sin_respuesta_no_resuelve_otros_incidentes(
    notificador: NotificadorFalso, repo_db: RepositorioDB, reloj: Reloj
) -> None:
    g = gestor(notificador, repo_db, reloj)
    g.procesar(lectura(battery=35))
    g.procesar(sin_respuesta())

    assert abierto(repo_db, Errores.TEMPERATURA_BATERIA_ALTA) is not None
    assert [e.accion for e in notificador.eventos] == ["abrir", "abrir"]


def test_si_falla_el_aviso_de_sin_respuesta_se_reintenta_en_la_siguiente(
    notificador: NotificadorFalso, repo_db: RepositorioDB, reloj: Reloj
) -> None:
    g = gestor(notificador, repo_db, reloj, fallas=3)
    notificador.falla = True
    for _ in range(3):
        g.procesar(sin_respuesta())
    assert abierto(repo_db, SIN_RESPUESTA) is None

    notificador.falla = False
    g.procesar(sin_respuesta())
    assert notificador.eventos[0].fallas == 4
    assert abierto(repo_db, SIN_RESPUESTA) is not None


def test_equipos_con_el_mismo_host_y_distinta_clave_son_independientes(
    notificador: NotificadorFalso, repo_db: RepositorioDB, reloj: Reloj
) -> None:
    # El sensor de humedad vive en un UPS: que no responda no es que el UPS no responda
    humedad = Equipo(EQUIPO.hostname, "Sensor de humedad", f"{EQUIPO.hostname}-humedad")
    g = gestor(notificador, repo_db, reloj)
    g.procesar(sin_respuesta(humedad))
    g.procesar(lectura())  # el UPS responde

    assert abierto(repo_db, SIN_RESPUESTA, clave=humedad.clave) is not None
    assert abierto(repo_db, SIN_RESPUESTA) is None
    assert len(notificador.eventos) == 1

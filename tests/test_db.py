import sqlite3
from contextlib import closing
from datetime import UTC, datetime, timedelta
from pathlib import Path

import pytest

from infraestructura.database import RepositorioDB

HOST = "ups-test"
ERROR = "CARGA_MINIMA"


def filas(repo: RepositorioDB, sql: str) -> list[tuple[object, ...]]:
    with closing(sqlite3.connect(repo.db_file)) as conn:
        return conn.execute(sql).fetchall()


def test_crea_las_tablas(repo_db: RepositorioDB) -> None:
    tablas = filas(repo_db, "SELECT name FROM sqlite_master WHERE type='table' ORDER BY name")
    assert tablas == [("fallas_consecutivas",), ("incidentes",)]


def test_crear_el_repositorio_dos_veces_no_falla(repo_db: RepositorioDB) -> None:
    # El esquema se ejecuta en cada arranque sobre la misma base
    repo_db.abrir_incidente(HOST, ERROR)
    otro = RepositorioDB(repo_db.db_file)
    assert otro.incidente_abierto(HOST, ERROR) is not None


def test_crea_la_carpeta_de_la_base_si_no_existe(tmp_path: Path) -> None:
    # data/ no esta en git: en un clon nuevo no existe
    db_file = tmp_path / "data" / "errores-v2.db"

    repo = RepositorioDB(str(db_file))
    repo.abrir_incidente(HOST, ERROR)

    assert db_file.exists()
    assert repo.incidente_abierto(HOST, ERROR) is not None


# ------------------------------------------------------------------ incidentes


def test_sin_incidentes_no_hay_ninguno_abierto(repo_db: RepositorioDB) -> None:
    assert repo_db.incidente_abierto(HOST, ERROR) is None


def test_abrir_incidente(repo_db: RepositorioDB) -> None:
    repo_db.abrir_incidente(HOST, ERROR)

    incidente = repo_db.incidente_abierto(HOST, ERROR)
    assert incidente is not None
    assert (incidente.ups_host, incidente.tipo_error) == (HOST, ERROR)
    # inicio en UTC, con zona, y de recien
    assert incidente.inicio.tzinfo == UTC
    assert datetime.now(UTC) - incidente.inicio < timedelta(minutes=1)


def test_abrir_dos_veces_no_duplica(repo_db: RepositorioDB) -> None:
    repo_db.abrir_incidente(HOST, ERROR)
    repo_db.abrir_incidente(HOST, ERROR)

    assert filas(repo_db, "SELECT COUNT(*) FROM incidentes") == [(1,)]


def test_la_base_impide_dos_incidentes_abiertos_del_mismo_error(repo_db: RepositorioDB) -> None:
    # La regla la garantiza el indice unico parcial, no solo el codigo
    repo_db.abrir_incidente(HOST, ERROR)
    with closing(sqlite3.connect(repo_db.db_file)) as conn, pytest.raises(sqlite3.IntegrityError):
        conn.execute("INSERT INTO incidentes (ups_host, tipo_error) VALUES (?, ?)", (HOST, ERROR))


def test_cerrar_incidente_guarda_el_fin(repo_db: RepositorioDB) -> None:
    repo_db.abrir_incidente(HOST, ERROR)
    repo_db.cerrar_incidente(HOST, ERROR)

    assert repo_db.incidente_abierto(HOST, ERROR) is None
    [(inicio, fin)] = filas(repo_db, "SELECT inicio, fin FROM incidentes")
    assert fin is not None
    assert str(fin) >= str(inicio)


def test_cerrar_sin_incidente_abierto_no_hace_nada(repo_db: RepositorioDB) -> None:
    repo_db.cerrar_incidente(HOST, ERROR)
    assert filas(repo_db, "SELECT COUNT(*) FROM incidentes") == [(0,)]


def test_cada_aparicion_es_un_incidente_nuevo(repo_db: RepositorioDB) -> None:
    # El historial queda: los cerrados no se reutilizan ni se pisan
    repo_db.abrir_incidente(HOST, ERROR)
    repo_db.cerrar_incidente(HOST, ERROR)
    repo_db.abrir_incidente(HOST, ERROR)

    estados = filas(repo_db, "SELECT fin IS NULL FROM incidentes ORDER BY id")
    assert estados == [(0,), (1,)]  # el primero cerrado, el segundo abierto


def test_incidentes_de_distintos_equipos_y_errores_son_independientes(
    repo_db: RepositorioDB,
) -> None:
    repo_db.abrir_incidente("UPS-A", ERROR)
    repo_db.abrir_incidente("UPS-B", ERROR)
    repo_db.abrir_incidente("UPS-A", "LOAD_MAXIMO")

    repo_db.cerrar_incidente("UPS-A", ERROR)

    assert repo_db.incidente_abierto("UPS-A", ERROR) is None
    assert repo_db.incidente_abierto("UPS-B", ERROR) is not None
    assert repo_db.incidente_abierto("UPS-A", "LOAD_MAXIMO") is not None


# ------------------------------------------------------------------ fallas consecutivas


def test_sumar_falla_cuenta_las_ejecuciones_seguidas(repo_db: RepositorioDB) -> None:
    assert [repo_db.sumar_falla(HOST, ERROR) for _ in range(3)] == [1, 2, 3]
    assert repo_db.sumar_falla("otro-ups", ERROR) == 1


def test_reiniciar_fallas_vuelve_a_empezar(repo_db: RepositorioDB) -> None:
    repo_db.sumar_falla(HOST, ERROR)
    repo_db.sumar_falla(HOST, ERROR)

    repo_db.reiniciar_fallas(HOST, ERROR)

    assert filas(repo_db, "SELECT COUNT(*) FROM fallas_consecutivas") == [(0,)]
    assert repo_db.sumar_falla(HOST, ERROR) == 1

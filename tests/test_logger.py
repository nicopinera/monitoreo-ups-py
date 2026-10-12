import logging
import os
from collections.abc import Iterator
from pathlib import Path

import pytest

import config.configuracion as c
from infraestructura.logger import configurar_logger


@pytest.fixture(autouse=True)
def restaurar_logging() -> Iterator[None]:
    """configurar_logger cambia el logger raiz: se restaura al terminar cada test."""
    raiz = logging.getLogger()
    handlers, nivel = raiz.handlers[:], raiz.level
    yield
    for handler in raiz.handlers:
        if handler not in handlers:
            handler.close()
    raiz.handlers[:] = handlers
    raiz.setLevel(nivel)


def leer_log(log_dir: Path) -> str:
    for handler in logging.getLogger().handlers:
        handler.flush()
    with open(os.path.join(log_dir, c.NOMBRE_ARCHIVO_LOG), encoding="utf-8") as archivo:
        return archivo.read()


def test_nunca_escribe_en_stdout(capsys: pytest.CaptureFixture[str], tmp_path: Path) -> None:
    # Requisito clave: stdout es solo para las lineas de telegraf
    configurar_logger(str(tmp_path))
    log = logging.getLogger("prueba")

    log.info("info")
    log.warning("warning")
    log.error("error")

    assert capsys.readouterr().out == ""


@pytest.mark.parametrize("nivel", ["info", "warning", "error"])
def test_todo_va_al_archivo_y_nada_a_la_consola(
    capsys: pytest.CaptureFixture[str], tmp_path: Path, nivel: str
) -> None:
    configurar_logger(str(tmp_path))

    getattr(logging.getLogger("prueba"), nivel)("timeout en f1r2u1")

    assert "timeout en f1r2u1" in leer_log(tmp_path)
    consola = capsys.readouterr()
    assert consola.out == ""
    assert consola.err == ""


def test_crea_la_carpeta_de_logs(tmp_path: Path) -> None:
    carpeta = tmp_path / "data" / "logs"

    configurar_logger(str(carpeta))
    logging.getLogger("prueba").info("primer log")

    assert "primer log" in leer_log(carpeta)


def test_nivel_debug(tmp_path: Path) -> None:
    configurar_logger(str(tmp_path), logging.DEBUG)
    logging.getLogger("prueba").debug("detalle")

    assert "detalle" in leer_log(tmp_path)


def test_por_defecto_no_registra_debug(tmp_path: Path) -> None:
    configurar_logger(str(tmp_path))
    logging.getLogger("prueba").debug("detalle")

    assert "detalle" not in leer_log(tmp_path)


def test_si_no_puede_crear_el_archivo_sigue_con_stderr(
    capsys: pytest.CaptureFixture[str], tmp_path: Path
) -> None:
    # Un archivo en lugar de carpeta hace fallar la creacion del log
    no_es_carpeta = tmp_path / "archivo"
    no_es_carpeta.write_text("")

    configurar_logger(str(no_es_carpeta))
    logging.getLogger("prueba").error("sigue funcionando")

    err = capsys.readouterr().err
    assert "No se pudo abrir el archivo de log" in err
    assert "sigue funcionando" in err


def test_sin_archivo_stderr_solo_muestra_desde_warning(
    capsys: pytest.CaptureFixture[str], tmp_path: Path
) -> None:
    no_es_carpeta = tmp_path / "archivo"
    no_es_carpeta.write_text("")

    configurar_logger(str(no_es_carpeta))
    logging.getLogger("prueba").info("informativo")

    assert "informativo" not in capsys.readouterr().err

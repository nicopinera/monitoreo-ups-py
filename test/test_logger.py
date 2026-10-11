import logging
import os

import pytest

import config.configuracion as c
from infraestructura.logger import configurar_logger


@pytest.fixture(autouse=True)
def restaurar_logging():
    """configurar_logger cambia el logger raiz: se restaura al terminar cada test."""
    raiz = logging.getLogger()
    handlers, nivel = raiz.handlers[:], raiz.level
    yield
    for handler in raiz.handlers:
        if handler not in handlers:
            handler.close()
    raiz.handlers[:] = handlers
    raiz.setLevel(nivel)


def leer_log(log_dir):
    for handler in logging.getLogger().handlers:
        handler.flush()
    with open(os.path.join(log_dir, c.NOMBRE_ARCHIVO_LOG), encoding="utf-8") as archivo:
        return archivo.read()


def test_nunca_escribe_en_stdout(capsys, tmp_path):
    # Requisito clave: stdout es solo para las lineas de telegraf
    configurar_logger(log_dir=str(tmp_path))
    log = logging.getLogger("prueba")

    log.info("info")
    log.warning("warning")
    log.error("error")

    assert capsys.readouterr().out == ""


@pytest.mark.parametrize("nivel", ["info", "warning", "error"])
def test_todo_va_al_archivo_y_nada_a_la_consola(capsys, tmp_path, nivel):
    configurar_logger(log_dir=str(tmp_path))

    getattr(logging.getLogger("prueba"), nivel)("timeout en f1r2u1")

    assert "timeout en f1r2u1" in leer_log(tmp_path)
    consola = capsys.readouterr()
    assert consola.out == ""
    assert consola.err == ""


def test_usa_la_variable_de_entorno_para_la_carpeta(monkeypatch, tmp_path):
    carpeta = tmp_path / "logs_env"
    monkeypatch.setenv(c.VAR_LOG_DIR, str(carpeta))

    configurar_logger()
    logging.getLogger("prueba").info("desde env")

    assert "desde env" in leer_log(carpeta)


def test_nivel_debug_desde_variable_de_entorno(monkeypatch, tmp_path):
    monkeypatch.setenv(c.VAR_LOG_LEVEL, "debug")

    configurar_logger(log_dir=str(tmp_path))
    logging.getLogger("prueba").debug("detalle")

    assert "detalle" in leer_log(tmp_path)


def test_nivel_invalido_usa_info(tmp_path):
    configurar_logger(log_dir=str(tmp_path), nivel="CUALQUIERA")

    assert logging.getLogger().level == logging.INFO


def test_si_no_puede_crear_el_archivo_sigue_con_stderr(capsys, tmp_path):
    # Un archivo en lugar de carpeta hace fallar la creacion del log
    no_es_carpeta = tmp_path / "archivo"
    no_es_carpeta.write_text("")

    configurar_logger(log_dir=str(no_es_carpeta))
    logging.getLogger("prueba").error("sigue funcionando")

    err = capsys.readouterr().err
    assert "No se pudo abrir el archivo de log" in err
    assert "sigue funcionando" in err


def test_sin_archivo_stderr_solo_muestra_desde_warning(capsys, tmp_path):
    no_es_carpeta = tmp_path / "archivo"
    no_es_carpeta.write_text("")

    configurar_logger(log_dir=str(no_es_carpeta))
    logging.getLogger("prueba").info("informativo")

    assert "informativo" not in capsys.readouterr().err

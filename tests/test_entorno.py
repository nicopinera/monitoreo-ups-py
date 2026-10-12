import logging
import os
from pathlib import Path

import pytest

import config.configuracion as c
from config.entorno import (
    VAR_DATA_DIR,
    VAR_SNMP_COMMUNITY,
    ErrorConfiguracion,
    cargar_entorno,
)

MINIMO = {VAR_SNMP_COMMUNITY: "comunidad"}  # la unica variable obligatoria


def test_valores_por_defecto() -> None:
    entorno = cargar_entorno(None, MINIMO)

    assert entorno.webhook_url is None
    assert entorno.grafana_url == "https://grafana.srv.unc.edu.ar/d/26SryAYmz/datacenter"
    assert entorno.snmp.community == "comunidad"
    assert entorno.snmp.timeout == 1.0
    assert entorno.snmp.retries == 1
    assert entorno.http_timeout == 10.0
    assert entorno.max_workers == 13
    assert entorno.fallas_para_alerta == 3
    assert entorno.log_level == logging.INFO
    assert entorno.data_dir == os.path.join(c.RUTA_RAIZ, "data")
    assert entorno.archivo_db == os.path.join(c.RUTA_RAIZ, "data", "errores-v2.db")
    assert entorno.logs_dir == os.path.join(c.RUTA_RAIZ, "data", "logs")


def test_convierte_los_valores() -> None:
    entorno = cargar_entorno(
        None,
        {
            **MINIMO,
            "GOOGLE_CHAT_WEBHOOK_URL": "https://chat.example/webhook",
            "GRAFANA_URL": "http://grafana.local/d/x",
            "SNMP_TIMEOUT": "2.5",
            "SNMP_RETRIES": "0",
            "HTTP_TIMEOUT": "5",
            "MAX_WORKERS": "26",
            "SNMP_FALLAS_PARA_ALERTA": "1",
            "LOG_LEVEL": "debug",
        },
    )

    assert entorno.webhook_url == "https://chat.example/webhook"
    assert entorno.grafana_url == "http://grafana.local/d/x"
    assert entorno.snmp.timeout == 2.5
    assert entorno.snmp.retries == 0
    assert entorno.http_timeout == 5.0
    assert entorno.max_workers == 26
    assert entorno.fallas_para_alerta == 1
    assert entorno.log_level == logging.DEBUG


def test_valor_vacio_cuenta_como_ausente() -> None:
    entorno = cargar_entorno(None, {**MINIMO, "GOOGLE_CHAT_WEBHOOK_URL": "", "MAX_WORKERS": " "})

    assert entorno.webhook_url is None
    assert entorno.max_workers == 13


def test_falta_la_comunidad_snmp() -> None:
    with pytest.raises(ErrorConfiguracion, match="SNMP_COMMUNITY: falta y es obligatoria"):
        cargar_entorno(None, {})


def test_informa_todos_los_errores_juntos() -> None:
    invalido = {
        "SNMP_TIMEOUT": "abc",
        "SNMP_RETRIES": "1.5",
        "MAX_WORKERS": "0",
        "GRAFANA_URL": "grafana.local",
        "SNMP_FALLAS_PARA_ALERTA": "0",
        "LOG_LEVEL": "MUCHO",
        "GOOGLE_CHAT_WEBHOOK_URL": "http://chat.example/webhook",
    }

    with pytest.raises(ErrorConfiguracion) as error:
        cargar_entorno(None, invalido)

    mensaje = str(error.value)
    assert "SNMP_COMMUNITY: falta y es obligatoria" in mensaje
    assert "SNMP_TIMEOUT='abc': tiene que ser un numero" in mensaje
    assert "SNMP_RETRIES='1.5': tiene que ser un entero" in mensaje
    assert "MAX_WORKERS='0': tiene que ser mayor o igual a 1" in mensaje
    assert "GRAFANA_URL: tiene que empezar con https:// o http://" in mensaje
    assert "SNMP_FALLAS_PARA_ALERTA='0': tiene que ser mayor o igual a 1" in mensaje
    assert "LOG_LEVEL='MUCHO'" in mensaje
    assert "GOOGLE_CHAT_WEBHOOK_URL: tiene que empezar con https://" in mensaje


def test_ruta_relativa_se_toma_desde_la_raiz_del_repo() -> None:
    entorno = cargar_entorno(None, {**MINIMO, VAR_DATA_DIR: "otra/carpeta/"})

    assert entorno.data_dir == os.path.join(c.RUTA_RAIZ, "otra", "carpeta")


def test_ruta_absoluta_se_respeta(tmp_path: Path) -> None:
    entorno = cargar_entorno(None, {**MINIMO, VAR_DATA_DIR: str(tmp_path)})

    assert entorno.data_dir == str(tmp_path)


def escribir_env(tmp_path: Path, contenido: str) -> str:
    ruta = tmp_path / ".env"
    ruta.write_text(contenido, encoding="utf-8")
    return str(ruta)


def test_lee_el_archivo_env(tmp_path: Path) -> None:
    ruta = escribir_env(
        tmp_path,
        '# comentario\nSNMP_COMMUNITY=desde-archivo\nGOOGLE_CHAT_WEBHOOK_URL="https://x.example"\n',
    )

    entorno = cargar_entorno(ruta, {})

    assert entorno.snmp.community == "desde-archivo"
    assert entorno.webhook_url == "https://x.example"  # python-dotenv quita las comillas


def test_el_entorno_real_gana_sobre_el_archivo(tmp_path: Path) -> None:
    ruta = escribir_env(tmp_path, "SNMP_COMMUNITY=desde-archivo\nLOG_LEVEL=ERROR\n")

    entorno = cargar_entorno(ruta, {"LOG_LEVEL": "DEBUG"})

    assert entorno.snmp.community == "desde-archivo"
    assert entorno.log_level == logging.DEBUG


def test_archivo_inexistente_no_es_error(tmp_path: Path) -> None:
    entorno = cargar_entorno(str(tmp_path / "no-existe.env"), MINIMO)

    assert entorno.snmp.community == "comunidad"


def test_no_modifica_las_variables_del_proceso(tmp_path: Path) -> None:
    ruta = escribir_env(tmp_path, "SNMP_COMMUNITY=x\nVARIABLE_SOLO_EN_ARCHIVO=1\n")

    cargar_entorno(ruta, {})

    assert "VARIABLE_SOLO_EN_ARCHIVO" not in os.environ

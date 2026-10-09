import os
import subprocess
import sys

import pytest
from easysnmp import EasySNMPConnectionError
import config.configuracion as c
import main
from test.conftest import ClienteSNMPFalso, NotificadorFalso

RUTA_SRC = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "src")


def tarea_que_imprime(texto):
    return lambda: print(texto)


def tarea_que_falla(mensaje):
    def tarea():
        raise RuntimeError(mensaje)
    return tarea


# ------------------------------------------------------------------ import sin efectos secundarios

def test_importar_main_no_configura_logging(tmp_path):
    # En un proceso aparte: importar main no debe escribir nada ni crear la carpeta de logs
    carpeta_logs = tmp_path / "logs"
    entorno = dict(os.environ, PYTHONPATH=RUTA_SRC, MONITOREO_LOG_DIR=str(carpeta_logs))

    resultado = subprocess.run(
        [sys.executable, "-c", "import main"], env=entorno, capture_output=True, text=True, timeout=30
    )

    assert resultado.returncode == 0
    assert resultado.stdout == ""
    assert resultado.stderr == ""
    assert not carpeta_logs.exists()


# ------------------------------------------------------------------ ejecutar_tareas

def test_falla_en_tarea_secuencial_no_frena_al_resto(capsys, caplog):
    secuenciales = [("humedad", tarea_que_imprime("linea humedad")), ("DC", tarea_que_falla("se rompio el DC"))]
    paralelas = [("state a", tarea_que_imprime("linea a")), ("state b", tarea_que_imprime("linea b"))]

    resultados = main.ejecutar_tareas(secuenciales, paralelas)

    assert resultados == [True, False, True, True]
    salida = capsys.readouterr().out
    assert "linea humedad" in salida
    assert "linea a" in salida
    assert "linea b" in salida
    assert "Error al ejecutar DC" in caplog.text
    assert "se rompio el DC" in caplog.text  # el traceback queda en el log


def test_falla_en_tarea_paralela_se_registra_y_el_resto_sigue(capsys, caplog):
    paralelas = [
        ("state a", tarea_que_imprime("linea a")),
        ("state b", tarea_que_falla("fallo en un hilo")),
        ("state c", tarea_que_imprime("linea c")),
    ]

    resultados = main.ejecutar_tareas([], paralelas)

    assert resultados == [True, False, True]
    salida = capsys.readouterr().out
    assert "linea a" in salida
    assert "linea c" in salida
    assert "Error al ejecutar state b" in caplog.text
    assert "fallo en un hilo" in caplog.text


# ------------------------------------------------------------------ crear_tareas + ejecutar_tareas

def test_host_que_no_resuelve_dns_solo_afecta_a_ese_host(monkeypatch, capsys, caplog, notificador, repo_db):
    host_roto = c.HOST_NAME_STATE[0]
    respuestas = {
        c.OIDB: "25", c.OIDCAPACITY: "100", c.OIDLOAD: "40", c.OIDLIFE: "150000", c.OIDCURRENT: "6", c.OIDT: "22",
        c.OID_HUMEDAD: "45",
    }

    def fabrica_clientes(hostname):
        # Igual que easysnmp con un nombre que no resuelve DNS
        if hostname == host_roto:
            raise EasySNMPConnectionError("couldn't create SNMP handle")
        return ClienteSNMPFalso(respuestas)

    monkeypatch.setattr(main, "ClienteSNMP", fabrica_clientes)

    resultados = main.ejecutar_tareas(*main.crear_tareas(notificador, repo_db))

    lineas = capsys.readouterr().out.splitlines()
    lineas_state = [linea for linea in lineas if "battery=" in linea]
    assert len(lineas_state) == len(c.HOST_NAME_STATE) - 1
    assert not any(f"host={host_roto} " in linea for linea in lineas)
    assert f"ups_temp2,host={c.HOST_NAME_HUMEDAD} humidity=45" in lineas
    assert resultados.count(False) == 1
    assert f"Error al ejecutar state {host_roto}" in caplog.text


# ------------------------------------------------------------------ codigo de salida de main

@pytest.mark.parametrize(
    ("tareas", "codigo_esperado"),
    [
        ([tarea_que_imprime("ok"), tarea_que_imprime("ok")], 0),
        ([tarea_que_imprime("ok"), tarea_que_falla("x")], 0),   # al menos una bien -> 0
        ([tarea_que_falla("x"), tarea_que_falla("y")], 1),      # fallaron todas -> 1
    ],
)
def test_codigo_de_salida(monkeypatch, tareas, codigo_esperado):
    monkeypatch.setattr(main, "Notificador", lambda ruta_env: NotificadorFalso())
    monkeypatch.setattr(main, "RepositorioDB", lambda ruta_db: None)  # no tocar data/errores.db
    monkeypatch.setattr(
        main, "crear_tareas", lambda notificador, repo_db: ([], [(f"t{i}", t) for i, t in enumerate(tareas)])
    )

    assert main.main() == codigo_esperado


def test_si_fallan_tareas_se_registra_el_resumen(monkeypatch, caplog):
    monkeypatch.setattr(main, "Notificador", lambda ruta_env: NotificadorFalso())
    monkeypatch.setattr(main, "RepositorioDB", lambda ruta_db: None)
    monkeypatch.setattr(
        main, "crear_tareas", lambda notificador, repo_db: ([], [("a", tarea_que_imprime("ok")), ("b", tarea_que_falla("x"))])
    )

    main.main()

    assert "Fallaron 1 de 2 tareas" in caplog.text

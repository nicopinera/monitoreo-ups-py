import os
import subprocess
import sys
import time
from collections.abc import Callable
from pathlib import Path

import pytest
from easysnmp import EasySNMPConnectionError

import config.configuracion as c
import main
from infraestructura.database import RepositorioDB
from tests.dobles import ClienteSNMPFalso, NotificadorFalso

RUTA_SRC = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "src")


def tarea_que_devuelve(*lineas: str) -> Callable[[], list[str]]:
    return lambda: list(lineas)


def tarea_que_falla(mensaje: str) -> Callable[[], list[str]]:
    def tarea() -> list[str]:
        raise RuntimeError(mensaje)

    return tarea


# ------------------------------------------------------------------ import sin efectos secundarios


def test_importar_main_no_configura_logging(tmp_path: Path) -> None:
    # En un proceso aparte: importar main no debe escribir nada ni crear la carpeta de logs
    carpeta_logs = tmp_path / "logs"
    entorno = dict(os.environ, PYTHONPATH=RUTA_SRC, MONITOREO_LOG_DIR=str(carpeta_logs))

    resultado = subprocess.run(
        [sys.executable, "-c", "import main"],
        env=entorno,
        capture_output=True,
        text=True,
        timeout=30,
        check=False,  # el codigo de salida se verifica abajo
    )

    assert resultado.returncode == 0
    assert resultado.stdout == ""
    assert resultado.stderr == ""
    assert not carpeta_logs.exists()


# ------------------------------------------------------------------ ejecutar_tareas


def test_falla_en_una_tarea_se_registra_y_el_resto_sigue(caplog: pytest.LogCaptureFixture) -> None:
    tareas = [
        ("humedad", tarea_que_devuelve("linea humedad")),
        ("DC", tarea_que_falla("se rompio el DC")),
        ("state a", tarea_que_devuelve("linea a")),
    ]

    resultados = main.ejecutar_tareas(tareas)

    assert resultados == [["linea humedad"], None, ["linea a"]]
    assert "Error al ejecutar DC" in caplog.text
    assert "se rompio el DC" in caplog.text  # el traceback queda en el log


def tarea_lenta(segundos: float, linea: str) -> Callable[[], list[str]]:
    def tarea() -> list[str]:
        time.sleep(segundos)
        return [linea]

    return tarea


def test_las_tareas_corren_en_paralelo_y_respetan_el_orden() -> None:
    # Si corrieran una detras de otra tardarian 0.9 s; en paralelo, ~0.3 s.
    # La primera es la que mas tarda: el resultado igual sale en el orden de las tareas.
    tareas = [
        ("DC", tarea_lenta(0.3, "dc")),
        ("humedad", tarea_lenta(0.1, "humedad")),
        ("state a", tarea_lenta(0.3, "a")),
        ("state b", tarea_lenta(0.2, "b")),
    ]

    inicio = time.monotonic()
    resultados = main.ejecutar_tareas(tareas, max_workers=4)
    duracion = time.monotonic() - inicio

    assert resultados == [["dc"], ["humedad"], ["a"], ["b"]]
    assert duracion < 0.6


# ------------------------------------------------------------------ crear_tareas + ejecutar_tareas


def test_host_que_no_resuelve_dns_solo_afecta_a_ese_host(
    monkeypatch: pytest.MonkeyPatch,
    caplog: pytest.LogCaptureFixture,
    notificador: NotificadorFalso,
    repo_db: RepositorioDB,
) -> None:
    host_roto = c.HOST_NAME_STATE[0]
    respuestas = {
        c.OIDB: "25",
        c.OIDCAPACITY: "100",
        c.OIDLOAD: "40",
        c.OIDLIFE: "150000",
        c.OIDCURRENT: "6",
        c.OIDT: "22",
        c.OID_HUMEDAD: "45",
    }

    def fabrica_clientes(hostname: str) -> ClienteSNMPFalso:
        # Igual que easysnmp con un nombre que no resuelve DNS
        if hostname == host_roto:
            raise EasySNMPConnectionError("couldn't create SNMP handle")
        return ClienteSNMPFalso(respuestas)

    monkeypatch.setattr(main, "ClienteSNMP", fabrica_clientes)

    resultados = main.ejecutar_tareas(main.crear_tareas(notificador, repo_db))

    lineas = [linea for resultado in resultados if resultado for linea in resultado]
    lineas_state = [linea for linea in lineas if "battery=" in linea]
    assert len(lineas_state) == len(c.HOST_NAME_STATE) - 1
    assert not any(f"host={host_roto} " in linea for linea in lineas)
    assert f"ups_temp2,host={c.HOST_NAME_HUMEDAD} humidity=45" in lineas
    assert resultados.count(None) == 1
    assert f"Error al ejecutar state {host_roto}" in caplog.text


# ------------------------------------------------------------------ codigo de salida de main


def preparar_main(monkeypatch: pytest.MonkeyPatch, tareas: list[main.Tarea]) -> None:
    """main con tareas falsas, sin tocar el chat ni data/errores.db."""
    monkeypatch.setattr(main, "Notificador", lambda ruta_env: NotificadorFalso())
    monkeypatch.setattr(main, "RepositorioDB", lambda ruta_db: None)
    monkeypatch.setattr(main, "crear_tareas", lambda notificador, repo_db: tareas)


@pytest.mark.parametrize(
    ("tareas", "codigo_esperado"),
    [
        ([tarea_que_devuelve("a"), tarea_que_devuelve("b")], 0),
        ([tarea_que_devuelve("a"), tarea_que_falla("x")], 0),  # hay metricas -> 0
        ([tarea_que_falla("x"), tarea_que_falla("y")], 1),  # fallaron todas -> 1
        ([tarea_que_devuelve(), tarea_que_devuelve()], 1),  # ningun equipo respondio -> 1
    ],
)
def test_codigo_de_salida(
    monkeypatch: pytest.MonkeyPatch, tareas: list[Callable[[], list[str]]], codigo_esperado: int
) -> None:
    preparar_main(monkeypatch, [(f"t{i}", t) for i, t in enumerate(tareas)])

    assert main.main() == codigo_esperado


def test_si_fallan_tareas_se_registra_el_resumen(
    monkeypatch: pytest.MonkeyPatch, caplog: pytest.LogCaptureFixture
) -> None:
    preparar_main(monkeypatch, [("a", tarea_que_devuelve("ok")), ("b", tarea_que_falla("x"))])

    main.main()

    assert "Fallaron 1 de 2 tareas" in caplog.text


# ------------------------------------------------------------------ salida a stdout


def test_main_escribe_las_lineas_en_el_orden_de_las_tareas(
    monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
) -> None:
    preparar_main(
        monkeypatch,
        [
            ("humedad", tarea_que_devuelve("humedad")),
            ("a", tarea_que_devuelve("a1", "a2")),
            ("b", tarea_que_falla("x")),
            ("c", tarea_que_devuelve()),
            ("d", tarea_que_devuelve("d1")),
        ],
    )

    main.main()

    assert capsys.readouterr().out == "humedad\na1\na2\nd1\n"


class StdoutQueRegistra:
    def __init__(self) -> None:
        self.escrituras: list[str] = []

    def write(self, texto: str) -> None:
        self.escrituras.append(texto)

    def flush(self) -> None:
        pass


def test_main_escribe_todo_con_una_sola_escritura(monkeypatch: pytest.MonkeyPatch) -> None:
    # Una sola escritura desde el hilo principal: no hay forma de que dos lineas se intercalen
    stdout = StdoutQueRegistra()
    monkeypatch.setattr(sys, "stdout", stdout)
    preparar_main(monkeypatch, [(f"t{i}", tarea_que_devuelve(f"linea {i}")) for i in range(20)])

    main.main()

    assert stdout.escrituras == ["".join(f"linea {i}\n" for i in range(20))]


def test_sin_metricas_no_escribe_nada(
    monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture[str],
    caplog: pytest.LogCaptureFixture,
) -> None:
    preparar_main(monkeypatch, [("a", tarea_que_devuelve())])

    assert main.main() == 1
    assert capsys.readouterr().out == ""  # ni siquiera un salto de linea suelto
    assert "No se obtuvo ninguna metrica" in caplog.text

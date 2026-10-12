import logging
import os
import subprocess
import sys
import time
from collections.abc import Callable, Iterator
from pathlib import Path

import pytest

import config.configuracion as c
import config.entorno as entorno_mod
import main
from config.entorno import AjustesSNMP, Entorno
from infraestructura.database import RepositorioDB
from tests.dobles import ClienteSNMPFalso, NotificadorFalso, entorno_de_prueba

# preparar_main reemplaza la base y el notificador: la carpeta de datos no se usa
ENTORNO = entorno_de_prueba("/no/se/usa")

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
    carpeta_datos = tmp_path / "data"
    entorno = dict(os.environ, PYTHONPATH=RUTA_SRC, MONITOREO_DATA_DIR=str(carpeta_datos))

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
    assert not carpeta_datos.exists()


# ------------------------------------------------------------------ ejecutar_tareas


def test_falla_en_una_tarea_se_registra_y_el_resto_sigue(caplog: pytest.LogCaptureFixture) -> None:
    tareas = [
        ("humedad", tarea_que_devuelve("linea humedad")),
        ("DC", tarea_que_falla("se rompio el DC")),
        ("state a", tarea_que_devuelve("linea a")),
    ]

    resultados = main.ejecutar_tareas(tareas, max_workers=4)

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


def test_error_al_crear_el_cliente_solo_afecta_a_ese_host(
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

    def fabrica_clientes(hostname: str, ajustes: AjustesSNMP) -> ClienteSNMPFalso:
        # Un error al crear el cliente de un host solo afecta a ese host
        if hostname == host_roto:
            raise RuntimeError("no se pudo crear la sesion SNMP")
        return ClienteSNMPFalso(respuestas)

    monkeypatch.setattr(main, "ClienteSNMP", fabrica_clientes)

    ajustes = AjustesSNMP(community="x", timeout=1.0, retries=1)
    resultados = main.ejecutar_tareas(main.crear_tareas(ajustes, notificador, repo_db), 4)

    lineas = [linea for resultado in resultados if resultado for linea in resultado]
    lineas_state = [linea for linea in lineas if "battery=" in linea]
    assert len(lineas_state) == len(c.HOST_NAME_STATE) - 1
    assert not any(f"host={host_roto} " in linea for linea in lineas)
    assert f"ups_temp2,host={c.HOST_NAME_HUMEDAD} humidity=45" in lineas
    assert resultados.count(None) == 1
    assert f"Error al ejecutar state {host_roto}" in caplog.text


# ------------------------------------------------------------------ codigo de salida de main


def preparar_main(monkeypatch: pytest.MonkeyPatch, tareas: list[main.Tarea]) -> None:
    """main con tareas falsas, sin tocar el chat ni la base de data/."""
    monkeypatch.setattr(main, "Notificador", lambda url, timeout: NotificadorFalso())
    monkeypatch.setattr(main, "RepositorioDB", lambda ruta_db: None)
    monkeypatch.setattr(main, "crear_tareas", lambda ajustes, notificador, repo_db, fallas: tareas)


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

    assert main.main(ENTORNO) == codigo_esperado


def test_si_fallan_tareas_se_registra_el_resumen(
    monkeypatch: pytest.MonkeyPatch, caplog: pytest.LogCaptureFixture
) -> None:
    preparar_main(monkeypatch, [("a", tarea_que_devuelve("ok")), ("b", tarea_que_falla("x"))])

    main.main(ENTORNO)

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

    main.main(ENTORNO)

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

    main.main(ENTORNO)

    assert stdout.escrituras == ["".join(f"linea {i}\n" for i in range(20))]


def test_sin_metricas_no_escribe_nada(
    monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture[str],
    caplog: pytest.LogCaptureFixture,
) -> None:
    preparar_main(monkeypatch, [("a", tarea_que_devuelve())])

    assert main.main(ENTORNO) == 1
    assert capsys.readouterr().out == ""  # ni siquiera un salto de linea suelto
    assert "No se obtuvo ninguna metrica" in caplog.text


# ----------------------------------------------------------------- iniciar: configuracion y log


@pytest.fixture
def entorno_limpio(monkeypatch: pytest.MonkeyPatch) -> None:
    """Quita las variables del monitoreo que puedan estar definidas en la maquina del test."""
    for variable in (
        entorno_mod.VAR_WEBHOOK_URL,
        entorno_mod.VAR_SNMP_COMMUNITY,
        entorno_mod.VAR_SNMP_TIMEOUT,
        entorno_mod.VAR_SNMP_RETRIES,
        entorno_mod.VAR_HTTP_TIMEOUT,
        entorno_mod.VAR_MAX_WORKERS,
        entorno_mod.VAR_LOG_LEVEL,
        entorno_mod.VAR_DATA_DIR,
    ):
        monkeypatch.delenv(variable, raising=False)


@pytest.fixture
def restaurar_logging() -> Iterator[None]:
    raiz = logging.getLogger()
    handlers, nivel = raiz.handlers[:], raiz.level
    yield
    for handler in raiz.handlers:
        if handler not in handlers:
            handler.close()
    raiz.handlers[:] = handlers
    raiz.setLevel(nivel)


@pytest.mark.usefixtures("entorno_limpio")
def test_configuracion_invalida_sale_con_1_y_lo_explica_en_stderr(
    monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str], tmp_path: Path
) -> None:
    env = tmp_path / ".env"
    env.write_text(f"MONITOREO_DATA_DIR={tmp_path / 'data'}\nSNMP_TIMEOUT=abc\n", encoding="utf-8")
    llamado: list[Entorno] = []

    def main_falso(entorno: Entorno) -> int:
        llamado.append(entorno)
        return 0

    monkeypatch.setattr(main, "main", main_falso)

    assert main.iniciar(str(env)) == 1

    err = capsys.readouterr().err
    assert "Configuracion invalida" in err
    assert "SNMP_COMMUNITY: falta y es obligatoria" in err
    assert "SNMP_TIMEOUT='abc'" in err
    assert llamado == []  # no se monitorea con una configuracion rota
    assert not (tmp_path / "data").exists()


@pytest.mark.usefixtures("entorno_limpio", "restaurar_logging")
def test_iniciar_carga_el_entorno_y_configura_el_log(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    env = tmp_path / ".env"
    env.write_text(
        f"SNMP_COMMUNITY=x\nMONITOREO_DATA_DIR={tmp_path / 'data'}\nLOG_LEVEL=DEBUG\n",
        encoding="utf-8",
    )
    recibido = []

    def main_falso(entorno: Entorno) -> int:
        recibido.append(entorno)
        logging.getLogger("prueba").debug("monitoreando")
        return 0

    monkeypatch.setattr(main, "main", main_falso)

    assert main.iniciar(str(env)) == 0

    assert recibido[0].snmp.community == "x"
    log = (tmp_path / "data" / "logs" / c.NOMBRE_ARCHIVO_LOG).read_text(encoding="utf-8")
    assert "monitoreando" in log  # el logger usa la carpeta y el nivel del entorno


@pytest.mark.usefixtures("entorno_limpio", "restaurar_logging")
def test_excepcion_en_main_sale_con_1_y_queda_en_el_log(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    env = tmp_path / ".env"
    env.write_text(f"SNMP_COMMUNITY=x\nMONITOREO_DATA_DIR={tmp_path}\n", encoding="utf-8")

    def main_que_falla(entorno: Entorno) -> int:
        raise RuntimeError("base rota")

    monkeypatch.setattr(main, "main", main_que_falla)

    assert main.iniciar(str(env)) == 1

    log = (tmp_path / "logs" / c.NOMBRE_ARCHIVO_LOG).read_text(encoding="utf-8")
    assert "Error fatal en el flujo principal" in log
    assert "base rota" in log

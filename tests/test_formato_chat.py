import time
from datetime import UTC, datetime, timedelta
from typing import Any

import pytest

import config.configuracion as c
from core.alertas import Chequeo, Equipo, Evento, Regla
from core.errores import Errores
from infraestructura.formato_chat import (
    TITULOS,
    armar_mensaje,
    clave_hilo,
    formatear_duracion,
    formatear_numero,
)

UPS = Equipo("f1r11u1", "UPS", "f1r11u1")
HUMEDAD = Equipo("f2r7u1", "Sensor de humedad", "f2r7u1-humedad")
INICIO = datetime(2026, 10, 12, 20, 21, tzinfo=UTC)
GRAFANA = "https://grafana.example/d/datacenter"


def regla(error: Errores) -> Regla:
    return next(r for r in c.REGLAS_UPS if r.error == error)


LOAD = regla(Errores.LOAD_MAXIMO)


def widget(mensaje: dict[str, Any]) -> dict[str, Any]:
    """El decoratedText de la alerta (primer widget de la tarjeta)."""
    decorado: dict[str, Any] = mensaje["cardsV2"][0]["card"]["sections"][0]["widgets"][0][
        "decoratedText"
    ]
    return decorado


def botones(mensaje: dict[str, Any]) -> list[dict[str, Any]]:
    widgets = mensaje["cardsV2"][0]["card"]["sections"][0]["widgets"]
    return [b for w in widgets if "buttonList" in w for b in w["buttonList"]["buttons"]]


def test_todos_los_errores_tienen_texto() -> None:
    assert set(TITULOS) == set(Errores)


@pytest.mark.parametrize(("valor", "texto"), [(63, "63"), (25.0, "25"), (7.5, "7,5"), (-1, "-1")])
def test_formatear_numero(valor: float, texto: str) -> None:
    assert formatear_numero(valor) == texto


@pytest.mark.parametrize(
    ("minutos", "texto"),
    [
        (0, "menos de 1 min"),
        (12, "12 min"),
        (60, "1 h"),
        (135, "2 h 15 min"),
        (1620, "1 d 3 h"),
        (2880, "2 d"),
    ],
)
def test_formatear_duracion(minutos: int, texto: str) -> None:
    assert formatear_duracion(INICIO, INICIO + timedelta(minutes=minutos)) == texto


def test_alerta_y_resolucion_comparten_el_hilo() -> None:
    alerta = Evento(UPS, Errores.LOAD_MAXIMO, "abrir", INICIO)
    cierre = Evento(UPS, Errores.LOAD_MAXIMO, "cerrar", INICIO, INICIO + timedelta(hours=1))
    otro = Evento(UPS, Errores.LOAD_MAXIMO, "abrir", INICIO + timedelta(days=1))

    assert clave_hilo(alerta) == clave_hilo(cierre) == "f1r11u1-LOAD_MAXIMO-20261012T202100Z"
    assert clave_hilo(otro) != clave_hilo(alerta)  # un incidente nuevo abre otro hilo


def test_alerta_con_valor_umbral_y_boton_de_grafana() -> None:
    evento = Evento(UPS, Errores.LOAD_MAXIMO, "abrir", INICIO, chequeo=Chequeo(LOAD, 63, True))
    mensaje = armar_mensaje(evento, GRAFANA)

    assert mensaje["fallbackText"] == "⚠️ f1r11u1: Carga de salida alta (63 %)"
    assert "text" not in mensaje  # se mostraria repetido arriba de la tarjeta
    tarjeta = mensaje["cardsV2"][0]
    assert tarjeta["cardId"] == clave_hilo(evento)
    assert tarjeta["card"]["header"]["title"] == "UPS f1r11u1"
    assert tarjeta["card"]["header"]["subtitle"].startswith("Alerta nueva · ")
    texto = widget(mensaje)
    assert texto["topLabel"] == "Carga de salida alta"
    assert "<b>63 %</b>" in texto["text"]
    assert texto["text"].endswith("· máximo 45 %")
    assert texto["startIcon"] == {"materialIcon": {"name": "warning"}}
    assert botones(mensaje) == [
        {"text": "Ver en Grafana", "onClick": {"openLink": {"url": GRAFANA}}}
    ]


def test_umbral_minimo_y_decimales() -> None:
    autonomia = regla(Errores.AUTONOMIA_MINIMO)
    evento = Evento(UPS, autonomia.error, "abrir", INICIO, chequeo=Chequeo(autonomia, 7.5, True))

    assert widget(armar_mensaje(evento))["text"].endswith("<b>7,5 min</b></font> · mínimo 10 min")


def test_sensor_roto_no_muestra_umbral() -> None:
    roto = regla(Errores.UIO_ROTO)
    evento = Evento(UPS, roto.error, "abrir", INICIO, chequeo=Chequeo(roto, -1, True))

    texto = widget(armar_mensaje(evento))["text"]
    assert "valor imposible" in texto
    assert "mínimo" not in texto


def test_resolucion_con_valor_actual_y_duracion_sin_boton() -> None:
    fin = INICIO + timedelta(hours=2, minutes=15)
    evento = Evento(
        UPS, Errores.LOAD_MAXIMO, "cerrar", INICIO, fin, chequeo=Chequeo(LOAD, 48, False)
    )
    mensaje = armar_mensaje(evento, GRAFANA)

    assert mensaje["fallbackText"] == "✅ f1r11u1: Carga de salida normalizada (duró 2 h 15 min)"
    assert mensaje["cardsV2"][0]["card"]["header"]["subtitle"].startswith("Resuelto · ")
    texto = widget(mensaje)
    assert "<b>48 %</b>" in texto["text"]
    assert texto["text"].endswith("· duró 2 h 15 min")
    assert texto["startIcon"] == {"materialIcon": {"name": "check_circle"}}
    assert botones(mensaje) == []


def test_sin_respuesta_de_otro_tipo_de_equipo() -> None:
    evento = Evento(HUMEDAD, Errores.SIN_RESPUESTA_SNMP, "abrir", INICIO, fallas=3)
    mensaje = armar_mensaje(evento, GRAFANA)

    # El resumen nombra el tipo: el host es el mismo que el de un UPS
    assert mensaje["fallbackText"] == "⚠️ Sensor de humedad f2r7u1: Sin respuesta SNMP (no responde)"
    assert mensaje["cardsV2"][0]["card"]["header"]["title"] == "Sensor de humedad f2r7u1"
    assert "3 ejecuciones seguidas" in widget(mensaje)["text"]
    assert widget(mensaje)["startIcon"] == {"materialIcon": {"name": "error"}}


def test_resolucion_de_sin_respuesta() -> None:
    fin = INICIO + timedelta(minutes=12)
    mensaje = armar_mensaje(Evento(UPS, Errores.SIN_RESPUESTA_SNMP, "cerrar", INICIO, fin))

    assert mensaje["fallbackText"] == "✅ f1r11u1: Responde de nuevo por SNMP (duró 12 min)"
    assert widget(mensaje)["text"] == "duró 12 min"


def test_sin_grafana_no_hay_boton() -> None:
    evento = Evento(UPS, Errores.LOAD_MAXIMO, "abrir", INICIO, chequeo=Chequeo(LOAD, 63, True))
    assert botones(armar_mensaje(evento, None)) == []


def test_la_fecha_se_muestra_en_hora_local(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("TZ", "America/Argentina/Cordoba")
    time.tzset()
    try:
        evento = Evento(UPS, Errores.SIN_RESPUESTA_SNMP, "abrir", INICIO, fallas=3)
        subtitulo = armar_mensaje(evento)["cardsV2"][0]["card"]["header"]["subtitle"]
        assert subtitulo == "Alerta nueva · 12/10/2026 17:21"  # 20:21 UTC
    finally:
        monkeypatch.undo()
        time.tzset()

"""
Mensajes de Google Chat con tarjetas (cardsV2) a partir de los eventos del dominio (M10).

Cambiar el diseno de los mensajes se hace solo aca: ni las reglas ni los drivers saben de Chat.
Cada incidente tiene su hilo (threadKey): la alerta lo abre y la resolucion responde en el.
"""

from datetime import datetime
from typing import Any

from core.alertas import Evento, Numero
from core.errores import Errores

# Texto de cada error: (al abrirse, al resolverse)
TITULOS: dict[Errores, tuple[str, str]] = {
    Errores.TEMPERATURA_BATERIA_ALTA: (
        "Temperatura de batería alta",
        "Temperatura de batería normalizada",
    ),
    Errores.UIO_ROTO: ("Sensor de temperatura ambiente roto", "Sensor de temperatura ambiente OK"),
    Errores.UIO_TEMPERATURA_ALTA: ("Temperatura ambiente alta", "Temperatura ambiente normalizada"),
    Errores.CARGA_MINIMA: ("Carga de batería baja", "Carga de batería normalizada"),
    Errores.LOAD_MAXIMO: ("Carga de salida alta", "Carga de salida normalizada"),
    Errores.AUTONOMIA_MINIMO: ("Autonomía baja", "Autonomía normalizada"),
    Errores.SIN_RESPUESTA_SNMP: ("Sin respuesta SNMP", "Responde de nuevo por SNMP"),
}

COLOR_ALERTA = "#b3580b"
COLOR_SIN_RESPUESTA = "#b3261e"
COLOR_RESUELTO = "#1e7a46"


def clave_hilo(evento: Evento) -> str:
    """
    Identifica el hilo del incidente: equipo + error + inicio. La alerta y su resolucion tienen
    el mismo inicio (se guarda en la base), asi que caen en el mismo hilo.
    """
    return f"{evento.equipo.clave}-{evento.error.name}-{evento.inicio:%Y%m%dT%H%M%SZ}"


def formatear_numero(valor: Numero) -> str:
    """7.5 -> '7,5' y 25.0 -> '25' (coma decimal, sin decimales de mas)."""
    if float(valor).is_integer():
        return str(int(valor))
    return f"{valor:g}".replace(".", ",")


def formatear_duracion(inicio: datetime, fin: datetime) -> str:
    """'2 h 15 min', '12 min', '1 d 3 h' o 'menos de 1 min'."""
    minutos = int((fin - inicio).total_seconds() // 60)
    if minutos < 1:
        return "menos de 1 min"
    dias, minutos = divmod(minutos, 24 * 60)
    horas, minutos = divmod(minutos, 60)
    if dias:
        return f"{dias} d {horas} h" if horas else f"{dias} d"
    if horas:
        return f"{horas} h {minutos} min" if minutos else f"{horas} h"
    return f"{minutos} min"


def _con_unidad(valor: Numero, unidad: str) -> str:
    return f"{formatear_numero(valor)} {unidad}"


def _resaltado(texto: str, color: str) -> str:
    return f'<font color="{color}"><b>{texto}</b></font>'


def _detalle(evento: Evento) -> tuple[str, str]:
    """(texto de la tarjeta con formato, resumen corto para la notificacion)"""
    chequeo = evento.chequeo
    if evento.accion == "cerrar":
        duracion = f"duró {formatear_duracion(evento.inicio, evento.fin or evento.inicio)}"
        if chequeo is None:
            return duracion, f"({duracion})"
        valor = _con_unidad(chequeo.valor, chequeo.regla.unidad)
        return f"{_resaltado(valor, COLOR_RESUELTO)} · {duracion}", f"({duracion})"

    if evento.error == Errores.SIN_RESPUESTA_SNMP:
        texto = f"{evento.fallas} ejecuciones seguidas" if evento.fallas else "sin respuesta"
        return f"{_resaltado(texto, COLOR_SIN_RESPUESTA)} sin respuesta", "(no responde)"

    if chequeo is None:  # no deberia pasar: todo error que no es SIN_RESPUESTA sale de una regla
        return "", ""
    regla = chequeo.regla
    valor = _con_unidad(chequeo.valor, regla.unidad)
    if evento.error == Errores.UIO_ROTO:
        return f"lee {_resaltado(valor, COLOR_ALERTA)} (valor imposible)", f"({valor})"
    limite = "máximo" if regla.condicion == "max" else "mínimo"
    umbral = _con_unidad(regla.umbral, regla.unidad)
    return f"{_resaltado(valor, COLOR_ALERTA)} · {limite} {umbral}", f"({valor})"


def armar_mensaje(evento: Evento, grafana_url: str | None = None) -> dict[str, Any]:
    """
    Cuerpo del POST al webhook: `cardsV2` es la tarjeta que se ve en el espacio y
    `fallbackText` el resumen que se usa donde no se puede mostrar la tarjeta (la notificacion
    del celular). No se usa `text`: Chat lo mostraria como un mensaje aparte, repetido arriba
    de la tarjeta.
    Las fechas se muestran en la hora local del proceso (TZ del contenedor).
    """
    equipo = evento.equipo
    abre = evento.accion == "abrir"
    titulo = TITULOS[evento.error][0 if abre else 1]
    detalle, resumen = _detalle(evento)
    fecha = (evento.inicio if abre else evento.fin or evento.inicio).astimezone()

    if not abre:
        icono, color_estado = "check_circle", COLOR_RESUELTO
    elif evento.error == Errores.SIN_RESPUESTA_SNMP:
        icono, color_estado = "error", COLOR_SIN_RESPUESTA
    else:
        icono, color_estado = "warning", COLOR_ALERTA

    widgets: list[dict[str, Any]] = [
        {
            "decoratedText": {
                "startIcon": {"materialIcon": {"name": icono}},
                "topLabel": titulo,
                "text": detalle or _resaltado(titulo, color_estado),
            }
        }
    ]
    if abre and grafana_url:
        widgets.append(
            {
                "buttonList": {
                    "buttons": [
                        {"text": "Ver en Grafana", "onClick": {"openLink": {"url": grafana_url}}}
                    ]
                }
            }
        )

    # "UPS f1r11u1" en la tarjeta; en el resumen alcanza el host, salvo en los equipos que no
    # son un UPS comun (el sensor de humedad comparte host con un UPS)
    nombre = f"{equipo.tipo} {equipo.hostname}"
    nombre_corto = equipo.hostname if equipo.tipo == "UPS" else nombre
    emoji = "⚠️" if abre else "✅"
    return {
        "fallbackText": f"{emoji} {nombre_corto}: {titulo} {resumen}".rstrip(),
        "cardsV2": [
            {
                "cardId": clave_hilo(evento),
                "card": {
                    "header": {
                        "title": nombre,
                        "subtitle": f"{'Alerta nueva' if abre else 'Resuelto'} · "
                        f"{fecha:%d/%m/%Y %H:%M}",
                    },
                    "sections": [{"widgets": widgets}],
                },
            }
        ],
    }

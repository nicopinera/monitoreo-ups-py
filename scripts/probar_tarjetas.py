"""
Envia tarjetas de ejemplo a un webhook de Google Chat, para ver como quedan sin esperar una
alerta real. Uso (con el webhook de un espacio de PRUEBA, nunca el de produccion):

    make probar-tarjetas WEBHOOK='https://chat.googleapis.com/v1/spaces/.../messages?key=...&token=...'

No lee el .env a proposito: el webhook se pasa explicito en cada uso. Los mensajes son los
mismos que arma el monitoreo (mismo formateador); los datos son de ejemplo.
"""

import sys
from datetime import UTC, datetime, timedelta
from urllib.parse import parse_qs, urlsplit

from config.configuracion import REGLAS_UPS
from config.entorno import GRAFANA_URL_DEFECTO
from core.alertas import Chequeo, Equipo, Evento, Regla
from core.errores import Errores
from infraestructura.notificador import Notificador


def _regla(error: Errores) -> Regla:
    return next(regla for regla in REGLAS_UPS if regla.error == error)


def eventos_de_ejemplo(ahora: datetime) -> list[Evento]:
    """Los escenarios de la maqueta: alerta y resolucion en su hilo, sin respuesta y varias."""
    ups = Equipo("f1r11u1", "UPS", "f1r11u1-prueba")
    otro = Equipo("f2r10u1", "UPS", "f2r10u1-prueba")
    humedad = Equipo("f2r7u1", "Sensor de humedad", "f2r7u1-humedad-prueba")
    varios = Equipo("f3r6u1", "UPS", "f3r6u1-prueba")

    load = _regla(Errores.LOAD_MAXIMO)
    inicio_load = ahora - timedelta(hours=2, minutes=15)
    inicio_snmp = ahora - timedelta(minutes=12)
    return [
        # 1. Alerta y su resolucion, en el mismo hilo (mismo equipo, error e inicio)
        Evento(ups, load.error, "abrir", inicio_load, chequeo=Chequeo(load, 63, True)),
        Evento(ups, load.error, "cerrar", inicio_load, ahora, chequeo=Chequeo(load, 48, False)),
        # 2. Un equipo que deja de responder y vuelve
        Evento(otro, Errores.SIN_RESPUESTA_SNMP, "abrir", inicio_snmp, fallas=3),
        Evento(otro, Errores.SIN_RESPUESTA_SNMP, "cerrar", inicio_snmp, ahora),
        Evento(humedad, Errores.SIN_RESPUESTA_SNMP, "abrir", ahora, fallas=3),
        # 3. Varias alertas del mismo equipo: una tarjeta (y un hilo) por incidente
        *(
            Evento(varios, regla.error, "abrir", ahora, chequeo=Chequeo(regla, valor, True))
            for regla, valor in (
                (_regla(Errores.TEMPERATURA_BATERIA_ALTA), 31),
                (_regla(Errores.AUTONOMIA_MINIMO), 7.5),
                (_regla(Errores.UIO_ROTO), -1),
            )
        ),
    ]


def limpiar_webhook(url: str) -> str:
    """
    Quita las barras invertidas que zsh agrega al pegar una URL (messages\\?key\\=...): una URL
    de webhook nunca las tiene, y con ellas Google no ve key ni token y responde 403.
    """
    return url.replace("\\", "")


def main(argv: list[str]) -> int:
    url = limpiar_webhook(argv[1]) if len(argv) == 2 else ""
    parametros = parse_qs(urlsplit(url).query)
    if not url.startswith("https://") or "key" not in parametros or "token" not in parametros:
        print(
            "Uso: make probar-tarjetas WEBHOOK='https://chat.googleapis.com/...?key=...&token=...'\n"
            "La URL completa del webhook, con key y token, entre comillas simples.\n"
            "Usar el webhook de un espacio de prueba, no el de produccion.",
            file=sys.stderr,
        )
        return 2
    notificador = Notificador(url, timeout=10.0, grafana_url=GRAFANA_URL_DEFECTO)
    ahora = datetime.now(UTC).replace(microsecond=0)
    fallidos = 0
    for evento in eventos_de_ejemplo(ahora):
        ok = notificador.notificar(evento)
        fallidos += not ok
        estado = "enviado" if ok else "ERROR (ver el detalle arriba)"
        print(f"{evento.equipo.hostname} {evento.error.name} {evento.accion}: {estado}")
    return 1 if fallidos else 0


if __name__ == "__main__":
    import logging

    logging.basicConfig(level=logging.WARNING, format="%(levelname)s %(message)s")
    sys.exit(main(sys.argv))

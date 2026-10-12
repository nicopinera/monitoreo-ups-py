"""
Decide que avisar a partir de la Lectura de un driver, para cualquier equipo.

Las alertas son por cambio de estado: se avisa cuando un error aparece (se abre un incidente) y
cuando se resuelve (se cierra), no en cada ejecucion. El estado vive en la base (incidentes).
"""

import logging
from collections.abc import Callable
from datetime import UTC, datetime
from typing import TYPE_CHECKING

from core.alertas import Chequeo, Evento
from core.errores import Errores
from core.ups_base import Lectura

if TYPE_CHECKING:
    from infraestructura.database import RepositorioDB
    from infraestructura.notificador import Notificador

logger = logging.getLogger(__name__)


def ahora_utc() -> datetime:
    # Sin microsegundos: la base guarda segundos y el inicio identifica al hilo del chat
    return datetime.now(UTC).replace(microsecond=0)


class GestorAlertas:
    def __init__(
        self,
        repo_db: "RepositorioDB",
        notificador: "Notificador",
        fallas_para_alerta: int = 1,
        reloj: Callable[[], datetime] = ahora_utc,
    ) -> None:
        """
        fallas_para_alerta: ejecuciones seguidas sin respuesta SNMP antes de avisar.
        reloj: fecha y hora actual en UTC (los tests la fijan).
        """
        self.repo_db = repo_db
        self.notificador = notificador
        self.fallas_para_alerta = fallas_para_alerta
        self.reloj = reloj

    def procesar(self, lectura: Lectura) -> None:
        """
        Detecta los cambios de estado y avisa cada uno por separado (cada incidente tiene su
        propio hilo en el chat). Un cambio se guarda en la base recien si su aviso se envio: si
        falla, en la proxima ejecucion se detecta otra vez y se reintenta (nunca se pierde, A8).
        """
        for evento in self._detectar(lectura):
            if self.notificador.notificar(evento):
                self._confirmar(evento)
            else:
                logger.warning(
                    "No se pudo notificar %s (%s): se reintenta en la proxima ejecucion",
                    evento.equipo.clave,
                    evento.error.name,
                )

    # ------------------------------------------------------------------ deteccion

    def _detectar(self, lectura: Lectura) -> list[Evento]:
        """Compara la lectura con los incidentes abiertos, sin escribir incidentes."""
        eventos = [self._detectar_sin_respuesta(lectura)]
        eventos += [
            self._detectar_cambio(lectura, chequeo.regla.error, chequeo.en_alerta, chequeo=chequeo)
            for chequeo in lectura.chequeos
        ]
        return [evento for evento in eventos if evento is not None]

    def _detectar_sin_respuesta(self, lectura: Lectura) -> Evento | None:
        """
        SIN_RESPUESTA_SNMP se avisa recien despues de `fallas_para_alerta` ejecuciones seguidas
        sin respuesta: un paquete UDP perdido o un equipo lento una vez no es una alerta. Se
        resuelve con la primera respuesta. La cuenta se guarda en la base entre ejecuciones.
        """
        clave = lectura.equipo.clave
        nombre = Errores.SIN_RESPUESTA_SNMP.name
        if lectura.hay_datos:
            self.repo_db.reiniciar_fallas(clave, nombre)
            return self._detectar_cambio(lectura, Errores.SIN_RESPUESTA_SNMP, en_alerta=False)

        fallas = self.repo_db.sumar_falla(clave, nombre)
        if fallas < self.fallas_para_alerta:
            logger.info(
                "%s sin respuesta SNMP (%d de %d ejecuciones seguidas para avisar)",
                clave,
                fallas,
                self.fallas_para_alerta,
            )
            return None
        return self._detectar_cambio(
            lectura, Errores.SIN_RESPUESTA_SNMP, en_alerta=True, fallas=fallas
        )

    def _detectar_cambio(
        self,
        lectura: Lectura,
        error: Errores,
        en_alerta: bool,
        *,
        chequeo: Chequeo | None = None,
        fallas: int | None = None,
    ) -> Evento | None:
        """
        - En alerta y sin incidente abierto -> abrir.
        - Sin alerta y con incidente abierto -> cerrar (con el inicio, para la duracion y el hilo).
        - Si no, no cambio nada: None.
        """
        abierto = self.repo_db.incidente_abierto(lectura.equipo.clave, error.name)
        if en_alerta and abierto is None:
            return Evento(
                lectura.equipo, error, "abrir", self.reloj(), chequeo=chequeo, fallas=fallas
            )
        if not en_alerta and abierto is not None:
            return Evento(
                lectura.equipo, error, "cerrar", abierto.inicio, fin=self.reloj(), chequeo=chequeo
            )
        return None

    def _confirmar(self, evento: Evento) -> None:
        """Guarda en la base un cambio ya avisado."""
        clave, nombre = evento.equipo.clave, evento.error.name
        if evento.accion == "abrir":
            self.repo_db.abrir_incidente(clave, nombre, evento.inicio)
        else:
            # Un evento "cerrar" siempre trae fin; el reloj es solo para que mypy lo sepa
            self.repo_db.cerrar_incidente(clave, nombre, evento.fin or self.reloj())

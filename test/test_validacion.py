from core.errores import Errores
from core.validacion import (
    validar_carga,
    validar_load,
    validar_respuesta_snmp,
    validar_temp_bateria,
    validar_temp_uio,
    validar_tiempo_autonomia,
)


def test_validar_temp_bateria_ok():
    valor_temperatura_bat = 20  # Valor de temperatura correcto
    error, msj = validar_temp_bateria(valor=valor_temperatura_bat)
    assert error is None
    assert msj is None


def test_validar_temp_bateria_fallo():
    valor_aux_temp_bat = 30  # Valor mayor de lo correcto
    msj_esperado = f"[ADVERTENCIA] *{Errores.TEMPERATURA_BATERIA_ALTA.name}*: Valor actual *{valor_aux_temp_bat} [°C]*"
    error, msj = validar_temp_bateria(valor=valor_aux_temp_bat)
    assert error is not None
    assert msj is not None
    assert error.name == Errores.TEMPERATURA_BATERIA_ALTA.name
    assert error.value == Errores.TEMPERATURA_BATERIA_ALTA.value
    assert msj == msj_esperado


def test_validar_uio_ok():
    valor_aux_uio = 20  # Valor de temperatura correcto
    error, msj = validar_temp_uio(valor=valor_aux_uio)
    assert error is None
    assert msj is None


def test_validar_uio_roto():
    valor_aux_temp_uio = -1  # Valor UIO roto
    msj_esperado = "[ADVERTENCIA] Sensor de Temperatura Roto"
    error, msj = validar_temp_uio(valor=valor_aux_temp_uio)
    assert error is not None
    assert msj is not None
    assert error.name == Errores.UIO_ROTO.name
    assert error.value == Errores.UIO_ROTO.value
    assert msj == msj_esperado


def test_validar_uio_alta():
    valor_aux_temp_uio = 30  # Valor UIO roto
    msj_esperado = f"[ADVERTENCIA] *{Errores.UIO_TEMPERATURA_ALTA.name}*: Valor actual *{valor_aux_temp_uio} [°C]*"
    error, msj = validar_temp_uio(valor=valor_aux_temp_uio)
    assert error is not None
    assert msj is not None
    assert error.name == Errores.UIO_TEMPERATURA_ALTA.name
    assert error.value == Errores.UIO_TEMPERATURA_ALTA.value
    assert msj == msj_esperado


def test_validar_carga_ok():
    valor_carga = 90  # Valor de temperatura correcto
    error, msj = validar_carga(valor=valor_carga)
    assert error is None
    assert msj is None


def test_validar_carga_fallo():
    valor_carga = 50  # Valor mayor de lo correcto
    msj_esperado = f"[ADVERTENCIA] *{Errores.CARGA_MINIMA.name}*: Valor actual *{valor_carga} %*"
    error, msj = validar_carga(valor=valor_carga)
    assert error is not None
    assert msj is not None
    assert error.name == Errores.CARGA_MINIMA.name
    assert error.value == Errores.CARGA_MINIMA.value
    assert msj == msj_esperado


def test_validar_load_ok():
    valor_load = 46  # El valor reportado no debe superar el nuevo umbral
    error, msj = validar_load(valor=valor_load)
    assert error is None
    assert msj is None


def test_validar_load_fallo():
    valor_load = 61  # Valor por encima del nuevo umbral
    msj_esperado = f"[ADVERTENCIA] *{Errores.LOAD_MAXIMO.name}*: Valor actual *{valor_load} %*"
    error, msj = validar_load(valor=valor_load)
    assert error is not None
    assert msj is not None
    assert error.name == Errores.LOAD_MAXIMO.name
    assert error.value == Errores.LOAD_MAXIMO.value
    assert msj == msj_esperado


def test_validar_autonomia_ok():
    valor_autonomia = 10.5  # Valor de temperatura correcto
    error, msj = validar_tiempo_autonomia(valor=valor_autonomia)
    assert error is None
    assert msj is None


def test_validar_autonomia_fallo():
    valor_autonomia = 5.5  # Valor mayor de lo correcto
    msj_esperado = (
        f"[ADVERTENCIA] *{Errores.AUTONOMIA_MINIMO.name}*: Valor actual *{valor_autonomia} [min]*"
    )
    error, msj = validar_tiempo_autonomia(valor=valor_autonomia)
    assert error is not None
    assert msj is not None
    assert error.name == Errores.AUTONOMIA_MINIMO.name
    assert error.value == Errores.AUTONOMIA_MINIMO.value
    assert msj == msj_esperado


def test_validar_respuesta_snmp_ok():
    error, msj = validar_respuesta_snmp(hay_datos=True)
    assert error is None
    assert msj is None


def test_validar_respuesta_snmp_fallo():
    msj_esperado = f"[ADVERTENCIA] *{Errores.SIN_RESPUESTA_SNMP.name}*: El equipo no respondió a ninguna consulta SNMP"
    error, msj = validar_respuesta_snmp(hay_datos=False)
    assert error.name == Errores.SIN_RESPUESTA_SNMP.name
    assert error.value == Errores.SIN_RESPUESTA_SNMP.value
    assert msj == msj_esperado

import pytest
import os
import sqlite3
from src.infraestructura.database import RepositorioDB

@pytest.fixture
def db_repo(tmp_path):
    # Creamos una base de datos temporal para cada test
    db_file = tmp_path / "test_errores.db"
    # El RepositorioDB usará el script SQL real definido en la configuración
    repo = RepositorioDB(str(db_file))
    return repo

def test_creacion_tablas(db_repo):
    """Verifica que las tablas se creen correctamente al inicializar."""
    with sqlite3.connect(db_repo.db_file) as conn:
        cursor = conn.cursor()
        cursor.execute("SELECT name FROM sqlite_master WHERE type='table' AND name='errores'")
        assert cursor.fetchone() is not None

def test_agregar_y_consultar_error_activo(db_repo):
    """Prueba que un error se agregue y se pueda encontrar como activo."""
    host = "ups-test"
    error = "BATERIA_BAJA"
    
    db_repo.agregar_error(host, error)
    resultado = db_repo.error_activo(host, error)
    
    assert resultado is not None
    assert resultado[1] == host # ups_host
    assert resultado[2] == error # tipo_error
    assert resultado[3] == "activo" # estado_error

def test_resolver_error(db_repo):
    """Prueba que un error activo pase a estado resuelto."""
    host = "ups-test"
    error = "SOBRECARGA"
    
    db_repo.agregar_error(host, error)
    db_repo.resolver_error(host, error)
    
    # No debe haber error activo
    assert db_repo.error_activo(host, error) is None
    
    # Debe aparecer como resuelto
    resuelto = db_repo.error_resuelto(host, error)
    assert resuelto is not None
    assert resuelto[3] == "resuelto"

def test_activar_error_resuelto(db_repo):
    """Prueba que un error resuelto pueda volver a activarse."""
    host = "ups-test"
    error = "TEMPERATURA"
    
    # 1. Creamos y resolvemos
    db_repo.agregar_error(host, error)
    db_repo.resolver_error(host, error)
    assert db_repo.error_activo(host, error) is None
    
    # 2. Reactivamos
    db_repo.activar_error(host, error)
    
    # 3. Debe volver a estar activo
    activo = db_repo.error_activo(host, error)
    assert activo is not None
    assert activo[3] == "activo"

def test_historial_errores(db_repo):
    """Verifica que el sistema distinga entre errores de diferentes hosts."""
    db_repo.agregar_error("UPS-A", "ERROR_1")
    db_repo.agregar_error("UPS-B", "ERROR_1")
    
    assert db_repo.error_activo("UPS-A", "ERROR_1") is not None
    assert db_repo.error_activo("UPS-B", "ERROR_1") is not None
    
    db_repo.resolver_error("UPS-A", "ERROR_1")
    
    assert db_repo.error_activo("UPS-A", "ERROR_1") is None
    assert db_repo.error_activo("UPS-B", "ERROR_1") is not None

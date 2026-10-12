-- Esquema de data/errores-v2.db. Se ejecuta en cada arranque: todo es IF NOT EXISTS.
-- Las fechas se guardan en UTC (CURRENT_TIMESTAMP de SQLite): se convierten a hora local
-- recien al mostrarlas.

-- Un incidente por fila: desde que se aviso un error hasta que se aviso su resolucion.
-- Abierto (fin NULL) = error activo. Cerrados = historial, con su duracion (fin - inicio).
CREATE TABLE IF NOT EXISTS incidentes(
    id INTEGER PRIMARY KEY,
    ups_host TEXT NOT NULL,
    tipo_error TEXT NOT NULL,
    inicio TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,
    fin TIMESTAMP,
    CHECK (fin IS NULL OR fin >= inicio)
);

-- La base garantiza que un error tenga como mucho un incidente abierto por equipo.
-- Ademas es el indice que usa la consulta del estado actual.
CREATE UNIQUE INDEX IF NOT EXISTS incidente_abierto
    ON incidentes(ups_host, tipo_error) WHERE fin IS NULL;

-- Ejecuciones seguidas en las que se detecto un error que todavia no se aviso (por ahora solo
-- SIN_RESPUESTA_SNMP). Se borra cuando el error desaparece.
CREATE TABLE IF NOT EXISTS fallas_consecutivas(
    ups_host TEXT NOT NULL,
    tipo_error TEXT NOT NULL,
    cantidad INTEGER NOT NULL CHECK (cantidad > 0),
    PRIMARY KEY (ups_host, tipo_error)
);

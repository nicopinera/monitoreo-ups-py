CREATE TABLE IF NOT EXISTS errores(
    id INTEGER PRIMARY KEY,
    ups_host TEXT NOT NULL,
    tipo_error TEXT NOT NULL,
    estado_error TEXT NOT NULL CHECK (estado_error IN ('activo', 'resuelto')),
    fecha TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP
);
# Diagnóstico y Soluciones: Problemas de Imports y Ejecución

## Problemas encontrados

### 1. **Error: `ModuleNotFoundError: No module named 'config'`**

**Causa**: Cuando ejecutas `python3 -c "..."` o `python3 src/main.py` desde la raíz, Python no incluye el directorio `src/` en el `sys.path`. Por lo tanto, los imports como `import config.configuracion as c` fallan porque Python busca `config/` en la raíz, no dentro de `src/`.

**Línea del error**:
```python
# src/config/logger.py, línea 4
import config.configuracion as c  # ❌ Falla si src/ no está en el path
```

---

### 2. **Error: `ModuleNotFoundError: No module named 'src'`**

**Causa**: En `src/drivers/state_ups.py` (y otros drivers) había imports inconsistentes que asumían ejecutarse desde la raíz del proyecto:

```python
# src/drivers/state_ups.py, línea 2
from src.core.ups_base import BaseUPS  # ❌ Busca 'src' dentro de 'src/'
```

Esto sucede porque:
- `src/main.py` usa imports relativos: `from drivers.state_ups import StateUPS`
- Pero `src/drivers/state_ups.py` usa imports absolutos: `from src.core.ups_base import BaseUPS`

Resulta en un conflicto: cuando `main.py` importa `drivers/state_ups.py`, ese módulo intenta importar `src.core...`, pero ya está dentro de `src/`, así que falla.

---

## Soluciones implementadas

### 1. **Corregir imports en todos los drivers** ✅

Se cambió en `src/drivers/state_ups.py`, `src/drivers/dc_ups.py`, `src/drivers/hum_ups.py`:

**Antes**:
```python
from src.core.ups_base import BaseUPS       # ❌ Ruta absoluta desde raíz
```

**Ahora**:
```python
from core.ups_base import BaseUPS          # ✅ Ruta relativa a src/
```

---

### 2. **Crear script wrapper `run.py`** ✅

Se creó un archivo `run.py` en la raíz que:
- Agrega `src/` al `sys.path` automáticamente.
- Importa y ejecuta `main()`.
- Permite ejecutar desde la raíz sin problemas de imports.

```bash
python3 run.py
```

---

## Cómo ejecutar el programa correctamente

### Opción 1: Usar el script wrapper (recomendado)
```bash
python3 run.py
```

### Opción 2: Ejecutar con `-m` desde la raíz
```bash
cd /home/juan_ignacio/Documentos/monitoreo-ups
python3 -m src.main
```

### ❌ NO hacer esto:
```bash
python3 src/main.py          # Falla: imports con rutas relativas no funcionan
python3 -c "from main..."    # Falla: no puede encontrar módulos internos
```

---

## Validaciones completadas

### ✅ Sintaxis verificada
```bash
python3 -m py_compile src/config/logger.py src/main.py src/infraestructura/...
# ✓ Sin errores
```

### ✅ Logger funciona correctamente
```bash
python3 -c "import sys; sys.path.insert(0, 'src'); from config.logger import ..."
# Salida esperada:
# 2026-05-06 12:19:56,554 - test - INFO - ✓ INFO ok
# 2026-05-06 12:19:56,555 - test - ERROR - ✓ ERROR ok
# metric,host=test value=1   (sin timestamp - limpio para Telegraf)
```

### ✅ Archivos de log creados correctamente
```
logs/
├── app.log      (contiene INFO + ERROR)
├── errors.log   (contiene solo ERROR)
└── .gitignore   (excluye logs/ del repositorio)
```

**Verificación**:
```bash
tail -n 3 logs/app.log
# 2026-05-06 12:19:56,554 - test - INFO - ✓ INFO ok
# 2026-05-06 12:19:56,555 - test - ERROR - ✓ ERROR ok

tail -n 3 logs/errors.log
# 2026-05-06 12:19:56,555 - test - ERROR - ✓ ERROR ok
```

---

## Próximos pasos para probar el sistema completo

1. **Si tienes SNMP configurado y `.env` con credenciales válidas**:
   ```bash
   python3 run.py
   ```
   Luego verifica:
   ```bash
   tail -f logs/app.log          # Ver eventos en vivo
   tail -f logs/errors.log       # Ver errores en vivo
   ```

2. **Si no tienes SNMP pero quieres probar el logger**:
   ```bash
   python3 run.py 2>&1 | head -20   # Verá errores de conexión SNMP (normales)
   ```
   Aun así, los logs se guardarán correctamente.

3. **Revisar estructura de directorios**:
   ```bash
   tree logs/ -a
   # logs/
   # ├── .gitignore
   # ├── app.log
   # └── errors.log
   ```

---

## Resumen de cambios

| Archivo | Cambio | Razón |
|---------|--------|-------|
| `src/drivers/state_ups.py` | `from src.core...` → `from core...` | Consistencia de imports relativos |
| `src/drivers/dc_ups.py` | `from src.core...` → `from core...` | Consistencia de imports relativos |
| `src/drivers/hum_ups.py` | `from src.core...` → `from core...` | Consistencia de imports relativos |
| `run.py` | Nuevo archivo | Facilita ejecución desde raíz |
| `.gitignore` | Agregado `logs/` | Excluir archivos de log |
| `logs/.gitignore` | Nuevo archivo | Mantener directorio en git |

---

## Si aún hay problemas

Ejecuta desde la raíz del proyecto:
```bash
python3 -c "import sys; sys.path.insert(0, 'src'); from main import main; main()"
```

Esto es equivalente a `python3 run.py`.

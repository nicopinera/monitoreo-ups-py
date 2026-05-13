# Guía de Documentación: Sphinx y Swagger/OpenAPI

## Índice
1. [Introducción](#introducción)
2. [Instalación de Sphinx](#instalación-de-sphinx)
3. [Configuración de Sphinx](#configuración-de-sphinx)
4. [Generación de Documentación](#generación-de-documentación)
5. [Integración con Swagger/OpenAPI](#integración-con-swaggeropenapi)
6. [Publicación en ReadTheDocs](#publicación-en-readthedocs)

---

## Introducción

Este proyecto utiliza **Sphinx** como herramienta principal para la generación automática de documentación a partir de docstrings en código Python. La documentación está diseñada siguiendo el estándar **Google Style** de docstrings, compatible con `sphinx.ext.napoleon`.

### ¿Qué es Sphinx?

Sphinx es una herramienta poderosa que:
- Genera documentación en múltiples formatos (HTML, PDF, ePub)
- Extrae automáticamente docstrings del código Python
- Crea tablas de contenido, índices, y referencias cruzadas
- Soporta temas profesionales como ReadTheDocs

### Estructura de Docstrings Soportados

Todos los módulos, clases, funciones y métodos siguen el formato **Google Style**:

```python
def ejemplo_funcion(param1, param2):
    """Brief description of the function.
    
    More detailed explanation if needed.
    
    Args:
        param1 (str): Description of param1.
        param2 (int): Description of param2.
        
    Returns:
        bool: Description of return value.
        
    Raises:
        ValueError: When something is invalid.
        TypeError: When type is wrong.
    """
    pass
```

---

## Instalación de Sphinx

### Paso 1: Crear un entorno virtual (recomendado)

```bash
# Navegar al directorio raíz del proyecto
cd /home/nacho/Trabajo/monitoreo-ups

# Crear entorno virtual
python3 -m venv venv

# Activar entorno virtual
source venv/bin/activate  # En Windows: venv\Scripts\activate
```

### Paso 2: Instalar Sphinx y dependencias

```bash
# Instalar desde requirements.txt
pip install -r requirements.txt

# O instalar manualmente
pip install sphinx sphinx-rtd-theme sphinx-napoleon
```

### Paso 3: Verificar instalación

```bash
sphinx-build --version
```

Deberías ver algo como: `sphinx-build 4.5.0`

---

## Configuración de Sphinx

### Paso 1: Crear estructura de documentación (primera vez)

Si Sphinx no está aún configurado:

```bash
cd docs
sphinx-quickstart .
```

Responde las preguntas interactivas:
- **Project name**: "Monitoreo UPS"
- **Author name**: "Tu Nombre"
- **Version**: "1.0.0"
- **Release**: "1.0.0"
- **Language**: "es" (para Spanish)

Esto crea automáticamente `conf.py` y plantillas base.

### Paso 2: Configurar `conf.py` para Google Style Docstrings

Edita `docs/conf.py` y asegúrate que incluya:

```python
# Extensiones necesarias
extensions = [
    'sphinx.ext.autodoc',       # Extrae docstrings del código
    'sphinx.ext.napoleon',       # Convierte Google Style a reStructuredText
    'sphinx.ext.viewcode',       # Enlaza al código fuente
    'sphinx.ext.todo',
    'sphinx.ext.mathjax',        # Soporte para matemáticas
]

# Configuración de Napoleon para Google Style
napoleon_google_docstring = True
napoleon_numpy_docstring = False
napoleon_include_init_with_doc = False
napoleon_include_private_with_doc = False
napoleon_attr_annotations = True

# Tema profesional
html_theme = 'sphinx_rtd_theme'

# Opciones del tema
html_theme_options = {
    'logo_only': False,
    'display_version': True,
    'prev_next_buttons_location': 'bottom',
    'style_external_links': False,
}

# Ruta al código fuente (relativa a conf.py)
import sys
import os
sys.path.insert(0, os.path.abspath('../src'))

# Configuración de autodoc
autodoc_default_options = {
    'members': True,
    'member-order': 'bysource',
    'special-members': '__init__',
    'undoc-members': True,
    'show-inheritance': True,
}
```

### Paso 3: Crear índice principal (`index.rst`)

Edita `docs/index.rst`:

```rst
Documentación - Monitoreo UPS
=============================

Sistema de monitoreo completo para equipos UPS en datacenter.

.. toctree::
   :maxdepth: 2
   :caption: Contenidos:

   instalacion
   uso
   api/modules
   guia_tecnica

Índices y Tablas
================

* :ref:`genindex`
* :ref:`modindex`
* :ref:`search`
```

### Paso 4: Crear módulos de documentación automática

En `docs/source`, crea archivos `.rst` para cada módulo:

```bash
mkdir -p docs/source
```

Crea `docs/source/modules.rst`:

```rst
API Reference
=============

.. toctree::
   :maxdepth: 2

   core
   drivers
   infraestructura
   config
```

Crea `docs/source/core.rst`:

```rst
Core Module
===========

.. automodule:: core.errores
   :members:
   :undoc-members:
   :show-inheritance:

.. automodule:: core.validacion
   :members:
   :undoc-members:
   :show-inheritance:

.. automodule:: core.ups_base
   :members:
   :undoc-members:
   :show-inheritance:
```

Repite para `drivers.rst`, `infraestructura.rst`, `config.rst`.

---

## Generación de Documentación

### Comando básico

```bash
cd docs
make html
```

Esto genera HTML en `docs/_build/html/`. Abre `docs/_build/html/index.html` en tu navegador.

### Limpiar y regenerar

```bash
make clean
make html
```

### Generar en otros formatos

```bash
make pdf       # Requiere LaTeX
make epub      # Libro electrónico
```

### Validar con sphinx-build directo

```bash
sphinx-build -b html docs/ docs/_build/html -W --keep-going
```

Flags:
- `-W`: Trata advertencias como errores (strict mode)
- `--keep-going`: Continúa después de errores
- `-b html`: Backend HTML

---

## Integración con Swagger/OpenAPI

### Contexto del Proyecto

**Importante**: El proyecto actual **no tiene endpoints web** (es CLI/daemon). 

Swagger/OpenAPI es útil si el proyecto se expande con una API REST. La siguiente sección documenta **cómo implementarlo si se necesita en el futuro**.

### Caso de Uso: Exposición de Monitoreo vía API REST

Si se desea crear endpoints web para consultar estado UPS, se podría implementar así:

#### Opción 1: FastAPI (Recomendado por documentación automática)

```bash
pip install fastapi uvicorn
```

Crear `src/api/main.py`:

```python
"""REST API for UPS monitoring endpoints.

Provides HTTP endpoints for querying UPS status, historical data,
and triggering manual monitoring cycles.
"""

from fastapi import FastAPI
from fastapi.openapi.utils import get_openapi

app = FastAPI(
    title="Monitoreo UPS API",
    description="API REST para consulta de estado de equipos UPS",
    version="1.0.0",
)

@app.get("/api/v1/ups/{hostname}/status")
async def get_ups_status(hostname: str):
    """Obtener estado actual de un UPS.
    
    Args:
        hostname: Nombre corto del UPS (ej: f1r2u1)
        
    Returns:
        dict: Métricas actuales del UPS (battery, temp, capacity, load, life, current)
    """
    pass

@app.get("/api/v1/ups")
async def list_all_ups():
    """Listar todos los UPS disponibles en el sistema.
    
    Returns:
        list: Lista de hostnames monitorados
    """
    pass

@app.get("/docs")
async def swagger_docs():
    """Documentación interactiva Swagger (auto-generada)."""
    pass

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8000)
```

Ejecutar:
```bash
cd src
python -m api.main
```

Swagger UI se abre automáticamente en: `http://localhost:8000/docs`

#### Opción 2: Flask + Flasgger

```bash
pip install flask flasgger
```

Crear `src/api/flask_api.py`:

```python
"""REST API for UPS monitoring using Flask."""

from flask import Flask
from flasgger import Swagger

app = Flask(__name__)
swagger = Swagger(app)

@app.route('/api/v1/ups/<hostname>/status', methods=['GET'])
def get_ups_status(hostname):
    """
    Obtener estado de un UPS
    ---
    parameters:
      - name: hostname
        in: path
        type: string
        required: true
        description: Nombre corto del UPS
    responses:
      200:
        description: Métricas del UPS
        schema:
          properties:
            battery:
              type: number
            temp:
              type: number
            capacity:
              type: number
    """
    pass

if __name__ == '__main__':
    app.run(debug=True, port=5000)
```

Swagger UI en: `http://localhost:5000/apidocs/`

---

## Publicación en ReadTheDocs

### Paso 1: Preparar repositorio Git

```bash
git init
git add .
git commit -m "Initial commit with Sphinx documentation"
git push origin main
```

### Paso 2: Registrarse en ReadTheDocs

Ir a https://readthedocs.org y crear cuenta.

### Paso 3: Importar Proyecto

1. Click en "Import a Project"
2. Seleccionar tu repositorio de GitHub
3. ReadTheDocs automáticamente detectará `docs/conf.py`
4. Configurar en Settings:
   - Python version: 3.9+
   - Requirements file: `requirements.txt`
   - Default branch: `main`

### Paso 4: Crear archivo `.readthedocs.yml`

En la raíz del proyecto, crear `.readthedocs.yml`:

```yaml
version: 2

build:
  os: ubuntu-20.04
  tools:
    python: "3.9"

python:
  install:
    - requirements: requirements.txt
    
sphinx:
  configuration: docs/conf.py
  
formats:
  - pdf
  - epub
```

### Paso 5: Disparar build

Hacer push a GitHub:
```bash
git push origin main
```

ReadTheDocs automáticamente disparará un build. Ver progreso en el dashboard.

---

## Validación y Testing de Documentación

### Verificar estructura de docstrings

```bash
# Usando sphinx-build con warnings estrictos
sphinx-build -b html docs/ docs/_build/html -W

# Usando pylint (si está instalado)
pylint --disable=all --enable=missing-docstring src/
```

### Verificar enlaces rotos

```bash
# Instalar
pip install sphinx-linkcheck

# Ejecutar en conf.py: extensions += ['sphinx.ext.linkcheck']
# Luego:
sphinx-build -b linkcheck docs/ docs/_build/linkcheck
```

### Vista previa local

```bash
# Ejecutar servidor HTTP local
cd docs/_build/html
python -m http.server 8000

# Abrir en navegador: http://localhost:8000
```

---

## Mejores Prácticas

### 1. Mantener Docstrings Actualizados
- Actualizar docstrings cuando cambies la función
- Verificar que Args/Returns/Raises están en sincronía

### 2. Ejemplos en Docstrings
```python
def ejemplo():
    """Función de ejemplo.
    
    Example:
        >>> resultado = ejemplo()
        >>> print(resultado)
    """
```

### 3. Referencias Cruzadas
```python
"""Usa :py:class:`OtraClase` o :py:func:`otra_funcion`."""
```

### 4. Código en la Documentación
```rst
.. code-block:: python

    # Código Python
    ups = StateUPS(hostname, cliente)
    ups.obtener_datos(oid_dict)
```

### 5. Notas y Advertencias
```python
"""Función importante.

.. note::
   Este es un punto importante.
   
.. warning::
   Cuidado: no uses esto en producción.
"""
```

---

## Troubleshooting

### "Module not found" al generar

**Problema**: Sphinx no encuentra los módulos
```
WARNING: autodoc: failed to import module 'core.errores'
```

**Solución**: Editar `docs/conf.py`:
```python
sys.path.insert(0, os.path.abspath('../src'))
```

### Docstrings no se procesan

**Problema**: Los docstrings no aparecen en HTML

**Solución**: Asegurar que `napoleon` está en `extensions`:
```python
extensions = ['sphinx.ext.napoleon', ...]
```

### Theme no se aplica

**Problema**: HTML se ve sin estilo

**Solución**: 
```bash
pip install sphinx-rtd-theme --upgrade
```

---

## Referencias

- [Sphinx Documentation](https://www.sphinx-doc.org/)
- [Napoleon Extension](https://www.sphinx-doc.org/en/master/usage/extensions/napoleon.html)
- [Google Python Style Guide](https://google.github.io/styleguide/pyguide.html)
- [ReadTheDocs](https://docs.readthedocs.io/)
- [FastAPI OpenAPI](https://fastapi.tiangolo.com/)

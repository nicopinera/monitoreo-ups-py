#!/usr/bin/env python3
"""
Script wrapper para ejecutar el monitoreo UPS desde la raíz del proyecto.
Uso: python3 run.py
"""
import sys
import os

# Agregar src al path para que los imports relativos funcionen
sys.path.insert(0, os.path.join(os.path.dirname(__file__), 'src'))

# Importar y ejecutar main
from main import main

if __name__ == "__main__":
    try:
        main()
    except KeyboardInterrupt:
        print("\nMonitoreo interrumpido por el usuario.")
        sys.exit(0)
    except Exception as e:
        print(f"Error crítico: {e}", file=sys.stderr)
        sys.exit(1)

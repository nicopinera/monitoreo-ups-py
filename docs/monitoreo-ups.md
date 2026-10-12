# Monitoreo UPS Pabellon Argentina

## **Monitorización de UPS - Pabellón Argentina**

El módulo consulta por **SNMP** cada minuto los UPS del Data Center del Pabellón Argentina y entrega sus métricas a **Telegraf**, que las guarda en InfluxDB para verlas en **Grafana**. Cuando un valor sale de rango (temperatura, carga, autonomía) o un equipo deja de responder, avisa en el espacio de **Google Chat** del grupo y vuelve a avisar cuando se normaliza.

Equipos monitoreados:

- **26 UPS APC** de las filas 1, 2 y 3: temperatura de baterías y ambiente, carga de baterías, carga de salida, autonomía y corriente. Tienen todas las alertas.
- **UPS trifásico del DC** (`ups-dc`): autonomía, tensiones, corrientes y potencias por fase. Solo avisa si deja de responder.
- **Sensor de humedad** conectado al UPS `f2r7u1`. Solo avisa si deja de responder.

```text
Telegraf (cada 60 s) ──▶ docker compose run ──▶ contenedor monitoreo-ups
                                                   ├─ consulta los UPS por SNMP (en paralelo)
                                                   ├─ imprime las métricas ──▶ Telegraf ──▶ InfluxDB ──▶ Grafana
                                                   └─ si algo cambió de estado ──▶ tarjeta en Google Chat
```

<p class="callout info">El proyecto está instalado en la máquina virtual pdu-monitoreo, en /etc/telegraf/monitoreo-ups. Acceder mediante: ssh pdu-monitoreo</p>

### **_Guía de Instalación - Requisitos para la instalación_**

a) El proyecto corre en la VM **pdu-monitoreo** (**Ubuntu 24.04**) dentro de un contenedor **Docker**, así que la VM **no necesita Python** ni librerías instaladas: todo viene dentro de la imagen (Python 3.13 y ezsnmp). En la VM tiene que estar instalado:

- **Docker** con los plugins **compose** y **buildx**.
- **Telegraf**.
- **git**.

```shell
docker compose version
docker buildx version
systemctl status telegraf
```

b) Compruebe que la VM, o el lugar desde donde se ejecute el programa, tenga acceso a los UPS del Data Center del Pabellón Argentina. Es necesario comprobarlo con la ayuda del equipo de Redes, o chequear si ya se hizo en el lugar donde se lo haya documentado. Aun así puede hacerlo con cualquiera de los siguientes comandos:

```shell
ping + ip_del_ups
host + nombre_del_host_del_UPS
ping 172.16.46.51
host f2r2u2.psi.unc.edu.ar
```

c) Luego de verificar que tenga acceso, es necesario configurar manualmente cada UPS desde su página y agregar la IP de la máquina virtual que ejecutará el programa dentro de las comunidades habilitadas para SNMP del UPS. Se hace de la siguiente manera:

- Ingresamos a la página del UPS, por ejemplo [http://f2r2u2.psi.unc.edu.ar](http://f2r2u2.psi.unc.edu.ar)
- Nos vamos al apartado de configuraciones -&gt; Network -&gt; SNMPv1 -&gt; Access Control
- Verificamos alguna IP que no se esté utilizando, consultando con el jefe de grupo, o alguna comunidad libre
- Agregamos o reemplazamos por la IP de nuestra máquina virtual. El **Community Name** tiene que ser **publicapc** y el **Access Type** en **Read**

### **_Instrucciones para la instalación_**

<p class="callout info">El paso a paso completo, con el porqué de cada comando, los permisos de cada carpeta y la solución a los problemas comunes, está en el runbook del repositorio: docs/runbook_vm.md. Acá va el resumen.</p>

A) **Acceso al repositorio.** La VM baja el código de GitLab con una **deploy key**: una clave SSH de solo lectura registrada en el proyecto (Settings → Repository → Deploy keys), no en la cuenta de una persona. Se genera en la VM para el usuario `telegraf`, que es el dueño del clon y el que ejecuta todo.

B) **Clonar** el repositorio en la carpeta de Telegraf, como `telegraf`:

```shell
sudo install -d -o telegraf -g telegraf -m 750 /etc/telegraf/monitoreo-ups
sudo -u telegraf git clone --branch main \
  --config core.sshCommand="ssh -i /etc/telegraf/.ssh/monitoreo-ups_deploy -o IdentitiesOnly=yes" \
  git@gitlab.unc.edu.ar:psi.iaas/monitoreo-ups.git /etc/telegraf/monitoreo-ups
```

C) **Configuración (.env).** Se crea un archivo `.env` en la raíz del proyecto a partir de la plantilla `.env.example`, con permisos `600` (solo lo lee `telegraf`). El formato es `CLAVE=valor`, sin comillas ni espacios:

```shell
sudo install -o telegraf -g telegraf -m 600 /etc/telegraf/monitoreo-ups/.env.example /etc/telegraf/monitoreo-ups/.env
sudo nano /etc/telegraf/monitoreo-ups/.env
```

```shell
SNMP_COMMUNITY=publicapc
GOOGLE_CHAT_WEBHOOK_URL=<URL del webhook del espacio de Google Chat>
MONITOREO_UID=998
MONITOREO_GID=999
```

<p class="callout warning">En BookStack, reemplazar la línea del webhook por la URL real del espacio (Google Chat → el espacio → Apps e integraciones → Webhooks). En el repositorio queda solo el marcador: el repositorio tiene una copia en GitHub y la URL permite publicar en el espacio.</p>

- `MONITOREO_UID`/`MONITOREO_GID` son el UID y el GID del usuario `telegraf` (`id -u telegraf`, `id -g telegraf`): el contenedor corre con ese usuario.
- Las demás variables (timeouts, nivel de log, minutos sin respuesta antes de avisar, link de Grafana) tienen valores por defecto y están explicadas en el `.env.example`.

D) **Primer deploy.** Construye la imagen de Docker, la prueba y la deja lista para Telegraf:

```shell
sudo -u telegraf /etc/telegraf/monitoreo-ups/deploy/actualizar.sh
```

E) **Prueba manual.** Una ejecución igual a la que hace Telegraf, sin enviar alertas al chat:

```shell
sudo -u telegraf docker compose -f /etc/telegraf/monitoreo-ups/compose.yaml run --rm -T -e GOOGLE_CHAT_WEBHOOK_URL= monitoreo

# salida (una línea por UPS, más las del DC y la humedad)
ups_temp2,host=f1r2u1 battery=20,temp=13,capacity=100,load=23,life=31.37,current=5
ups_temp2,host=f1r3u1 battery=21,temp=23,capacity=100,load=14,life=71.28,current=3
...
ups_temp2,host=f2r7u1 humidity=37
dc-ups,host=ups-dc autonomia=37.5
dc-ups,host=ups-dc carga_bat=100
...
```

F) **Telegraf y deploy automático.** Se copian a la VM tres archivos de la carpeta `deploy/` del repositorio: el input de Telegraf, el cron del deploy automático y la rotación de su log:

```shell
sudo install -m 644 /etc/telegraf/monitoreo-ups/deploy/telegraf-monitoreo-ups.conf /etc/telegraf/telegraf.d/monitoreo-ups.conf
sudo install -m 644 /etc/telegraf/monitoreo-ups/deploy/cron-monitoreo-ups /etc/cron.d/monitoreo-ups
sudo install -m 644 /etc/telegraf/monitoreo-ups/deploy/logrotate-monitoreo-ups /etc/logrotate.d/monitoreo-ups
sudo systemctl restart telegraf
```

### **_USO DEL SOFTWARE - COMO USARLO_**

Las métricas se imprimen en el formato **line protocol** para que Telegraf pueda leerlas y guardarlas en su base de datos. Telegraf es un servicio que recopila y envía métricas, eventos y registros de distintos sistemas a una base de series de tiempo como InfluxDB, y tiene plugins para extender sus funciones. Este módulo usa el plugin **\[\[inputs.exec\]\]**, que ejecuta un comando cada cierto intervalo y lee lo que imprime.

El input está en su propio archivo, **/etc/telegraf/telegraf.d/monitoreo-ups.conf**, separado del `telegraf.conf` (donde están los inputs de otros scripts):

```toml
[[inputs.exec]]
  commands = [
    "docker compose -f /etc/telegraf/monitoreo-ups/compose.yaml run --rm -T monitoreo",
  ]
  interval = "60s"
  timeout = "30s"
  data_format = "influx"
```

- **interval**: cada cuánto se ejecuta el monitoreo (60 s).
- **timeout**: cuánto espera Telegraf como máximo a que termine. Una ejecución completa tarda unos 6 segundos: un UPS que no responde no la demora, porque se deja de consultar después del primer timeout.
- **data_format**: el formato de lo que imprime el programa (line protocol de InfluxDB).

```bash
# Iniciar el sistema de telegraf
sudo systemctl start telegraf

# Si ya estaba corriendo y se modificó la configuración
sudo systemctl restart telegraf

# Verificar el status del servicio
sudo systemctl status telegraf
sudo journalctl -u telegraf --since "1 hour ago"
```

Para **detener** el monitoreo, comentar el bloque **\[\[inputs.exec\]\]** de `/etc/telegraf/telegraf.d/monitoreo-ups.conf` (o mover el archivo fuera de la carpeta) y reiniciar Telegraf.

#### **Alertas en Google Chat**

Las alertas llegan como **tarjetas** al espacio de Google Chat, solo cuando algo **cambia**: una vez cuando aparece el problema y otra cuando se normaliza, no cada minuto. Cada problema (incidente) abre un **hilo**: la alerta es el primer mensaje y su resolución llega como respuesta en el mismo hilo, con el valor actual y cuánto duró. La notificación del celular muestra un resumen de una línea, por ejemplo `⚠️ f1r11u1: Carga de salida alta (63 %)`. La tarjeta de la alerta tiene un botón **Ver en Grafana** que abre el dashboard del datacenter.

| Alerta                              | Cuándo se dispara                                | Equipos |
| ----------------------------------- | ------------------------------------------------ | ------- |
| Temperatura de batería alta         | más de 28 °C                                     | UPS APC |
| Temperatura ambiente alta           | más de 28 °C                                     | UPS APC |
| Sensor de temperatura ambiente roto | valor negativo                                   | UPS APC |
| Carga de batería baja               | menos de 70 %                                    | UPS APC |
| Carga de salida alta                | más de 60 %                                      | UPS APC |
| Autonomía baja                      | menos de 9 min                                   | UPS APC |
| Sin respuesta SNMP                  | 3 ejecuciones seguidas (3 minutos) sin respuesta | todos   |

<p class="callout info">"Sin respuesta SNMP" espera 3 minutos para no avisar por un paquete perdido. Se cambia con SNMP_FALLAS_PARA_ALERTA en el .env de la VM.</p>

<p class="callout info">Si Google Chat no responde, la alerta no se pierde: se vuelve a intentar en la ejecución siguiente.</p>

#### **Logs y estado**

Todo lo del módulo queda dentro del clon, en la carpeta `data/`:

```shell
# Log del monitoreo (qué consultó, qué equipo no respondió, qué avisó)
sudo -u telegraf tail -f /etc/telegraf/monitoreo-ups/data/logs/monitoreo.log

# Log del deploy automático (vacío mientras no haya cambios nuevos)
sudo -u telegraf tail -f /etc/telegraf/monitoreo-ups/data/logs/deploy.log

# Alertas abiertas en este momento (fechas en UTC)
sudo -u telegraf sqlite3 /etc/telegraf/monitoreo-ups/data/errores-v2.db 'select * from incidentes where fin is null'
```

### **_ACTUALIZACIÓN DEL SOFTWARE - QUÉ SE HACE A MANO Y QUÉ ES AUTOMÁTICO_**

**El código no se edita en la VM.** Todo cambio se hace en el repositorio, pasa por las pruebas automáticas y llega solo a la VM.

**Lo que se hace a mano:**

1. Crear una rama desde `dev`, hacer el cambio y probarlo en la PC (`make check` corre lo mismo que el CI).
2. Abrir un **Merge Request a `dev`**. El pipeline de GitLab verifica el formato del código (ruff), los tipos (mypy), los tests (pytest), las vulnerabilidades de las dependencias (pip-audit), el script de deploy (shellcheck) y que la imagen de Docker se construya y arranque.
3. Cuando el pipeline está en verde, se mergea. Para publicar, **Merge Request de `dev` a `main`**. `main` está protegida: no se puede mergear sin el pipeline en verde.

**Lo que pasa solo:**

1. Cada **5 minutos**, un cron de la VM (`deploy/actualizar.sh`) consulta GitLab. Si no hay commits nuevos en `main`, no hace nada.
2. Si hay un commit nuevo: actualiza el clon, **construye la imagen** nueva, la **prueba** y recién entonces la marca como la imagen de producción (`monitoreo-ups:prod`).
3. La ejecución siguiente de Telegraf ya usa la versión nueva, y llega un aviso al chat: `✅ monitoreo-ups desplegado: <commit>`.
4. **Si algo falla** (el build o la prueba), producción sigue con la versión anterior, el monitoreo no se interrumpe y llega un aviso `❌ Falló el deploy` una sola vez.

En resumen, desde el merge a `main` hasta que el cambio corre en la VM pasan como mucho unos 5 minutos más lo que tarde la construcción.

**Lo que no pasa por el repositorio** y se cambia directo en la VM:

- **El `.env`** (webhook, comunidad, timeouts, nivel de log): se edita con `sudo nano /etc/telegraf/monitoreo-ups/.env` y aplica en la ejecución siguiente, sin deploy.
- **Los archivos copiados de `deploy/`** (input de Telegraf, cron y logrotate): si cambian en el repositorio, hay que volver a copiarlos a mano, como en el paso F de la instalación.

<p class="callout info">Volver a la versión anterior (rollback): sudo -u telegraf docker image ls monitoreo-ups para ver las versiones guardadas (se conservan las 3 últimas) y sudo -u telegraf docker tag monitoreo-ups:&lt;versión anterior&gt; monitoreo-ups:prod. La versión definitiva se corrige con un git revert por Merge Request.</p>

#### **Agregado de un nuevo UPS**

Una vez instalado el UPS y configurado su SNMP (paso c de los requisitos):

- Abrir el archivo **src/config/configuracion.py**. Ahí hay una lista de hostnames por fila de racks (`HOST_NAME_SHORT_F1`, `F2`, `F3`) y una lista general que las junta.
- Agregar el hostname del nuevo UPS en la lista de su fila, como están los demás.
- Hacer el Merge Request. Cuando llega a `main`, el UPS se empieza a monitorear solo.

<p class="callout warning">Si el UPS nuevo no tiene configurado SNMP para la IP de la VM, no va a responder y a los 3 minutos llega la alerta "Sin respuesta SNMP".</p>

#### **Cambiar un umbral de alerta**

Los umbrales están en el mismo archivo, **src/config/configuracion.py**, en la tabla `REGLAS_UPS`: una línea por alerta, con la métrica, si es un máximo o un mínimo, el valor y la unidad. Se cambia el valor y se hace el Merge Request: llega a la VM como cualquier otro cambio.

#### **Mantenimiento**

Para mantener el software hay que actualizar el SO de la VM y las dependencias del proyecto (`uv lock --upgrade` por Merge Request; el pipeline semanal avisa si alguna dependencia tiene una vulnerabilidad conocida). Si encuentra que se puede simplificar el software, hágalo. Lo mismo si hace falta agregar más información que aclare partes confusas. Si cree conveniente hacerle mantenimiento al presente documento, hágalo. Hacer un esfuerzo en redactar de forma clara y concisa para que los demás lectores puedan entender el proyecto.

<p class="callout info">Para más detalles técnicos o cómo está compuesto el sistema, dirigirse al repositorio de GitLab del módulo: el README y la carpeta docs/ explican la arquitectura, el logging y la operación de la VM. [Link](https://gitlab.unc.edu.ar/psi.iaas/monitoreo-ups.git)</p>

### Revisión

| **Versión** | **Fecha**  | **Actualizó**  | **Motivo de Actualización**                                                                                |
| :---------: | :--------: | :------------: | ---------------------------------------------------------------------------------------------------------- |
|     2.0     | 12/10/2026 | Nicolas Piñera | Reescritura: ejecución con Docker, deploy automático, alertas con tarjetas e hilos, configuración por .env |
|     1.1     | 20/1/2026  | Nicolas Piñera | Se agregó información sobre requisitos e instalación                                                       |
|     1.0     | 19/1/2026  | Nicolas Piñera | Creación del Documento                                                                                     |

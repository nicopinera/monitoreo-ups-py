# Runbook — Instalación y operación en la VM

Cómo dejar el monitoreo de UPS funcionando en la VM (Ubuntu 24.04):

- el clon vive en `/etc/telegraf/monitoreo-ups`;
- Telegraf lo ejecuta con Docker;
- la VM se actualiza sola con cada merge a `main`.

**Cómo usar este documento:**

- **Instalación desde cero** (la VM no tiene el repo): seguir los pasos 1 a 9 en orden.
- **La VM ya tiene la instalación vieja** (Python directo, sin Docker), que es el caso de hoy:
  seguir el [Anexo A: migración](#anexo-a-migración-desde-la-instalación-actual). Usa los
  mismos pasos, pero arma el clon nuevo al lado del viejo para no cortar el monitoreo.
- **Operación del día a día, rollback y problemas:** secciones 10 a 12.

Cada paso dice **qué** se hace, **por qué**, los comandos, **cómo verificar** que salió bien
y, si hace falta, qué hacer si falla.

---

## Índice

0. [Conceptos](#0-conceptos)
1. [Requisitos de la VM](#1-requisitos-de-la-vm)
2. [Preparar el usuario `telegraf`](#2-preparar-el-usuario-telegraf)
3. [Acceso de solo lectura al repo (deploy key)](#3-acceso-de-solo-lectura-al-repo-deploy-key)
4. [Clonar el repo](#4-clonar-el-repo)
5. [Configuración: el `.env`](#5-configuración-el-env)
6. [Primer deploy y prueba manual](#6-primer-deploy-y-prueba-manual)
7. [Conectar Telegraf](#7-conectar-telegraf)
8. [Deploy automático: cron y rotación del log](#8-deploy-automático-cron-y-rotación-del-log)
9. [Verificaciones de puesta en marcha](#9-verificaciones-de-puesta-en-marcha)
10. [Rollback](#10-rollback)
11. [Operación diaria](#11-operación-diaria)
12. [Problemas comunes](#12-problemas-comunes)

- [Anexo A: migración desde la instalación actual](#anexo-a-migración-desde-la-instalación-actual)
- [Anexo B: permisos, uno por uno](#anexo-b-permisos-uno-por-uno)

---

## 0. Conceptos

### Cómo funciona todo junto

```text
                    ┌──────────────── GitLab ────────────────┐
  MR → pipeline     │  main (protegida: MR + pipeline verde) │
  verde → merge ──▶ └───────────────────┬────────────────────┘
                                        │ git fetch (deploy key, solo lectura)
VM ─────────────────────────────────────┼──────────────────────────────────────────
                                        ▼
  cron, cada 5 min, como telegraf: deploy/actualizar.sh
    ¿hay commit nuevo? ── no ──▶ termina sin hacer nada
          │ sí
          ▼
    actualiza el clon → docker build → smoke test → docker tag …:prod → aviso a Google Chat
                                          │ falla
                                          ▼
                       :prod no cambia (sigue la versión anterior) → aviso de fallo

  Telegraf, cada 60 s, como telegraf:
    docker compose run --rm -T monitoreo
      └─ contenedor nuevo de monitoreo-ups:prod → consulta los UPS → line protocol por stdout
         lee el .env y escribe base + logs en data/ (volumen) → el contenedor se borra
```

Hay **dos procesos independientes**:

- **Telegraf ejecuta el monitoreo** cada minuto, siempre con la imagen `:prod`.
- **Cron actualiza la imagen** cada 5 minutos si hay commits nuevos.

Telegraf no sabe nada del deploy: solo usa lo que diga `:prod` en ese momento.

### Glosario

| Término            | Qué es                                                                                                                                                                                                                              |
| ------------------ | ----------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------- |
| **Imagen**         | Paquete con Python, las dependencias y el código, listo para ejecutar. Se construye con `docker build` a partir del `Dockerfile`.                                                                                                   |
| **Contenedor**     | Una ejecución de una imagen. Acá vive unos segundos: Telegraf crea uno por minuto y se borra al terminar (`--rm`).                                                                                                                  |
| **Tag**            | Nombre de una imagen. Cada deploy crea `monitoreo-ups:<sha del commit>`, y `monitoreo-ups:prod` es un segundo nombre que apunta a la que está en producción. Mover `:prod` es instantáneo: así se despliega y así se hace rollback. |
| **Volumen**        | Carpeta de la VM que se ve dentro del contenedor. `data/` del clon aparece como `/app/data`; ahí quedan la base y los logs cuando el contenedor se borra.                                                                           |
| **Smoke test**     | Prueba mínima de que la imagen arranca: que cargue el código y que, sin configuración, salga con error explicando qué falta. No consulta UPS ni envía nada.                                                                         |
| **Deploy key**     | Clave SSH registrada en **un proyecto** de GitLab (no en una persona) que solo permite leerlo.                                                                                                                                      |
| **Grupo `docker`** | Los usuarios de este grupo pueden usar Docker sin `sudo`. `telegraf` lo necesita para ejecutar el contenedor.                                                                                                                       |
| **`/etc/cron.d/`** | Carpeta con archivos de cron del sistema. A diferencia del `crontab -e` de cada usuario, cada línea indica con qué usuario se ejecuta.                                                                                              |
| **logrotate**      | Servicio de Ubuntu que rota los logs: renombra el archivo, comprime los viejos y borra los más antiguos.                                                                                                                            |
| **flock**          | Candado sobre un archivo. Si un deploy tarda más de 5 minutos, el siguiente ve el candado tomado y sale, en lugar de pisarse con el anterior.                                                                                       |

### Convenciones de este runbook

- Todos los comandos se ejecutan con tu usuario administrador, con `sudo`.
- **Todo lo que toca el clon se ejecuta como `telegraf`** (`sudo -u telegraf …`). Así todo
  lo que se crea queda con el mismo dueño. Si corrés `git` como root dentro del clon, git se
  niega con _"detected dubious ownership"_. Si corrés el deploy como root, deja archivos de
  root que después el cron no puede modificar. El script se niega a correr como root.
- **Siempre rutas absolutas, nunca `cd` al clon.** El clon tiene permisos `750`: tu usuario
  no puede entrar, ni siquiera para después hacer `sudo`. Por eso los comandos usan
  `git -C <ruta>` y `docker compose -f <ruta>/compose.yaml`.
- `<algo>` es un valor a reemplazar.

---

## 1. Requisitos de la VM

**Qué:** verificar que estén Docker, Compose y Buildx, y que la VM llegue a internet y a GitLab.

**Por qué:**

- **Compose** lee el `compose.yaml`, donde está cómo se ejecuta el contenedor: volumen, `.env`,
  usuario y red.
- **Buildx** es el motor de build moderno (BuildKit). El `Dockerfile` lo necesita por los
  `RUN --mount` que usa para el caché de dependencias.
- **Salida a internet:** el build descarga la imagen base (Docker Hub), `uv` (`ghcr.io`) y las
  dependencias (PyPI).

```bash
docker version          # tienen que responder el cliente y el servidor ("Server:")
docker compose version
docker buildx version
```

Si `compose` o `buildx` no responden, depende de cómo se instaló Docker:

```bash
dpkg -l | grep -E "docker-ce |docker.io "
# Si aparece docker-ce (repositorio oficial de Docker):
sudo apt update && sudo apt install docker-compose-plugin docker-buildx-plugin
# Si aparece docker.io (repositorio de Ubuntu):
sudo apt update && sudo apt install docker-compose-v2 docker-buildx
```

Conectividad:

```bash
curl -sSI https://registry-1.docker.io/v2/ | head -1    # cualquier respuesta HTTP sirve (401 es normal)
curl -sSI https://ghcr.io | head -1
curl -sSI https://pypi.org/simple/ | head -1
nc -vz gitlab.unc.edu.ar 22                              # "succeeded": el SSH a GitLab está abierto
```

**Si `nc` al puerto 22 falla,** el firewall bloquea SSH: usar la alternativa por HTTPS del paso 3.

También tienen que estar `git`, `curl` y `flock` (este último viene en `util-linux`, instalado
por defecto), y Telegraf corriendo: `systemctl status telegraf`.

---

## 2. Preparar el usuario `telegraf`

**No hay que reinstalar Telegraf.** Usamos el usuario `telegraf` que creó su paquete, y solo
le agregamos lo que le falta.

### 2.1 Datos del usuario

```bash
getent passwd telegraf
# telegraf:x:<UID>:<GID>::/etc/telegraf:/bin/false
#                         ^^^^^^^^^^^^^ su home        ^^^^^^^^^^ sin shell (no se puede loguear)
id -u telegraf          # anotar: va en MONITOREO_UID (paso 5)
id -g telegraf          # anotar: va en MONITOREO_GID (paso 5)
```

### 2.2 Carpetas `.ssh` y `.docker` en su home

**Qué:** crear dos carpetas **vacías** en el home de `telegraf`.

**Por qué:** ssh y docker guardan su configuración en el home del usuario que los ejecuta:

- **`~/.ssh`:** la deploy key (paso 3) y `known_hosts`, la huella de GitLab que ssh verifica
  para no conectarse a un servidor falso.
- **`~/.docker`:** `docker build` (buildx) guarda ahí su estado. Si no puede escribir, el build
  falla con `mkdir /etc/telegraf/.docker: permission denied`.

El home de `telegraf` es `/etc/telegraf`, cuyo dueño es root, así que `telegraf` no puede
crearlas por su cuenta. Las crea root con dueño `telegraf` y permisos `700`, porque `.ssh`
tiene una clave privada y ssh rechaza carpetas que otros puedan leer.

```bash
sudo install -d -o telegraf -g telegraf -m 700 /etc/telegraf/.ssh /etc/telegraf/.docker
```

`install -d` crea una carpeta y en el mismo paso le asigna dueño (`-o`), grupo (`-g`) y
permisos (`-m`). Equivale a `mkdir` + `chown` + `chmod`.

Si `getent` mostró otro home, usá ese en lugar de `/etc/telegraf` en este paso y en el 3.

### 2.3 Acceso a Docker

**Qué:** agregar `telegraf` al grupo `docker` y reiniciar el servicio.

**Por qué:** Telegraf va a ejecutar `docker compose run`, y solo root o el grupo `docker`
pueden hablar con Docker. El reinicio hace falta porque los grupos de un proceso se fijan
cuando arranca: el Telegraf que ya está corriendo no se entera del grupo nuevo.

```bash
sudo usermod -aG docker telegraf      # -a: agregar sin sacarlo de sus otros grupos
sudo systemctl restart telegraf
```

**Verificar:**

```bash
sudo -u telegraf docker ps            # una tabla (aunque esté vacía), sin "permission denied"
```

> **Seguridad:** el grupo `docker` equivale a root en la VM, porque con Docker se puede
> montar cualquier carpeta del sistema. Es aceptable en una VM dedicada al monitoreo, y por
> eso hay tres resguardos:
>
> - el clon usa una credencial de **solo lectura**;
> - `main` está **protegida** (MR obligatorio con pipeline en verde);
> - el CI pasa `shellcheck` sobre el script de deploy.
>
> Todo lo que llega a `main` termina ejecutándose en la VM.

---

## 3. Acceso de solo lectura al repo (deploy key)

**Qué:** generar en la VM una clave SSH nueva y registrarla en el proyecto de GitLab como
_deploy key_ de solo lectura.

**¿Por qué no usar la clave SSH que ya tiene tu usuario en `~/.ssh`?**

- **`telegraf` no puede leerla.** Está en tu home con permisos solo para vos, y ssh se niega a
  usar una clave privada de otro usuario.
- **Da demasiado acceso.** Está registrada en tu cuenta personal: permite leer y escribir en
  todos tus proyectos. Cualquier cosa que corra como `telegraf` podría hacer push a cualquier
  repo tuyo.
- **Ata el deploy a tu cuenta.** Si cambiás o borrás tu clave, o dejás el equipo, el deploy
  deja de andar.

La deploy key está registrada en el **proyecto**, solo sirve para leer ese repo y se revoca
desde GitLab sin afectar a nadie.

### 3.1 Generar la clave en la VM

```bash
sudo -u telegraf ssh-keygen -t ed25519 -N "" \
  -C "monitoreo-ups deploy $(hostname)" \
  -f /etc/telegraf/.ssh/monitoreo-ups_deploy
```

- `-t ed25519`: tipo de clave moderno, corto y seguro.
- `-N ""`: **sin passphrase**. El cron la usa sin nadie presente para tipearla. La protegen los
  permisos: solo `telegraf` (y root) pueden leerla.
- `-C`: un comentario para reconocerla en GitLab.
- `-f`: dónde se guarda. Se crean dos archivos: `monitoreo-ups_deploy` (privada, **nunca sale
  de la VM**) y `monitoreo-ups_deploy.pub` (pública, la que se pega en GitLab).

```bash
sudo -u telegraf cat /etc/telegraf/.ssh/monitoreo-ups_deploy.pub    # copiar esta línea completa
```

### 3.2 Registrarla en GitLab

Requiere rol _Maintainer_ en el proyecto.

1. Abrir el proyecto `psi.iaas/monitoreo-ups` → **Settings → Repository → Deploy keys** →
   **Add new key**.
2. **Title:** `VM monitoreo <hostname>`. **Key:** la línea `.pub` del paso anterior.
3. **No marcar** _"Grant write permissions to this key"_: tiene que ser de solo lectura.
4. **Add key.**

### 3.3 Registrar la huella de GitLab

**Por qué:** la primera vez que ssh se conecta a un servidor pregunta _"Are you sure you want
to continue connecting?"_. El cron no puede contestar, así que fallaría. Además la huella
protege contra conectarse a un servidor que se haga pasar por GitLab. Por eso se registra a
mano y se compara con la oficial.

```bash
sudo -u telegraf sh -c 'ssh-keyscan -t ed25519 gitlab.unc.edu.ar >> /etc/telegraf/.ssh/known_hosts'
sudo -u telegraf ssh-keygen -lf /etc/telegraf/.ssh/known_hosts      # muestra la huella SHA256:...
```

Compararla con la publicada en GitLab (**Help (?) → Help → SSH host keys fingerprints**, o
`https://gitlab.unc.edu.ar/help/instance_configuration`) o preguntarle a quien administra el
GitLab. Tienen que ser iguales.

### 3.4 Probar el acceso

```bash
sudo -u telegraf ssh -i /etc/telegraf/.ssh/monitoreo-ups_deploy -o IdentitiesOnly=yes \
  -T git@gitlab.unc.edu.ar
# → "Welcome to GitLab, ..."
```

`-o IdentitiesOnly=yes` hace que ssh pruebe **solo** esta clave y no otras que encuentre.

### Alternativa: deploy token por HTTPS (solo si el puerto 22 está bloqueado)

Un deploy token es un usuario y contraseña de solo lectura del proyecto. A diferencia de la
deploy key, **vence** y es un secreto que hay que guardar.

1. GitLab → **Settings → Repository → Deploy tokens → Add token**. Completar un nombre y una
   fecha de vencimiento, y marcar solo el scope **`read_repository`**. Anotar el usuario y el
   token: GitLab no los vuelve a mostrar.
2. Guardarlos en un archivo de credenciales fuera del clon. **No ponerlos en la URL del
   remoto:** quedarían en `.git/config` y saldrían en `git remote -v`.

   ```bash
   sudo install -o telegraf -g telegraf -m 600 /dev/null /etc/telegraf/.git-credentials-monitoreo
   sudo -u telegraf sh -c 'printf "https://%s:%s@gitlab.unc.edu.ar\n" "<usuario_token>" "<token>" \
     > /etc/telegraf/.git-credentials-monitoreo'
   ```

3. En el paso 4, clonar con
   `--config credential.helper="store --file /etc/telegraf/.git-credentials-monitoreo"` y la URL
   `https://gitlab.unc.edu.ar/psi.iaas/monitoreo-ups.git`, en lugar de `core.sshCommand` y la URL
   SSH.
4. Agendar la renovación antes del vencimiento: cuando vence, el deploy falla y avisa.

---

## 4. Clonar el repo

**Qué:** crear la carpeta del clon, clonar `main` como `telegraf` y crear la carpeta de datos.

**Por qué así:**

- `/etc/telegraf` es de root, así que root crea la carpeta vacía y se la entrega a `telegraf`.
  A partir de ahí, todo lo hace `telegraf`.
- **Permisos `750`** (dueño: todo; grupo: leer y entrar; otros: nada). El `.env` y la base
  quedan protegidos aunque alguien cambie el modo de un archivo por error.
- **`--config core.sshCommand=…`** guarda dentro del clon (`.git/config`) qué clave usar. Así
  cualquier `git fetch` futuro, el del cron incluido, la usa sin configurar nada más.
- **`--branch main`:** es la rama que sigue el deploy. A `main` se llega por MR desde `dev`.
- **`data/`** no está en git (está en `.gitignore`), así que hay que crearla. Es la carpeta
  que el contenedor ve como volumen: ahí van la base, los logs y el estado del deploy.

```bash
sudo install -d -o telegraf -g telegraf -m 750 /etc/telegraf/monitoreo-ups

sudo -u telegraf git clone --branch main \
  --config core.sshCommand="ssh -i /etc/telegraf/.ssh/monitoreo-ups_deploy -o IdentitiesOnly=yes" \
  git@gitlab.unc.edu.ar:psi.iaas/monitoreo-ups.git /etc/telegraf/monitoreo-ups

sudo -u telegraf install -d -m 750 /etc/telegraf/monitoreo-ups/data/logs
```

**Verificar:**

```bash
sudo -u telegraf git -C /etc/telegraf/monitoreo-ups log --oneline -1    # último commit de main
sudo ls -ld /etc/telegraf/monitoreo-ups /etc/telegraf/monitoreo-ups/data
# drwxr-x--- telegraf telegraf …
sudo ls -l /etc/telegraf/monitoreo-ups/deploy/actualizar.sh             # -rwxr-xr-x (ejecutable)
```

---

## 5. Configuración: el `.env`

**Qué:** crear el `.env` a partir de la plantilla y completarlo.

**Por qué:**

- Los secretos (comunidad SNMP, webhook) y los ajustes de la VM **no están en git ni en la
  imagen**. Compose los pasa al contenedor en cada ejecución (`env_file: .env`).
- Cambiar un valor no requiere deploy: aplica en la próxima ejecución de Telegraf.
- `MONITOREO_UID`/`MONITOREO_GID` no los usa el programa: los usa compose para correr el
  contenedor con el usuario `telegraf`. Así la base y los logs que escribe el contenedor
  quedan del mismo dueño que el resto del clon.
- **Permisos `600`:** solo `telegraf` puede leerlo, porque tiene secretos.

```bash
sudo install -o telegraf -g telegraf -m 600 \
  /etc/telegraf/monitoreo-ups/.env.example /etc/telegraf/monitoreo-ups/.env
sudo nano /etc/telegraf/monitoreo-ups/.env       # editar como root conserva dueño y permisos
```

Completar. El formato es `CLAVE=valor`: sin comillas, sin espacios alrededor del `=` y sin
comentarios al final de la línea, que Docker tomaría como parte del valor.

```dotenv
SNMP_COMMUNITY=<comunidad de lectura de los UPS>
GOOGLE_CHAT_WEBHOOK_URL=https://chat.googleapis.com/v1/spaces/...
MONITOREO_UID=<id -u telegraf>
MONITOREO_GID=<id -g telegraf>
```

- El resto (timeouts, workers, nivel de log) tiene valores por defecto razonables; cada
  variable está explicada en el archivo.
- `MONITOREO_DATA_DIR` no hace falta: dentro del contenedor compose la fija en `/app/data`.

**Verificar:**

```bash
sudo ls -l /etc/telegraf/monitoreo-ups/.env
# -rw------- 1 telegraf telegraf …
sudo -u telegraf docker compose -f /etc/telegraf/monitoreo-ups/compose.yaml config --quiet
# sin salida = compose encontró todo lo que necesita
# "falta MONITOREO_UID en el .env" = completarlo
```

---

## 6. Primer deploy y prueba manual

### 6.1 Primer deploy

**Qué:** ejecutar a mano el mismo script que después correrá el cron.

**Por qué:** la imagen `monitoreo-ups:prod` todavía no existe, y sin ella Telegraf no puede
ejecutar nada. Correrlo a mano también permite ver el build en vivo y corregir problemas de
red o permisos antes de automatizar.

```bash
sudo -u telegraf /etc/telegraf/monitoreo-ups/deploy/actualizar.sh
```

Qué hace, en orden (lo vas a ver en pantalla):

1. `git fetch` para ver si hay un commit nuevo en `main`. Como la imagen todavía no existe,
   sigue de largo.
2. `docker build`: construye `monitoreo-ups:<sha>`. La primera vez tarda uno o dos minutos
   porque descarga la imagen base y las dependencias; después usa el caché.
3. Smoke test: que el código cargue y que, sin configuración, salga con error explicando que
   falta `SNMP_COMMUNITY`.
4. `docker tag … :prod`: la marca como la imagen de producción.
5. Borra versiones viejas (conserva 3) y envía un aviso "✅ desplegado" al Google Chat del
   `.env`.

**Verificar:**

```bash
sudo -u telegraf docker image ls monitoreo-ups      # :prod y :<sha> con el mismo IMAGE ID
```

**Si falla:** el mensaje dice en qué paso. Revisar la sección 12. Corregido el problema, el
reintento requiere `FORCE=1` (ver [10.4](#104-forzar-o-pausar-el-deploy)), porque el script no
reintenta solo un commit que ya falló:
`sudo -u telegraf env FORCE=1 /etc/telegraf/monitoreo-ups/deploy/actualizar.sh`.

### 6.2 Prueba manual del monitoreo

**Qué:** una ejecución igual a la que hará Telegraf, pero sin enviar alertas reales.

**Por qué:** confirmar que el contenedor llega a los UPS, que escribe en `data/` con el dueño
correcto y que la salida es line protocol válido, antes de conectarlo a Telegraf.

`-e GOOGLE_CHAT_WEBHOOK_URL=` pisa el webhook del `.env` solo para esta ejecución. Si hay
alertas no se envían, y como no se envían tampoco quedan registradas en la base: se enviarán
normalmente cuando lo ejecute Telegraf.

```bash
sudo -u telegraf docker compose -f /etc/telegraf/monitoreo-ups/compose.yaml \
  run --rm -T -e GOOGLE_CHAT_WEBHOOK_URL= monitoreo > /tmp/salida.txt
echo "código de salida: $?"          # 0
wc -l /tmp/salida.txt                # varias líneas: métricas de los 28 equipos
head -3 /tmp/salida.txt              # ups_…,host=… campo=valor …
sudo -u telegraf tail -20 /etc/telegraf/monitoreo-ups/data/logs/monitoreo.log
sudo ls -l /etc/telegraf/monitoreo-ups/data /etc/telegraf/monitoreo-ups/data/logs   # todo de telegraf
```

---

## 7. Conectar Telegraf

**Qué:** instalar el `[[inputs.exec]]` que ejecuta el contenedor cada 60 s.

**Por qué:** es lo que pone el monitoreo en producción. El archivo está versionado en
`deploy/telegraf-monitoreo-ups.conf`. Telegraf lee automáticamente todos los `.conf` de
`/etc/telegraf/telegraf.d/`, así que no hay que tocar el `telegraf.conf` principal.

### 7.1 Revisar que no haya otro input del monitoreo

Si quedara el input viejo (el que corre `python3 …/src/main.py`), cada UPS se consultaría dos
veces por minuto. Cada métrica llegaría duplicada y dos procesos competirían por la misma
base de alertas.

```bash
sudo grep -rn -B2 -A6 "monitoreo-ups\|main.py" /etc/telegraf/telegraf.conf /etc/telegraf/telegraf.d/
```

Si aparece un `[[inputs.exec]]` viejo, anotar si tiene opciones además de `commands`,
`interval`, `timeout` y `data_format` (por ejemplo `name_suffix` o `[inputs.exec.tags]`) y
copiarlas al archivo nuevo. Después **borrar o comentar el bloque viejo completo** (cada
línea con `#`).

### 7.2 Instalar el input nuevo

```bash
sudo install -o root -g root -m 644 \
  /etc/telegraf/monitoreo-ups/deploy/telegraf-monitoreo-ups.conf \
  /etc/telegraf/telegraf.d/monitoreo-ups.conf
```

Es una **copia**, propiedad de root como el resto de la configuración de Telegraf. El deploy
automático no la actualiza: si el archivo cambia en el repo, hay que volver a copiarlo.

### 7.3 Probar y activar

`telegraf --test` ejecuta los inputs una vez y muestra las métricas por pantalla **sin
enviarlas** a la base de métricas:

```bash
sudo -u telegraf telegraf --test \
  --config /etc/telegraf/telegraf.conf --config-directory /etc/telegraf/telegraf.d \
  --input-filter exec | head
```

Si muestra métricas de los UPS:

```bash
sudo systemctl restart telegraf
sudo journalctl -u telegraf -f        # esperar 1–2 minutos; no tienen que aparecer errores de inputs.exec
```

Verificar en Grafana que siguen llegando las métricas.

---

## 8. Deploy automático: cron y rotación del log

**Qué:** instalar el cron que corre el deploy cada 5 minutos y la rotación de su log.

**Por qué:**

- **`/etc/cron.d/` y no `crontab -e -u telegraf`:** el archivo es visible para cualquier
  administrador (un crontab de usuario queda escondido en `/var/spool/cron`), es copia de un
  archivo versionado y dice explícitamente con qué usuario corre.
- **logrotate:** el script agrega líneas a `data/logs/deploy.log` en cada deploy y sin
  rotación crecería para siempre. `monitoreo.log` no va acá: lo rota la propia aplicación.

```bash
sudo install -o root -g root -m 644 \
  /etc/telegraf/monitoreo-ups/deploy/cron-monitoreo-ups /etc/cron.d/monitoreo-ups
sudo install -o root -g root -m 644 \
  /etc/telegraf/monitoreo-ups/deploy/logrotate-monitoreo-ups /etc/logrotate.d/monitoreo-ups
sudo logrotate --debug /etc/logrotate.d/monitoreo-ups     # valida la sintaxis, no rota nada
```

Sobre el archivo de cron:

- **Root `644` es obligatorio:** cron ignora los archivos de `/etc/cron.d/` que otros puedan
  modificar, que tengan puntos en el nombre o que no terminen en salto de línea.
- **`MAILTO=""`:** cron no intenta mandar mails con la salida, que ya va a `deploy.log`.
- Cron detecta el archivo nuevo solo; no hay que reiniciarlo.

Igual que el input de Telegraf, cron y logrotate son **copias**: si cambian en el repo, hay que
volver a copiarlos.

**Verificar** (a los 5 minutos):

```bash
grep CRON /var/log/syslog | grep monitoreo-ups | tail -3     # cron lo está ejecutando
sudo -u telegraf tail /etc/telegraf/monitoreo-ups/data/logs/deploy.log
```

Si no hubo commits nuevos el script no escribe nada, así que el log puede estar vacío o no
existir todavía. Es lo normal.

---

## 9. Verificaciones de puesta en marcha

### 9.1 Un cambio en `main` se despliega solo

1. Hacer un MR con un cambio trivial, por ejemplo un comentario en el README, y mergearlo
   hasta `main`.
2. Esperar hasta 5 minutos más lo que tarde el build. Llega a Google Chat
   `✅ monitoreo-ups desplegado: <sha> — <título del commit>`.
3. Comprobar en la VM:

```bash
sudo -u telegraf tail -20 /etc/telegraf/monitoreo-ups/data/logs/deploy.log
#   … [deploy] Actualizando <sha viejo> -> <sha nuevo>
#   … [deploy] Construyendo monitoreo-ups:<sha>
#   … [deploy] Smoke test de monitoreo-ups:<sha>
#   … [deploy] Promovida monitoreo-ups:<sha> a :prod
sudo -u telegraf git -C /etc/telegraf/monitoreo-ups log --oneline -1
sudo -u telegraf docker image inspect monitoreo-ups:prod \
  --format '{{ index .Config.Labels "org.opencontainers.image.revision" }}'
# el sha corto del mismo commit
```

### 9.2 Rollback

Hacer la sección 10.2 completa: volver a la versión anterior, comprobarlo y volver a la
actual.

### 9.3 (Opcional) Un deploy roto no afecta producción

Mergear a `main` un cambio que rompa el build, por ejemplo una línea inválida en el
`Dockerfile`. **El CI lo frena antes** (job `docker-build`), así que esta prueba solo tiene
sentido forzándola en una rama: `sudo -u telegraf env BRANCH=<rama-de-prueba> …/actualizar.sh`.
Esperado:

- llega _"❌ Falló el deploy…"_;
- `:prod` sigue en la versión anterior;
- las métricas siguen llegando.

Al terminar, correr el script sin `BRANCH` para volver a `main`.

---

## 10. Rollback

### 10.1 Qué versiones hay

El deploy conserva las **3 últimas versiones** (`monitoreo-ups:<sha>`) además de `:prod`:

```bash
sudo -u telegraf docker image ls monitoreo-ups --format '{{.Tag}}\t{{.ID}}\t{{.CreatedAt}}'
# de la más nueva a la más vieja; :prod tiene el mismo ID que la versión en producción
sudo -u telegraf docker image inspect monitoreo-ups:prod \
  --format '{{ index .Config.Labels "org.opencontainers.image.revision" }}'
sudo -u telegraf git -C /etc/telegraf/monitoreo-ups log --oneline -5   # qué commit es cada sha
```

### 10.2 Rollback rápido (segundos)

Apuntar `:prod` a una versión anterior. La próxima ejecución de Telegraf, en menos de un
minuto, ya usa esa imagen:

```bash
sudo -u telegraf docker tag monitoreo-ups:<sha_anterior> monitoreo-ups:prod
```

Para volver a la versión actual:

```bash
sudo -u telegraf docker tag monitoreo-ups:<sha_actual> monitoreo-ups:prod
```

**Importante:** el rollback rápido **dura hasta el próximo merge a `main`**. El deploy solo
actúa cuando hay un commit nuevo, y en ese momento promueve la versión nueva. Por eso no
deshace tu rollback cada 5 minutos, pero tampoco lo respeta para siempre.

### 10.3 Rollback definitivo

`git revert` del commit problemático, por MR hasta `main`. El deploy lo despliega como
cualquier otro cambio y el historial queda registrado.

### 10.4 Forzar o pausar el deploy

- **Forzar un deploy ya,** sin esperar al cron:
  `sudo -u telegraf /etc/telegraf/monitoreo-ups/deploy/actualizar.sh`
- **Reintentar un commit que falló.** Por ejemplo, si el build falló por un corte de internet,
  el script no lo reintenta solo y espera un commit nuevo:
  `sudo -u telegraf env FORCE=1 /etc/telegraf/monitoreo-ups/deploy/actualizar.sh`
- **Pausar el deploy automático** (por ejemplo durante un incidente): comentar con `#` la
  última línea de `/etc/cron.d/monitoreo-ups` (`sudo nano`). Para reanudar, descomentarla.

---

## 11. Operación diaria

| Para…                                   | Comando                                                                                                                              |
| --------------------------------------- | ------------------------------------------------------------------------------------------------------------------------------------ |
| Ver el log de la aplicación             | `sudo -u telegraf tail -f /etc/telegraf/monitoreo-ups/data/logs/monitoreo.log`                                                       |
| Ver el log del deploy                   | `sudo -u telegraf tail -f /etc/telegraf/monitoreo-ups/data/logs/deploy.log`                                                          |
| Ver errores de Telegraf                 | `sudo journalctl -u telegraf --since "1 hour ago"`                                                                                   |
| Correr el monitoreo a mano              | `sudo -u telegraf docker compose -f /etc/telegraf/monitoreo-ups/compose.yaml run --rm -T monitoreo`                                  |
| Cambiar webhook, comunidad, timeouts…   | `sudo nano /etc/telegraf/monitoreo-ups/.env` (aplica en la próxima ejecución, sin deploy)                                            |
| Ver la versión en producción            | `sudo -u telegraf docker image inspect monitoreo-ups:prod --format '{{ index .Config.Labels "org.opencontainers.image.revision" }}'` |
| Ver el estado de las alertas            | `sudo -u telegraf sqlite3 /etc/telegraf/monitoreo-ups/data/errores.db 'select * from errores'` (`sudo apt install sqlite3`)          |
| Ver si hay un fallo de deploy pendiente | `sudo -u telegraf cat /etc/telegraf/monitoreo-ups/data/deploy_fallido` (si no existe, no hay)                                        |

---

## 12. Problemas comunes

| Síntoma                                                         | Causa y solución                                                                                                                                          |
| --------------------------------------------------------------- | --------------------------------------------------------------------------------------------------------------------------------------------------------- |
| `permission denied … /var/run/docker.sock`                      | `telegraf` no está en el grupo `docker`, o Telegraf no se reinició después de agregarlo (paso 2.3).                                                       |
| `Permission denied` al hacer `cd /etc/telegraf/monitoreo-ups`   | Es lo esperado: el clon es `750`. Usar rutas absolutas con `sudo -u telegraf` (ver convenciones).                                                         |
| `detected dubious ownership in repository`                      | Se corrió `git` como otro usuario. Usar `sudo -u telegraf git -C …`.                                                                                      |
| `Ejecutar como el dueño del clon`                               | Se corrió el script como root. Usar `sudo -u telegraf …`.                                                                                                 |
| `Host key verification failed`                                  | Falta la huella de GitLab en `/etc/telegraf/.ssh/known_hosts` (paso 3.3).                                                                                 |
| `Permission denied (publickey)`                                 | La deploy key no está en el proyecto, o el clon no tiene `core.sshCommand`: `sudo -u telegraf git -C /etc/telegraf/monitoreo-ups config core.sshCommand`. |
| `mkdir /etc/telegraf/.docker: permission denied`                | Falta la carpeta `.docker` (paso 2.2).                                                                                                                    |
| `falta MONITOREO_UID en el .env`                                | Completar `MONITOREO_UID`/`MONITOREO_GID` (paso 5).                                                                                                       |
| `pull access denied for monitoreo-ups`                          | `:prod` no existe todavía: hacer el primer deploy (paso 6.1).                                                                                             |
| Aviso _"no se pudo consultar GitLab (git fetch)"_               | Sin red hacia GitLab, o la deploy key fue revocada. Se reintenta solo cada 5 min y no repite el aviso.                                                    |
| Aviso _"falló el build de la imagen"_                           | Ver el error en `deploy.log`. Si fue la red, reintentar con `FORCE=1` (10.4). Si fue el código, se corrige con otro commit.                               |
| Aviso _"smoke test: …"_                                         | La imagen se construyó pero no arranca. Producción sigue con la versión anterior. Corregir con otro commit.                                               |
| Telegraf: `exit status 1` del input exec                        | El programa no produjo ninguna métrica o la configuración es inválida: ver `monitoreo.log` y `journalctl -u telegraf` (el motivo va a stderr).            |
| Telegraf: `command timed out`                                   | Subir `timeout` del input (hoy 30 s) y revisar en `monitoreo.log` qué equipo no responde.                                                                 |
| `unable to open database file` o errores de permisos en `data/` | `data/` cambió de dueño (alguien corrió el contenedor o el script como root): `sudo chown -R telegraf:telegraf /etc/telegraf/monitoreo-ups/data`.         |
| El build no puede descargar (Docker Hub, `ghcr.io`, PyPI)       | Falta salida a internet o hay proxy: configurarlo en `/etc/systemd/system/docker.service.d/` (plan §6.4).                                                 |

---

## Anexo A: migración desde la instalación actual

**Situación:** la VM ya tiene un clon en `/etc/telegraf/monitoreo-ups` que Telegraf ejecuta con
`python3 src/main.py`, y ese clon tiene la base de alertas (`data/errores.db`).

**Estrategia:** no se transforma el clon viejo. Se arma uno nuevo **al lado**
(`/etc/telegraf/monitoreo-ups.nuevo`) mientras el viejo sigue funcionando, se prueba y recién
después se intercambian. Así:

- el monitoreo no se interrumpe durante la preparación;
- el corte dura alrededor de un minuto;
- el clon viejo queda intacto como vuelta atrás.

### A.1 Preparar el clon nuevo (el monitoreo actual sigue funcionando)

1. **Pasos 1, 2 y 3 tal cual.** Agregar `telegraf` al grupo `docker` y reiniciarlo no afecta
   al input actual.
2. **Paso 4, clonando en `/etc/telegraf/monitoreo-ups.nuevo`.** Reemplazar la ruta en los tres
   comandos, incluido el `install -d` de `data/logs`.
3. **Paso 5, en el `.env` del clon nuevo.** Copiar los valores del `.env` actual
   (`sudo cat /etc/telegraf/monitoreo-ups/.env`) y agregar `MONITOREO_UID`/`MONITOREO_GID`.
4. **Paso 6.1 indicando la carpeta,** porque el script asume `/etc/telegraf/monitoreo-ups`:

   ```bash
   sudo -u telegraf env REPO_DIR=/etc/telegraf/monitoreo-ups.nuevo \
     /etc/telegraf/monitoreo-ups.nuevo/deploy/actualizar.sh
   ```

   Llega a Google Chat el aviso del deploy. Es esperable.

5. **Paso 6.2 con la ruta nueva,** y comparar con la instalación actual. Tienen que salir los
   mismos equipos y campos; los valores difieren un poco porque se leen en momentos distintos.
   Correr el clon viejo a mano equivale a una ejecución más de Telegraf: usa su propia base, y
   como las alertas solo se envían cuando cambia un estado, no duplica avisos.

   ```bash
   sudo -u telegraf docker compose -f /etc/telegraf/monitoreo-ups.nuevo/compose.yaml \
     run --rm -T -e GOOGLE_CHAT_WEBHOOK_URL= monitoreo > /tmp/nuevo.txt
   sudo -u telegraf sh -c 'cd /etc/telegraf/monitoreo-ups && python3 src/main.py' > /tmp/viejo.txt
   # "medición,tags + nombres de campos" de cada línea, sin los valores
   resumir() { awk '{ n = split($2, c, ","); s = $1; for (i = 1; i <= n; i++) { sub(/=.*/, "", c[i]); s = s " " c[i] }; print s }' "$1" | sort; }
   diff <(resumir /tmp/viejo.txt) <(resumir /tmp/nuevo.txt) && echo "mismos equipos y campos"
   ```

6. **Borrar la base de prueba** del clon nuevo. En el corte se reemplaza por la real:

   ```bash
   sudo -u telegraf rm -f /etc/telegraf/monitoreo-ups.nuevo/data/errores.db
   ```

### A.2 Corte

```bash
# 1. Detener Telegraf: nadie escribe la base mientras se copia
sudo systemctl stop telegraf

# 2. Intercambiar las carpetas. El clon no guarda su propia ruta: funciona igual tras el mv
sudo mv /etc/telegraf/monitoreo-ups /etc/telegraf/monitoreo-ups.viejo
sudo mv /etc/telegraf/monitoreo-ups.nuevo /etc/telegraf/monitoreo-ups

# 3. Llevar el estado de las alertas (sin esto se re-enviarían las alertas ya activas)
sudo install -o telegraf -g telegraf -m 640 \
  /etc/telegraf/monitoreo-ups.viejo/data/errores.db /etc/telegraf/monitoreo-ups/data/errores.db
```

1. **Cambiar el input de Telegraf:** paso 7 completo. En 7.1 aparece el input viejo, con
   `python3`, y hay que sacarlo. En 7.3 se vuelve a iniciar Telegraf: usar
   `sudo systemctl start telegraf` en lugar de `restart`.
2. **Paso 8** (cron y logrotate).
3. **Paso 9** (verificaciones).

### A.3 Vuelta atrás (si algo falla en el corte)

```bash
sudo systemctl stop telegraf
sudo rm -f /etc/telegraf/telegraf.d/monitoreo-ups.conf /etc/cron.d/monitoreo-ups
sudo mv /etc/telegraf/monitoreo-ups /etc/telegraf/monitoreo-ups.nuevo
sudo mv /etc/telegraf/monitoreo-ups.viejo /etc/telegraf/monitoreo-ups
# restaurar (descomentar) el [[inputs.exec]] viejo
sudo systemctl start telegraf
```

### A.4 Limpieza

A la semana, si todo anda bien:

```bash
sudo rm -rf /etc/telegraf/monitoreo-ups.viejo
```

---

## Anexo B: permisos, uno por uno

| Ruta                                          | Dueño    | Modo | Por qué                                                                                                        |
| --------------------------------------------- | -------- | ---- | -------------------------------------------------------------------------------------------------------------- |
| `/etc/telegraf/.ssh/`                         | telegraf | 700  | Tiene la clave privada. ssh rechaza carpetas que otros puedan leer.                                            |
| `/etc/telegraf/.ssh/monitoreo-ups_deploy`     | telegraf | 600  | Clave privada (la crea así `ssh-keygen`). ssh rechaza claves legibles por otros.                               |
| `/etc/telegraf/.docker/`                      | telegraf | 700  | Estado del cliente docker y de buildx.                                                                         |
| `/etc/telegraf/monitoreo-ups/`                | telegraf | 750  | El clon: solo `telegraf` lo modifica, y nadie fuera de su grupo lo lee.                                        |
| `…/monitoreo-ups/.env`                        | telegraf | 600  | Secretos (comunidad SNMP, webhook).                                                                            |
| `…/monitoreo-ups/data/` (y `logs/`)           | telegraf | 750  | Volumen del contenedor, que corre con el UID de `telegraf` (`MONITOREO_UID`).                                  |
| `…/monitoreo-ups/deploy/actualizar.sh`        | telegraf | 755  | Ejecutable: el permiso viene de git.                                                                           |
| `/etc/telegraf/telegraf.d/monitoreo-ups.conf` | root     | 644  | Configuración del sistema, como el resto de Telegraf.                                                          |
| `/etc/cron.d/monitoreo-ups`                   | root     | 644  | cron ignora archivos de `/etc/cron.d/` que otros puedan modificar.                                             |
| `/etc/logrotate.d/monitoreo-ups`              | root     | 644  | Ídem para logrotate. Rota como `telegraf` (`su telegraf telegraf`) porque la carpeta del log es de `telegraf`. |
| `/run/lock/monitoreo-ups-deploy.lock`         | telegraf | 644  | Candado del deploy (lo crea el script). Fuera del clon para que `git clean` no lo borre.                       |

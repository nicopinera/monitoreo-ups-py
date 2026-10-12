#!/usr/bin/env bash
# Deploy automatico del monitoreo de UPS. Lo ejecuta cron cada 5 minutos como telegraf
# (deploy/cron-monitoreo-ups). Ver docs/runbook_vm.md.
#
# Si hay un commit nuevo en la rama: actualiza el clon, construye la imagen, la prueba y recien
# entonces la promueve a :prod (la que usa compose.yaml). Si algo falla, :prod no cambia y el
# monitoreo sigue con la version anterior.
#
# Si no hay cambios no hace nada ni escribe en el log. Si un commit fallo, no lo reintenta en
# cada ejecucion (ni repite el aviso): espera el proximo commit, o FORCE=1 para reintentar a mano.
set -Eeuo pipefail

REPO_DIR="${REPO_DIR:-/etc/telegraf/monitoreo-ups}"
BRANCH="${BRANCH:-main}"
IMAGE="${IMAGE:-monitoreo-ups}"
PROD_TAG="${PROD_TAG:-prod}"
KEEP_IMAGES="${KEEP_IMAGES:-3}"
LOCK_FILE="${LOCK_FILE:-/run/lock/monitoreo-ups-deploy.lock}"
ENV_FILE="${ENV_FILE:-$REPO_DIR/.env}"
FORCE="${FORCE:-0}"

# Ultimo fallo avisado: el sha del commit que no se pudo desplegar, o "fetch" si no se pudo
# consultar GitLab. Esta en data/ porque esa carpeta esta ignorada y git clean no la toca.
ARCHIVO_FALLO="$REPO_DIR/data/deploy_fallido"

sha_remoto=""
# Imagen construida que todavia no paso el smoke test. Si el deploy falla se borra: si quedara,
# la proxima ejecucion la veria como "ya desplegada" y nunca reintentaria.
imagen_sin_probar=""

log() { echo "$(date --iso-8601=seconds) [deploy] $*"; }

notificar() {
  # Aviso a Google Chat con el mismo webhook del monitoreo. Si no hay webhook o falla el envio,
  # sigue igual: el aviso es un extra, el registro real es deploy.log.
  local url texto
  url="$(grep -E '^GOOGLE_CHAT_WEBHOOK_URL=' "$ENV_FILE" 2>/dev/null | cut -d= -f2- || true)"
  [[ -n "$url" ]] || return 0
  texto="${1//\\/\\\\}"
  texto="${texto//\"/\\\"}"
  curl -fsS --max-time 10 -H 'Content-Type: application/json' \
    -d "{\"text\": \"$texto\"}" "$url" >/dev/null || log "No se pudo enviar el aviso a Google Chat"
}

fallar() {
  log "ERROR: $1"
  if [[ -n "$imagen_sin_probar" ]]; then
    docker image rm "$imagen_sin_probar" >/dev/null 2>&1 || true
  fi
  local clave="${sha_remoto:-fetch}"
  if [[ "$(cat "$ARCHIVO_FALLO" 2>/dev/null)" != "$clave" ]]; then
    notificar "❌ Falló el deploy de monitoreo-ups ($1). Producción sigue con la versión anterior. Ver data/logs/deploy.log en la VM."
    echo "$clave" >"$ARCHIVO_FALLO" || true
  fi
  exit 1
}

# Los pasos principales llaman a fallar con un mensaje claro. Cualquier otro comando que falle
# (set -e) termina aca, con la linea para buscar en el log.
trap 'fallar "comando fallido en la línea $LINENO"' ERR

smoke_test() {
  local imagen="$1" salida

  # Las dependencias cargan (ezsnmp incluye su libreria de net-snmp)
  docker run --rm --network none --entrypoint python "$imagen" -c "import main" \
    || fallar "smoke test: la imagen no puede cargar el código (import main)"

  # Sin configuracion, el programa real (ENTRYPOINT) arranca, la valida y sale con 1 explicandolo
  if salida="$(docker run --rm --network none "$imagen" 2>&1 >/dev/null)"; then
    fallar "smoke test: sin configuración la imagen terminó con 0 (se esperaba 1)"
  elif [[ $? -ne 1 || "$salida" != *"SNMP_COMMUNITY"* ]]; then
    fallar "smoke test: sin configuración no salió con 1 avisando que falta SNMP_COMMUNITY: $salida"
  fi
}

limpiar_imagenes() {
  # Conserva las KEEP_IMAGES versiones mas nuevas (para rollback) ademas de :prod.
  # docker image ls lista de la mas nueva a la mas vieja: tail saltea las primeras.
  docker image ls "$IMAGE" --format '{{.Tag}}' \
    | grep -vE "^($PROD_TAG|<none>)$" \
    | tail -n +"$((KEEP_IMAGES + 1))" \
    | xargs -r -I{} docker image rm "$IMAGE:{}" >/dev/null || true
  # Imagenes sin tag que dejan los rebuilds, y cache de build de mas de una semana
  docker image prune -f >/dev/null || true
  docker builder prune -f --filter "until=168h" >/dev/null || true
}

main() {
  if [[ "$EUID" -eq 0 ]]; then
    # Como root, git y el lock quedarian de root y el cron (telegraf) no podria usarlos despues
    echo "Ejecutar como el dueño del clon: sudo -u telegraf $0" >&2
    exit 1
  fi

  # Un solo deploy a la vez: si el anterior sigue construyendo, este sale sin hacer nada
  exec 9>"$LOCK_FILE"
  if ! flock -n 9; then
    log "Otro deploy en curso, salgo."
    exit 0
  fi

  cd "$REPO_DIR"
  git fetch --quiet origin "$BRANCH" || fallar "no se pudo consultar GitLab (git fetch)"

  local sha_local sha_corto imagen
  sha_local="$(git rev-parse HEAD)"
  sha_remoto="$(git rev-parse "origin/$BRANCH")"
  sha_corto="$(git rev-parse --short=12 "origin/$BRANCH")"
  imagen="$IMAGE:$sha_corto"

  # Este commit ya fallo y se aviso: esperar uno nuevo (o FORCE=1)
  if [[ "$FORCE" != "1" && "$(cat "$ARCHIVO_FALLO" 2>/dev/null)" == "$sha_remoto" ]]; then
    exit 0
  fi

  # Nada que hacer: el clon esta al dia y su imagen existe
  if [[ "$sha_local" == "$sha_remoto" ]] && docker image inspect "$imagen" >/dev/null 2>&1; then
    rm -f "$ARCHIVO_FALLO"   # si habia fallado el fetch, ya se recupero
    exit 0
  fi

  if [[ "$sha_local" == "$sha_remoto" ]]; then
    log "Reintentando $sha_remoto"
  else
    log "Actualizando $sha_local -> $sha_remoto"
  fi
  git reset --hard --quiet "origin/$BRANCH"
  # Sin -x: los archivos ignorados (.env y data/, con la base y los logs) no se tocan
  git clean -fd --quiet

  log "Construyendo $imagen"
  imagen_sin_probar="$imagen"
  docker build --pull --progress=plain --build-arg GIT_SHA="$sha_corto" -t "$imagen" . \
    || fallar "falló el build de la imagen"

  log "Smoke test de $imagen"
  smoke_test "$imagen"

  # Recien aca cambia produccion: la proxima ejecucion de Telegraf usa la imagen nueva
  docker tag "$imagen" "$IMAGE:$PROD_TAG"
  imagen_sin_probar=""
  log "Promovida $imagen a :$PROD_TAG"
  rm -f "$ARCHIVO_FALLO"

  limpiar_imagenes
  notificar "✅ monitoreo-ups desplegado: $sha_corto — $(git log -1 --format=%s)"
}

# Todo el cuerpo esta en main(): bash lee la funcion completa antes de ejecutarla, asi el
# git reset que actualiza este mismo archivo no afecta a la ejecucion en curso.
main "$@"

#!/usr/bin/env bash
# Mide build, arranque, memoria y latencia del contenedor en un servidor Linux.
set -euo pipefail

RAIZ="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$RAIZ"

IMAGEN="${IMAGEN:-luzdelsur/embeddings:medicion}"
CONTENEDOR="${CONTENEDOR:-lds-embeddings-medicion}"
PUERTO="${PUERTO:-8000}"
MEMORIA="${MEMORIA:-1536m}"
REPETICIONES="${REPETICIONES:-30}"
SELLO="$(date +%Y%m%d_%H%M%S)"
SALIDA="$RAIZ/docs/medicion_docker_${SELLO}.txt"
LATENCIA_MD="$RAIZ/docs/latencia_docker_${SELLO}.md"
LOG_BUILD="$(mktemp)"
TIEMPOS="$(mktemp)"
PAYLOAD="$(mktemp)"

limpiar() {
    docker rm -f "$CONTENEDOR" >/dev/null 2>&1 || true
    rm -f "$LOG_BUILD" "$TIEMPOS" "$PAYLOAD"
}
trap limpiar EXIT
trap 'exit 130' INT TERM

fallar() {
    echo "ERROR: $*" >&2
    exit 1
}

ahora_ms() {
    date +%s%3N
}

puerto_ocupado() {
    if command -v ss >/dev/null 2>&1; then
        ss -ltn 2>/dev/null | awk '{print $4}' | grep -Eq "[:.]${PUERTO}$"
    elif command -v lsof >/dev/null 2>&1; then
        lsof -iTCP:"${PUERTO}" -sTCP:LISTEN >/dev/null 2>&1
    else
        (exec 3<>"/dev/tcp/127.0.0.1/${PUERTO}") >/dev/null 2>&1
    fi
}

main() {
    echo "== Entorno =="
    echo "Fecha: $(date -Iseconds)"
    echo "Arquitectura: $(uname -m)"
    cpu="$(lscpu 2>/dev/null | awk -F': +' '/Model name/{print $2; exit}')"
    nucleos="$(nproc 2>/dev/null || echo 'desconocidos')"
    echo "CPU: ${cpu:-no informada} (${nucleos} nucleos logicos)"
    echo "RAM total: $(awk '/MemTotal/{printf "%.1f GB", $2/1024/1024}' /proc/meminfo)"
    echo "RAM disponible: $(awk '/MemAvailable/{printf "%.1f GB", $2/1024/1024}' /proc/meminfo)"
    echo "Docker: $(docker version --format '{{.Server.Version}}' 2>/dev/null || echo 'no disponible')"
    echo "Memoria limite del contenedor: ${MEMORIA} (valor de partida, no validado)"

    command -v docker >/dev/null 2>&1 || fallar "Docker no esta instalado o no esta en el PATH."
    docker info >/dev/null 2>&1 || fallar "El daemon de Docker no responde. Enciendelo e intentalo de nuevo."
    command -v curl >/dev/null 2>&1 || fallar "Falta curl en el servidor."
    [ -f scripts/medir_latencia.py ] || fallar "No existe scripts/medir_latencia.py."
    docker rm -f "$CONTENEDOR" >/dev/null 2>&1 || true
    if puerto_ocupado; then
        fallar "El puerto ${PUERTO} esta ocupado. Liberalo o ejecuta PUERTO=8001 bash scripts/medir_docker.sh."
    fi

    echo
    echo "== Build =="
    inicio_build="$(date +%s)"
    if ! docker build -t "$IMAGEN" . >"$LOG_BUILD" 2>&1; then
        tail -n 40 "$LOG_BUILD"
        fallar "docker build fallo. Revisa el log anterior."
    fi
    fin_build="$(date +%s)"
    cat "$LOG_BUILD"
    tam_bytes="$(docker image inspect "$IMAGEN" --format '{{.Size}}')"
    echo "Tiempo de build: $((fin_build - inicio_build)) s"
    echo "Tamano de imagen: $(awk -v b="$tam_bytes" 'BEGIN{printf "%.1f MB", b/1048576}') (${tam_bytes} bytes)"
    docker images --format 'table {{.Repository}}:{{.Tag}}\t{{.Size}}' "$IMAGEN"

    echo
    echo "== Arranque =="
    inicio_ms="$(ahora_ms)"
    docker run -d --name "$CONTENEDOR" --memory="$MEMORIA" \
        -p "127.0.0.1:${PUERTO}:8000" "$IMAGEN" >/dev/null

    listo=0
    for _ in {1..90}; do
        if curl -fsS --max-time 5 "http://127.0.0.1:${PUERTO}/health" 2>/dev/null \
            | grep -q '"modelo_cargado"[[:space:]]*:[[:space:]]*true'; then
            listo=1
            break
        fi
        if ! docker ps --format '{{.Names}}' | grep -qx "$CONTENEDOR"; then
            docker logs "$CONTENEDOR" 2>&1 | tail -n 40 || true
            fallar "El contenedor termino antes de cargar el modelo."
        fi
        sleep 2
    done
    if [ "$listo" -ne 1 ]; then
        docker logs "$CONTENEDOR" 2>&1 | tail -n 80 || true
        fallar "El modelo no cargo en 180 s."
    fi
    fin_ms="$(ahora_ms)"
    echo "Tiempo hasta modelo_cargado=true: $((fin_ms - inicio_ms)) ms"
    echo "GET /health:"
    curl -sS --max-time 10 "http://127.0.0.1:${PUERTO}/health"
    echo

    echo
    echo "== 5 peticiones y memoria =="
    for _ in 1 2 3; do
        echo "POST /api/v1/similarity:"
        curl -sS --max-time 30 -X POST "http://127.0.0.1:${PUERTO}/api/v1/similarity" \
            -H "Content-Type: application/json" \
            -d '{"text_a":"Se escucho una explosion y se apago toda mi cuadra","text_b":"Sonó un fuerte ruido del transformador y no hay luz"}'
        echo
    done
    for _ in 1 2; do
        echo "POST /api/v1/similarity/batch:"
        curl -sS --max-time 30 -X POST "http://127.0.0.1:${PUERTO}/api/v1/similarity/batch" \
            -H "Content-Type: application/json" \
            -d '{"text":"No hay luz en toda la cuadra","candidates":["Corte de energia en la zona","Falla del medidor","Se cayo un poste y hay cables en la pista"]}'
        echo
    done

    echo
    echo "docker stats despues de 5 peticiones:"
    docker stats --no-stream \
        --format 'table {{.Name}}\t{{.CPUPerc}}\t{{.MemUsage}}\t{{.MemPerc}}' "$CONTENEDOR"

    echo
    echo "== Verificacion con 4 candidatos (uso real del backend) =="
    cat >"$PAYLOAD" <<'JSON'
{"text":"Se escucho una explosion y se apago toda mi cuadra","candidates":["No hay luz en toda la cuadra","Sonó un fuerte ruido del transformador","Se cayo un poste y hay cables en la pista","Mi luz parpadea solo en mi casa"]}
JSON
    for _ in {1..10}; do
        curl -sS --max-time 30 -o /dev/null -w '%{time_total}\n' \
            -X POST "http://127.0.0.1:${PUERTO}/api/v1/similarity/batch" \
            -H "Content-Type: application/json" \
            --data-binary @"$PAYLOAD"
    done >"$TIEMPOS"
    awk '{ ms=$1*1000; suma+=ms; if (ms>maximo) maximo=ms; n++ } END { printf "Lote de 4: promedio %.1f ms, maximo %.1f ms (%d peticiones)\n", suma/n, maximo, n; if (maximo > 1000) print "ADVERTENCIA: el lote de 4 candidatos supero 1000 ms." }' "$TIEMPOS"

    echo
    echo "== Latencia con scripts/medir_latencia.py (mismos escenarios) =="
    docker cp scripts/medir_latencia.py "$CONTENEDOR:/tmp/medir_latencia.py"
    docker exec "$CONTENEDOR" python /tmp/medir_latencia.py \
        --url "http://127.0.0.1:8000" \
        --repeticiones "$REPETICIONES" \
        --salida /tmp/latencia_docker.md
    docker cp "$CONTENEDOR:/tmp/latencia_docker.md" "$LATENCIA_MD"
    echo "Tabla de latencia copiada a $LATENCIA_MD"

    echo
    echo "== Contenido de la imagen =="
    docker run --rm "$IMAGEN" ls -la /app
    docker run --rm "$IMAGEN" sh -c '
set -eu
for ruta in /app/.env /app/.git /app/tests /app/scripts /app/docs; do
    if [ -e "$ruta" ]; then
        echo "PROHIBIDO: existe $ruta"
        exit 1
    fi
done
if find /app \( -name "pares_calibracion.csv" -o -name "calibracion_*.csv" \) | grep -q .; then
    echo "PROHIBIDO: hay datos de calibracion"
    exit 1
fi
echo "OK: sin .env, .git, tests, scripts, docs ni datos de calibracion en /app"
'

    echo
    echo "== Fin =="
    echo "Salida guardada en $SALIDA"
    echo "Latencia guardada en $LATENCIA_MD"
    echo "El limite de ${MEMORIA} NO queda validado: revisar docker stats antes de produccion."
}

mkdir -p "$RAIZ/docs"
main "$@" 2>&1 | tee "$SALIDA"

# ==============================================================================
# Etapa 1: Builder (Entorno de compilación e instalación de dependencias)
# ==============================================================================
FROM python:3.12-slim AS builder

WORKDIR /build

# Variables de entorno de optimización para Pip y Python
ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PIP_NO_CACHE_DIR=1 \
    PIP_DISABLE_PIP_VERSION_CHECK=1

# Instalar dependencias del sistema mínimas para compilar extensiones C si fueran requeridas
RUN apt-get update && apt-get install -y --no-install-recommends \
    build-essential \
    curl \
    && rm -rf /var/lib/apt/lists/*

# Crear entorno virtual dedicado para aislar paquetes instalados
RUN python -m venv /opt/venv
ENV PATH="/opt/venv/bin:$PATH"

# Copiar únicamente requirements.txt para maximizar el reuso de caché de Docker
COPY backend_case/requirements.txt .
RUN pip install --upgrade pip && \
    pip install -r requirements.txt

# ==============================================================================
# Etapa 2: Runner (Imagen de producción ligera y con usuario sin privilegios)
# ==============================================================================
FROM python:3.12-slim AS runner

WORKDIR /workspace

# Variables de entorno de ejecución para Python y FastAPI
ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PATH="/opt/venv/bin:$PATH" \
    PYTHONPATH="/workspace:/workspace/backend_case" \
    PORT=8000

# Instalar utilidades mínimas de runtime (curl para healthcheck)
RUN apt-get update && apt-get install -y --no-install-recommends \
    curl \
    && rm -rf /var/lib/apt/lists/*

# Seguridad: Crear usuario y grupo de sistema sin privilegios root
RUN groupadd -r -g 10001 appgroup && \
    useradd -r -u 10001 -g appgroup -d /workspace -s /sbin/nologin -c "App User" appuser

# Copiar el entorno virtual con todas las dependencias ya resueltas
COPY --from=builder /opt/venv /opt/venv

# Copiar el código del dominio puro UML, scaffolding móvil y backend de la aplicación
COPY --chown=appuser:appgroup core/ ./core/
COPY --chown=appuser:appgroup mobile_app_reference/ ./mobile_app_reference/
COPY --chown=appuser:appgroup backend_case/ ./backend_case/

# Establecer directorio de trabajo de la aplicación FastAPI
WORKDIR /workspace/backend_case

# Asegurar permisos de ejecución en el script de entrada
RUN chmod +x /workspace/backend_case/entrypoint.sh

# Ejecutar como usuario sin privilegios root
USER appuser

# Exponer el puerto del backend ASGI
EXPOSE 8000

# Healthcheck de disponibilidad del servicio FastAPI
HEALTHCHECK --interval=30s --timeout=5s --start-period=15s --retries=3 \
    CMD curl -f http://localhost:8000/docs || exit 1

# Script de entrada para inicialización determinística previa al fork de workers
ENTRYPOINT ["/workspace/backend_case/entrypoint.sh"]

# Comando de arranque del servidor Uvicorn con soporte WebSockets y multi-worker
CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000", "--workers", "2", "--ws-max-size", "8192"]

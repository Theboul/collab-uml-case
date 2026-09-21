# ==============================================================================
# Etapa 1: Builder (Compilación de la aplicación Angular SPA)
# ==============================================================================
FROM node:20-alpine AS builder

WORKDIR /app

# Asignar límite de memoria para evitar OOM durante la compilación de Angular/Tailwind
ENV NODE_OPTIONS="--max-old-space-size=4096"

# Copiar manifiestos de paquetes para aprovechar la caché de capas de Docker
COPY package*.json ./

# Instalar dependencias del proyecto
RUN npm install

# Copiar la totalidad del código fuente de la aplicación frontend
COPY . .

# Compilar la aplicación Angular para entorno de producción
RUN npm run build

# ==============================================================================
# Etapa 2: Runner (Servidor Web Nginx Alpine con soporte SSL/TLS y Certbot)
# ==============================================================================
FROM nginx:1.27-alpine AS runner

# Instalar OpenSSL para gestión y generación de certificados SSL
RUN apk add --no-cache openssl

# Copiar configuración personalizada de Nginx
COPY nginx.conf /etc/nginx/conf.d/default.conf

# Copiar script de inicialización para certificados SSL
COPY entrypoint.sh /entrypoint.sh
RUN chmod +x /entrypoint.sh && sed -i 's/\r$//' /entrypoint.sh

# Copiar los archivos estáticos generados en la etapa de compilación
COPY --from=builder /app/dist/front_generador_bd/browser /usr/share/nginx/html

# Exponer puertos estándar HTTP y HTTPS
EXPOSE 80 443

# Healthcheck de disponibilidad de Nginx mediante endpoint dedicado /healthz
HEALTHCHECK --interval=30s --timeout=3s --start-period=5s --retries=3 \
    CMD wget -qO- http://127.0.0.1/healthz || exit 1

# Punto de entrada para inicialización determinística de certificados SSL
ENTRYPOINT ["/entrypoint.sh"]

# Ejecutar Nginx en primer plano
CMD ["nginx", "-g", "daemon off;"]

#!/bin/sh
set -e

SSL_DIR="/etc/nginx/ssl/live"
DEFAULT_CERT="${SSL_DIR}/fullchain.pem"
DEFAULT_KEY="${SSL_DIR}/privkey.pem"
CERTBOT_DIR="/var/www/certbot"

# Asegurar existencia de directorios clave
mkdir -p "${SSL_DIR}" "${CERTBOT_DIR}"

# 1. Comprobar si Certbot generó certificados oficiales en un subdirectorio de dominio
# (Ejemplo: /etc/nginx/ssl/live/midominio.com/fullchain.pem)
OFFICIAL_CERT=$(find /etc/nginx/ssl/live -mindepth 2 -maxdepth 2 -name "fullchain.pem" 2>/dev/null | head -n 1)
if [ -n "${OFFICIAL_CERT}" ]; then
    OFFICIAL_DIR=$(dirname "${OFFICIAL_CERT}")
    echo "[nginx-entrypoint] Se detectó certificado oficial de Certbot en: ${OFFICIAL_DIR}"
    # Crear enlaces simbólicos a la ruta canónica usada por nginx.conf
    ln -sf "${OFFICIAL_DIR}/fullchain.pem" "${DEFAULT_CERT}"
    ln -sf "${OFFICIAL_DIR}/privkey.pem" "${DEFAULT_KEY}"
fi

# 2. Si no existen certificados (ni oficiales ni autofirmados), generar autofirmado de contingencia
if [ ! -f "${DEFAULT_CERT}" ] || [ ! -f "${DEFAULT_KEY}" ]; then
    echo "[nginx-entrypoint] No se encontraron certificados SSL en ${SSL_DIR}."
    echo "[nginx-entrypoint] Generando certificado SSL autofirmado de contingencia con soporte SAN (Subject Alternative Names)..."

    OPENSSL_CNF="/tmp/openssl_san.cnf"
    cat > "${OPENSSL_CNF}" << 'EOF'
[req]
default_bits = 2048
prompt = no
default_md = sha256
distinguished_name = dn
x509_extensions = v3_req

[dn]
C = US
ST = Cloud
L = Deployment
O = SchemaCraft UML CASE
OU = Infrastructure
CN = localhost

[v3_req]
subjectAltName = @alt_names
basicConstraints = CA:FALSE
keyUsage = nonRepudiation, digitalSignature, keyEncipherment
extendedKeyUsage = serverAuth

[alt_names]
DNS.1 = localhost
DNS.2 = *.localhost
DNS.3 = *.amazonaws.com
DNS.4 = *.compute.amazonaws.com
DNS.5 = *.compute-1.amazonaws.com
IP.1 = 127.0.0.1
IP.2 = 0.0.0.0
EOF

    openssl req -x509 -nodes -days 365 -newkey rsa:2048 \
        -keyout "${DEFAULT_KEY}" \
        -out "${DEFAULT_CERT}" \
        -config "${OPENSSL_CNF}" 2>/dev/null

    rm -f "${OPENSSL_CNF}"
    echo "[nginx-entrypoint] Certificado autofirmado generado exitosamente en ${SSL_DIR}."
else
    echo "[nginx-entrypoint] Certificados SSL validados en ${SSL_DIR}."
fi

echo "[nginx-entrypoint] Iniciando Nginx..."
exec "$@"

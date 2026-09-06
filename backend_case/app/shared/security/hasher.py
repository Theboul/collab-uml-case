"""
Utilidades criptográficas de hash y verificación de contraseñas.
Implementa PBKDF2-HMAC-SHA256 con salt criptográfico y comparación de tiempo constante.
"""

import hashlib
import hmac
import os

ITERATIONS = 310_000  # OWASP recommendation for PBKDF2-SHA256
SALT_SIZE = 16


def hash_password(password: str) -> str:
    """
    Genera un hash seguro con salt para la contraseña especificada.
    Formato retornado: pbkdf2_sha256$<iteraciones>$<salt_hex>$<hash_hex>
    """
    salt = os.urandom(SALT_SIZE)
    key = hashlib.pbkdf2_hmac(
        "sha256",
        password.encode("utf-8"),
        salt,
        ITERATIONS,
    )
    return f"pbkdf2_sha256${ITERATIONS}${salt.hex()}${key.hex()}"


def verify_password(plain_password: str, hashed_password: str) -> bool:
    """
    Verifica si una contraseña en texto plano coincide con el hash almacenado
    utilizando comparación en tiempo constante para mitigar timing attacks.
    """
    if not hashed_password or not hashed_password.startswith("pbkdf2_sha256$"):
        return False

    try:
        parts = hashed_password.split("$")
        if len(parts) != 4:
            return False

        _, iterations_str, salt_hex, stored_key_hex = parts
        iterations = int(iterations_str)
        salt = bytes.fromhex(salt_hex)

        new_key = hashlib.pbkdf2_hmac(
            "sha256",
            plain_password.encode("utf-8"),
            salt,
            iterations,
        )
        return hmac.compare_digest(new_key.hex(), stored_key_hex)
    except (ValueError, TypeError):
        return False

# Especificación Técnica de Autenticación, Identidad y Sesiones — SchemaCraft

> **Módulo:** Seguridad, Autenticación y Autorización Contextual  
> **Alcance:** Backend FastAPI (`backend_case`), Frontend Angular (`front_generador_bd`) y Protocolos de Tiempo Real (WebSockets).  
> **Casos de Uso relacionados:** CU2 (Gestión de Cuentas), CU5 (Colaboración Multiusuario), ADR-0005.

---

## 1. Principios Rectores y Aislamiento

1. **Aislamiento Total del Dominio UML (`core/uml_domain`)**:
   - El núcleo `core/uml_domain` no conoce usuarios, contraseñas, tokens JWT, cookies ni proveedores OAuth.
   - El AST UML vive serializado dentro de la columna `projects.semantic_model`. La seguridad envuelve al dominio desde la capa de aplicación/infraestructura, nunca desde su núcleo.

2. **Identidad Única Interna (`userId`)**:
   - Cada usuario posee un único identificador inmutable (`UUID`) en la tabla `users`.
   - Múltiples métodos de autenticación (contraseña local, Google OIDC, futuros proveedores como GitHub) se vinculan a ese mismo `userId` mediante la tabla `user_identities`.
   - Toda la aplicación (proyectos, auditoría, sockets de colaboración) opera exclusivamente con `userId`.

3. **Roles Contextuales por Lienzo (No Globales)**:
   - Los roles **Anfitrión** y **Colaborador** **no** pertenecen a la cuenta del usuario de forma global.
   - Pertenecen al contexto de cada proyecto/lienzo específico:
     - **Anfitrión (Host)**: Creador/propietario del proyecto (`project.owner_id == user.id`).
     - **Colaborador (Guest)**: Usuario autenticado registrado en `project_collaborators` que ingresa mediante código/enlace de sala.

4. **Sesión Robusta y Autorizada por el Servidor**:
   - **Access Token (JWT)**: Vida corta (15 minutos), portado en cabecera HTTP `Authorization: Bearer <token>`.
   - **Refresh Token (Opaco/Criptográfico)**: Vida media (7 a 14 días), almacenado exclusivamente en una cookie `HttpOnly`, `Secure`, `SameSite=Lax`.
   - **Revocación Server-Side**: Los refresh tokens se almacenan hasheados en `user_sessions`, permitiendo invalidar sesiones activas o cerrar sesión en todos los dispositivos.

---

## 2. Diagrama de Arquitectura de Autenticación

```
   ┌─────────────────────────────────────────────────────────────┐
   │                     MÉTODOS DE ACCESO                       │
   │   ┌─────────────────────┐         ┌─────────────────────┐   │
   │   │ Correo + Contraseña │         │     Google OIDC     │   │
   │   └──────────┬──────────┘         └──────────┬──────────┘   │
   └──────────────┼───────────────────────────────┼──────────────┘
                  │                               │
                  ▼                               ▼
   ┌─────────────────────────────────────────────────────────────┐
   │                   FastAPI / Security Gateway                │
   │   ┌────────────────────────┐   ┌────────────────────────┐   │
   │   │ Verificador Argon2id   │   │ Verificador Google GIS │   │
   │   └──────────┬─────────────┘   └──────────┬─────────────┘   │
   └──────────────┼────────────────────────────┼─────────────────┘
                  │                            │
                  ▼                            ▼
   ┌─────────────────────────────────────────────────────────────┐
   │                  Servicio de Identidad Unificada            │
   │   - Busca o crea registro en `users`                        │
   │   - Asocia / valida en `user_identities`                    │
   └──────────────────────────────┬──────────────────────────────┘
                                  │
                                  ▼
   ┌─────────────────────────────────────────────────────────────┐
   │                   Gestor de Sesiones JWT                    │
   │   - Emite Access Token (15 min) en JSON Body                │
   │   - Emite Refresh Token (7 días) en Cookie HttpOnly         │
   │   - Registra sesión activa en tabla `user_sessions`         │
   └──────────────────────────────┬──────────────────────────────┘
                                  │
                                  ▼
   ┌─────────────────────────────────────────────────────────────┐
   │                  Consumo en el CASE                         │
   │                                                             │
   │   Lienzo A (Creado por User 1):                             │
   │     ├─ User 1 (owner_id) ──> Rol: ANFITRIÓN                 │
   │     └─ User 2 (invitado) ──> Rol: COLABORADOR               │
   │                                                             │
   │   Lienzo B (Creado por User 2):                             │
   │     ├─ User 2 (owner_id) ──> Rol: ANFITRIÓN                 │
   │     └─ User 1 (invitado) ──> Rol: COLABORADOR               │
   └─────────────────────────────────────────────────────────────┘
```

---

## 3. Flujos de Autenticación en Detalle

### 3.1 Flujo: Inicio de Sesión con Correo y Contraseña
1. **Frontend (`ScLoginComponent`)**:
   - El usuario envía `email` y `password` a `POST /api/v2/auth/login`.
2. **Backend (`backend_case/app/shared/security`)**:
   - Consulta `user_identities` con `provider = 'password'` y `provider_user_id = LOWER(email)`.
   - Si no existe: lanza error `401 Unauthorized` (`AUTH_INVALID_CREDENTIALS`).
   - Verifica el hash de contraseña usando **Argon2id** (o `bcrypt`).
   - Verifica que el usuario padre en `users` tenga `is_active = true`.
   - Genera:
     - `accessToken`: JWT firmado con `HS256` o `RS256`, expiración a los 15 minutos, conteniendo `{ sub: userId, email, fullName }`.
     - `refreshToken`: Cadena pseudoaleatoria de alta entropía (32 bytes / 256 bits).
     - Almacena `SHA-256(refreshToken)` en `user_sessions` con `expires_at = NOW() + 7 days`.
3. **Respuesta HTTP**:
   - Encabezado: `Set-Cookie: sc_refresh_token=<token>; HttpOnly; Secure; SameSite=Lax; Path=/api/v2/auth; Max-Age=604800`
   - Cuerpo JSON:
     ```json
     {
       "accessToken": "eyJhbGciOi...",
       "tokenType": "Bearer",
       "expiresIn": 900,
       "user": {
         "id": "a1b2c3d4-0001-4000-8000-000000000001",
         "email": "alex.rivera@ejemplo.com",
         "fullName": "Alex Rivera",
         "avatarUrl": null
       }
     }
     ```

---

### 3.2 Flujo: Inicio de Sesión con Google OAuth 2.0 / OpenID Connect (OIDC)
El sistema utiliza el flujo seguro **Google Identity Services (GIS)** con verificación de firma en servidor:

1. **Frontend**:
   - Despliega el botón oficial de Google o inicia el flujo con `google.accounts.id.prompt()`.
   - Google autentica al usuario y entrega un **ID Token (JWT firmado por Google)** en el cliente.
   - El frontend envía dicho token al backend: `POST /api/v2/auth/google` con cuerpo `{ "credential": "<google_id_token>" }`.
2. **Backend**:
   - Valida el token contra los certificados públicos de Google (`https://www.googleapis.com/oauth2/v3/certs`) comprobando:
     - Firma criptográfica válida.
     - `aud` (audience) coincide exactamente con `GOOGLE_CLIENT_ID`.
     - `iss` pertenece a `accounts.google.com` o `https://accounts.google.com`.
     - `exp` es posterior a la hora actual.
   - Extrae los claims del token:
     - `sub`: Identificador único inmutable del usuario en Google.
     - `email`: Correo verificado por Google.
     - `name`: Nombre completo del usuario.
     - `picture`: URL de foto de perfil.
3. **Mapeo / Vinculación de Identidades (Account Linking)**:
   - **Caso 1: Identidad Google ya registrada**:
     - Existe `user_identities` con `provider = 'google'` y `provider_user_id = sub`.
     - Recupera el `user_id` asociado e inicia sesión.
   - **Caso 2: Usuario existente con ese email (creado previamente por contraseña)**:
     - No existe identidad de Google, pero `email` coincide en la tabla `users`.
     - Vincula automáticamente la nueva identidad de Google a ese mismo `user_id`:
       `INSERT INTO user_identities (user_id, provider, provider_user_id) VALUES (user.id, 'google', sub)`.
   - **Caso 3: Usuario completamente nuevo**:
     - Inserta en `users` con `email`, `full_name = name`, `avatar_url = picture`, `is_verified = true`.
     - Inserta en `user_identities` con `provider = 'google'`, `provider_user_id = sub`.
4. **Respuesta**: Idéntica al flujo de correo (Access Token en JSON + Cookie HttpOnly de Refresh Token).

---

### 3.3 Flujo: Renovación de Token (`Refresh Token Rotation`)
Cuando el Access Token expira (cada 15 min), Angular intercepta el `401 Unauthorized` de forma transparente:

1. **Frontend**:
   - `AuthInterceptor` detecta expiración y solicita renovación a `POST /api/v2/auth/refresh`.
   - La petición viaja con `withCredentials: true` (el navegador adjunta automáticamente la cookie `sc_refresh_token`).
2. **Backend**:
   - Lee la cookie `sc_refresh_token`.
   - Calcula `SHA-256(sc_refresh_token)` y busca en `user_sessions` donde `expires_at > NOW()`.
   - Si la sesión no existe (posible token reusado o robado): invalida todas las sesiones de ese usuario como medida de seguridad.
   - Si es válida:
     - Rota el Refresh Token: genera uno nuevo y actualiza el hash en `user_sessions`.
     - Genera un nuevo Access Token.
3. **Respuesta**:
   - Nueva Cookie `sc_refresh_token` actualizada.
   - JSON con el nuevo `accessToken`.

---

### 3.4 Flujo: Cierre de Sesión (Logout)
1. **Frontend**:
   - El usuario pulsa "Cerrar sesión" en `sc-app-shell` o expira su sesión.
   - Envía `POST /api/v2/auth/logout`.
2. **Backend**:
   - Lee el `sc_refresh_token` de la cookie.
   - Elimina la sesión activa de la tabla `user_sessions` (revocación inmediata en base de datos).
   - Invalida la cookie en el cliente emitiendo:
     `Set-Cookie: sc_refresh_token=; Max-Age=0; Expires=Thu, 01 Jan 1970 00:00:00 GMT; HttpOnly; Path=/api/v2/auth`
   - Retorna `204 No Content`.
3. **Frontend**:
   - Limpia el Access Token de la memoria/almacenamiento del cliente.
   - Limpia los datos de perfil cacheados (`sc_user`).
   - Redirige inmediatamente a `/login`.

---

## 4. Contrato de Endpoints REST (`/api/v2/auth/...`)

Todos los endpoints respetan el formato canónico de la arquitectura:

### 1. Registro con Contraseña
- **Ruta:** `POST /api/v2/auth/register`
- **Request Body:**
  ```json
  {
    "email": "alex.rivera@ejemplo.com",
    "password": "PasswordSeguro123!",
    "fullName": "Alex Rivera"
  }
  ```
- **Response (201 Created):** Access Token + User Info + Cookie HttpOnly.

### 2. Login con Contraseña
- **Ruta:** `POST /api/v2/auth/login`
- **Request Body:**
  ```json
  {
    "email": "alex.rivera@ejemplo.com",
    "password": "PasswordSeguro123!"
  }
  ```
- **Response (200 OK):** Access Token + User Info + Cookie HttpOnly.

### 3. Autenticación con Google (OIDC)
- **Ruta:** `POST /api/v2/auth/google`
- **Request Body:**
  ```json
  {
    "credential": "eyJhbGciOiJSUzI1NiIs..."
  }
  ```
- **Response (200 OK):** Access Token + User Info + Cookie HttpOnly.

### 4. Renovación de Sesión (Refresh)
- **Ruta:** `POST /api/v2/auth/refresh`
- **Headers:** Envío automático de cookie `sc_refresh_token`.
- **Response (200 OK):** Nuevo `accessToken` + nueva Cookie rotada.

### 5. Cierre de Sesión (Logout)
- **Ruta:** `POST /api/v2/auth/logout`
- **Response (204 No Content):** Cookie revocada y registro eliminado en `user_sessions`.

### 6. Usuario Actual (Me)
- **Ruta:** `GET /api/v2/auth/me`
- **Headers:** `Authorization: Bearer <accessToken>`
- **Response (200 OK):**
  ```json
  {
    "id": "a1b2c3d4-0001-4000-8000-000000000001",
    "email": "alex.rivera@ejemplo.com",
    "fullName": "Alex Rivera",
    "avatarUrl": null,
    "identities": ["password", "google"]
  }
  ```

---

## 5. Autorización Contextual: Anfitrión vs. Colaborador

En el módulo de modelado (`modeling`) y colaboración en tiempo real (`collaboration`):

| Acción en el Proyecto / Lienzo | Anfitrión (`HOST`) | Colaborador (`COLLABORATOR`) |
|---|:---:|:---:|
| Ver el esquema y componentes |  Sí |  Sí |
| Solicitar candado de edición sobre una entidad (`LockStore`) |  Sí |  Sí |
| Modificar atributos/métodos bajo candado |  Sí |  Sí |
| Invitar colaboradores (código o enlace de sala) |  Sí |  No |
| Forzar liberación de candados de otros usuarios |  Sí |  No |
| Cambiar motor de BD (PostgreSQL / MySQL / SQLite) |  Sí |  No |
| Exportar SQL DDL / Spring Boot / Postman |  Sí |  Sí |
| Renombrar el proyecto |  Sí |  No |
| Eliminar el proyecto definitivamente |  Sí |  No |

---

## 6. Manejo de Errores Canónicos

Siguiendo la sección 7 de `AGENTS.md`:

```json
{
  "code": "AUTH_INVALID_CREDENTIALS",
  "message": "El correo o la contraseña ingresados son incorrectos.",
  "details": []
}
```

Códigos definidos:
- `AUTH_INVALID_CREDENTIALS`: Credenciales no válidas.
- `AUTH_EMAIL_ALREADY_EXISTS`: Intento de registrar un correo ya existente con password.
- `AUTH_GOOGLE_TOKEN_INVALID`: ID token de Google corrupto o firma no verificable.
- `AUTH_SESSION_EXPIRED`: Refresh token expirado o revocado.
- `AUTH_FORBIDDEN_ACTION`: Acción reservada exclusivamente para el Anfitrión del lienzo.

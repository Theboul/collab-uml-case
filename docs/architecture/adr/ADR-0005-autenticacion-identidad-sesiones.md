# ADR-0005: Modelo de Autenticación, Identidad Unificada y Roles Contextuales (Anfitrión vs. Colaborador)

**Estado:** Aprobado  
**Fecha:** 2026-09-05  
**Decisores:** Equipo de Arquitectura / Antigravity  
**Casos de Uso relacionados:** CU2 (Gestión de Cuentas), CU5 (Colaboración Concurrente Multiusuario)  

---

## Contexto

El sistema CASE colaborativo SchemaCraft requiere un mecanismo de autenticación independiente del modelador UML que soporte:
1. Registro e inicio de sesión tradicional mediante correo y contraseña.
2. Autenticación delegada federada mediante proveedores externos OAuth 2.0 / OIDC (iniciando con Google y extensible a GitHub).
3. Una identidad única de usuario (`userId`) independiente del método o cantidad de proveedores utilizados.
4. Distinción de privilegios entre **Anfitrión** (creador de la sala/lienzo) y **Colaborador** (invitado mediante código o enlace).

Anteriormente, existía ambigüedad sobre si los roles debían ser atributos estáticos de la cuenta del usuario (`user.role = 'host'`) o si debían determinarse dinámicamente según el espacio de trabajo. Adicionalmente, el principio de arquitectura establece que `core/uml_domain` debe permanecer 100% puro e ignorar cualquier concepto de credenciales o sesiones.

---

## Decisión

1. **Desacoplamiento Estricto del Dominio UML**:
   - `core/uml_domain` no posee entidades ni referencias a usuarios, sesiones ni contraseñas.
   - El módulo de autenticación reside en la capa transversal de seguridad (`backend_case/app/shared/security/`).

2. **Identidad Unificada Multi-Proveedor (1:N)**:
   - La tabla principal `users` almacena los datos de perfil y el identificador canónico `id UUID`.
   - La tabla `user_identities` almacena los métodos de acceso (`password` con Argon2id, `google` con sub OIDC).
   - Se unifican automáticamente las identidades cuando un usuario con cuenta de contraseña decide iniciar sesión con Google utilizando el mismo correo verificado.

3. **Roles Contextuales por Lienzo (No Globales)**:
   - Un usuario no es Anfitrión de forma global en su perfil.
   - En cada proyecto/lienzo:
     - Si `project.owner_id == current_user.id`, el usuario opera como **Anfitrión** (administración de sala, eliminación, cambio de motor BD).
     - Si el usuario se une a un proyecto mediante enlace o código de sala (`room_name`), se registra en la tabla `project_collaborators` y opera como **Colaborador** (edición concurrente solicitando candados al `LockStore`).

4. **Gestión de Sesiones JWT Híbrida**:
   - **Access Token (JWT)** de corta duración (15 minutos) transportado en `Authorization: Bearer` para llamadas API y WebSockets.
   - **Refresh Token** de rotación estricta almacenado en cookie segura `HttpOnly`, `SameSite=Lax`, con hash registrado en la tabla `user_sessions` para permitir revocación inmediata en servidor (logout real).

---

## Consecuencias

### Positivas:
- **Cero contaminación del dominio**: La librería `core/uml_domain` permanece completamente pura y portable.
- **Soporte multi-proveedor limpio**: Agregar nuevos proveedores OIDC (GitHub, GitLab, etc.) en el futuro requiere únicamente un nuevo registro en `user_identities` sin alterar el resto de la base de datos.
- **Flexibilidad total de roles**: Una misma persona puede ser Anfitrión en su proyecto personal de comercio electrónico y Colaborador en el proyecto hospitalario de su colega.
- **Seguridad estándar de la industria**: La combinación de JWT en memoria y Refresh Token en cookie `HttpOnly` previene ataques XSS y CSRF.

### Negativas / Mitigaciones:
- Requiere implementar interceptores HTTP en Angular para renovar el token transparente antes de su vencimiento cada 15 minutos (mitigado mediante `AuthInterceptor` estándar en Angular).

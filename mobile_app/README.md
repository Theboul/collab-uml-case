# mobile_app — cliente móvil de gestión (CU12 + CU13)

Proyecto **Flutter separado de SchemaCraft**: no comparte código con el CASE ni toca
`core/uml_domain`. Consume el backend Spring Boot que **CU10** genera a partir del modelo UML
(dominio de ejemplo: `Pedido`, `Producto` y la intermedia `PedidoProducto`).

- **CU12** — ejecutar operaciones de gestión (crear / consultar / actualizar / eliminar).
- **CU13** — offline y sincronización (pendiente; la política de conflictos se decide aparte).

Decisiones y hallazgos: [`docs/decisions.md`](docs/decisions.md). El scaffold legacy
(`mobile_app_reference/`) se descartó como base (ver ese documento y `CLAUDE.md`).

## Estructura

```
lib/
  config/       ApiConfig (URL base por --dart-define)
  models/       Entity + Pedido/Producto/PedidoProducto (id explícito, Long → int)
  domain/       FieldSpec, FieldValidator (validación por tipo), EntityModule (metadatos del modelo)
  data/         ApiClient (HTTP + red), EntityRepository (operaciones + verificación), failures
  ui/           Inicio → menú de operaciones → listado/búsqueda → formulario / detalle
backend_cu10/   Backend generado por CU10 (fixture) + scripts de arranque + SQL de la base propia
test/           Unitarios y de widgets (backend simulado que reproduce las manías reales medidas)
test_backend/   Integración REAL contra el backend levantado
integration_test/  UI de punta a punta en un teléfono real
tool/           dev-env.cmd (toolchain solo para la sesión) y run-integration.cmd
```

## Toolchain (sin admin, en `C:\Users\alex\dev`)

| Componente | Ubicación |
|---|---|
| Flutter SDK (estable) | `C:\Users\alex\dev\flutter` |
| Android SDK (cmdline-tools + platform-tools + plataforma/build-tools) | `C:\Users\alex\dev\android-sdk` |
| JDK 21 (ya instalado) | `C:\Program Files\Java\jdk-21.0.12.1` |

No se tocó el PATH del sistema. En cada ventana de cmd: `call mobile_app\tool\dev-env.cmd`.

## Backend para desarrollo y pruebas

`backend_cu10/` es el proyecto Spring Boot generado por CU10 para este dominio, sin modificar
(solo se sobreescribe la conexión a la base con variables de entorno).

- **H2 en memoria** (tests y demos; con datos semilla `seed.sql`): `backend_cu10\run-h2.cmd` → `http://localhost:9000`.
- **PostgreSQL dedicado** (`gestion_movil`, nunca el usuario `postgres`): primero crear la base **una vez**,
  escribiendo tú la contraseña de `postgres`:

  ```
  & "C:\Program Files\PostgreSQL\17\bin\psql.exe" -U postgres -h localhost -f mobile_app\backend_cu10\create_dev_db.sql
  ```

  y luego `backend_cu10\run-postgres.cmd`. Para recrearla de cero:
  `DROP DATABASE gestion_movil; DROP ROLE gestion_movil;` y volver a ejecutar el `.sql`.
  (La contraseña `gestion_movil_dev` es solo de desarrollo local, sin valor.)

## Ejecutar

```
call mobile_app\tool\dev-env.cmd
cd mobile_app
flutter pub get
flutter analyze
flutter test                      # unitarios + widgets (sin red)
mobile_app\tool\run-integration.cmd   # levanta el backend H2 si hace falta y corre test_backend/
```

**En el teléfono por USB** (depuración USB activada):

```
adb devices                        # debe listar el teléfono como "device"
adb reverse tcp:9000 tcp:9000      # el 127.0.0.1:9000 del teléfono llega al backend del PC
flutter run -d <id>                # o: flutter test integration_test/cu12_flow_test.dart -d <id>
```

`--dart-define=API_BASE_URL=http://<ip-del-pc>:9000/api` cambia el destino (WiFi, emulador `10.0.2.2`).
Ojo para CU13: con `adb reverse` el teléfono sigue viendo el backend **aunque active el modo avión**
(el túnel va por USB); para probar sin conexión de verdad hay que usar WiFi hacia la IP del PC.

## Contrato y manias del backend generado (medidos contra el backend real, no supuestos)

Tabla completa en [`docs/decisions.md`](docs/decisions.md). Lo que mas pesa:

- **No valida tipos**: `{"precio":"abc"}` -> 200 con `null`; `{}` -> 200 y crea una fila vacia.
- **Ids inexistentes**: `GET`/`PUT` -> **500** (no 404); `DELETE` -> **200** aunque no exista.
- **Relaciones** (`PedidoProducto`): se *escriben* con `pedidoid` / `productoid` y se *leen* como
  `pedido` / `producto` (objeto o id suelto por identidad de Jackson). Otras formas, o un id que no
  existe, se ignoran en silencio (200 con `null`). La coleccion Postman de CU11 usa el contrato correcto.

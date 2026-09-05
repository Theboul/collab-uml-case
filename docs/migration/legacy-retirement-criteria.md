# Criterios y Protocolo de Retiro del Backend Django Legacy

Este documento define las condiciones estrictas y el protocolo formal que deben cumplirse antes de autorizar la desactivación y eliminación definitiva de la carpeta `back_generador_bd` (Django).

---

## 1. Lista de Verificación (Checklist) Mandatoria

Bajo ninguna circunstancia se eliminará `back_generador_bd` si no se han completado y validado positivamente el 100% de los siguientes criterios:

```text
[ ] Criterio 1: Cero referencias de red en el frontend Angular hacia Django
[ ] Criterio 2: Persistencia completa de proyectos y lienzos operativa en FastAPI
[ ] Criterio 3: Orquestación de IA (Gemini) plenamente funcional en FastAPI
[ ] Criterio 4: Colaboración en tiempo real y señalización WebRTC migrada a FastAPI
[ ] Criterio 5: Generador Flutter CRUD independizado e integrado en FastAPI
[ ] Criterio 6: Integración y exportación a Spring Boot verificada de extremo a extremo
[ ] Criterio 7: Pruebas automatizadas de regresión superadas exitosamente
[ ] Criterio 8: Período de gracia (cuarentena de 7 días con Django apagado) sin incidencias
```

---

## 2. Detalle de Validación por Criterio

### Criterio 1: Desacoplamiento Absoluto de Red en Angular
* **Prueba**: Auditoría estática de código (grep) en `front_generador_bd/src/` para verificar que ninguna URL apunte al puerto `8000` ni contenga rutas legadas de Django (`/api/backup/`, `/api/ai/`, `/ws/canvas/`).
* **Condición de Aprobación**: El tráfico de red en el navegador durante una sesión completa de uso (creación, edición colaborativa, IA y exportaciones) no debe registrar ninguna petición dirigida a Django.

### Criterio 2: Persistencia y Gestión de Proyectos
* **Prueba**: Capacidad de crear nuevos proyectos, guardar cambios en el lienzo UML, cerrar el navegador y recargar el proyecto recuperando íntegramente la estructura de clases, atributos, métodos, relaciones y coordenadas visuales de JointJS.
* **Condición de Aprobación**: Todos los datos se leen y escriben exclusivamente desde las tablas gestionadas por SQLAlchemy en PostgreSQL a través de FastAPI.

### Criterio 3: Orquestación de Inteligencia Artificial (Gemini)
* **Prueba**: Ejecución de pruebas de generación automática de diagramas a partir de:
  1. Texto descriptivo simple ("Sistema de biblioteca con libros, autores y préstamos").
  2. Dictado por voz capturado desde el micrófono.
  3. Imagen de boceto de clases dibujado a mano.
* **Condición de Aprobación**: FastAPI procesa las solicitudes, interactúa directamente con el SDK de Gemini, valida la salida contra `contracts/uml-model.v2.json` y entrega el diagrama al canvas sin intervención de Django.

### Criterio 4: Colaboración Multiusuario y Señalización
* **Prueba**: Sesión simultánea con 3 navegadores en un mismo lienzo:
  1. Sincronización instantánea de arrastre de cajas mediante WebRTC DataChannels.
  2. Bloqueo temporal (lock en Redis) cuando un usuario edita los atributos de una clase.
  3. Confirmación de mutaciones estructurales a través de los WebSockets de FastAPI.
* **Condición de Aprobación**: Las salas de colaboración se establecen y gestionan exclusivamente a través del nuevo `ConnectionManager` de FastAPI.

### Criterio 5: Desacoplamiento del Generador Flutter CRUD
* **Prueba**: Extracción de la lógica del generador de código Dart (originalmente en `back_generador_bd/apps/generator/`) y ejecución autónoma como módulo desacoplado dentro de FastAPI.
* **Condición de Aprobación**: La descarga del ZIP del proyecto Flutter compilable se realiza directamente desde FastAPI, sin requerir el runtime de Django ni sus modelos ORM.

### Criterio 6: Exportación a Spring Boot y Postman
* **Prueba**: Disparar la exportación del backend Spring Boot desde la interfaz de Angular.
* **Condición de Aprobación**: FastAPI convierte el modelo UML 2.5 canónico al formato esperado por el generador Spring Boot (`POST http://localhost:7000/generate`), recibe el archivo ZIP generado y lo transfiere al usuario sin errores.

---

## 3. Período de Gracia y Cuarentena Operativa

Una vez completadas todas las fases técnicas:
1. **Apagado en Frío**: Se detendrá el contenedor o proceso de Django durante un período de **7 días calendario**.
2. **Monitoreo de Errores**: Durante este lapso, el equipo continuará probando el sistema en desarrollo/staging.
3. **Rollback Rápido de Emergencia**: Si surgiera un caso de esquina no contemplado que impida operar, bastará con reactivar temporalmente el contenedor de Django y activar el feature flag correspondiente en `environment.ts`.
4. **Visto Bueno Final**: Tras 7 días continuos sin requerir a Django para ninguna operación, se declarará formalmente la obsolescencia total del componente.

---

## 4. Procedimiento de Desmantelamiento y Limpieza

Cumplido el período de gracia:
1. **Archivado Histórico**:
   ```bash
   git tag -a v1.0.0-django-decommissioned -m "Estado previo a la eliminación física del backend Django"
   ```
2. **Eliminación Física**:
   * Eliminar la carpeta `back_generador_bd/` del árbol de archivos.
3. **Limpieza de Infraestructura**:
   * Eliminar definiciones de servicio de Django en `docker-compose.yml`.
   * Eliminar tablas históricas residuales de Django en PostgreSQL mediante un script de limpieza controlado.
4. **Consolidación de Documentación**:
   * Actualizar los diagramas arquitectónicos reflejando a FastAPI como el único backend core del sistema.

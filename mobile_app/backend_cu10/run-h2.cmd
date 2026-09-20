@echo off
rem Levanta el backend Spring Boot generado por CU10 (Pedido / Producto / PedidoProducto)
rem contra H2 EN MEMORIA, en el puerto 9000. Sin dependencias externas: es la forma usada
rem por los tests automatizados. Los datos se pierden al detenerlo.
rem
rem Uso:  mobile_app\backend_cu10\run-h2.cmd        (Ctrl+C para detener)
setlocal
if not defined JAVA_HOME set "JAVA_HOME=C:\Program Files\Java\jdk-21.0.12.1"
set "PATH=%JAVA_HOME%\bin;%PATH%"
set "HERE=%~dp0"
set "SPRING_DATASOURCE_URL=jdbc:h2:mem:cu10;DB_CLOSE_DELAY=-1"
set "SPRING_DATASOURCE_DRIVER_CLASS_NAME=org.h2.Driver"
set "SPRING_DATASOURCE_USERNAME=sa"
set "SPRING_DATASOURCE_PASSWORD=sa"
set "SPRING_JPA_HIBERNATE_DDL_AUTO=create"
set "SPRING_JPA_DATABASE_PLATFORM=org.hibernate.dialect.H2Dialect"
rem Datos semilla (seed.sql) cargados tras crear el esquema:
set "SPRING_SQL_INIT_MODE=always"
set "SPRING_JPA_DEFER_DATASOURCE_INITIALIZATION=true"
set "SPRING_SQL_INIT_DATA_LOCATIONS=file:%HERE%seed.sql"
call "%HERE%..\..\back_generator_uml\mvnw.cmd" -f "%HERE%pom.xml" spring-boot:run

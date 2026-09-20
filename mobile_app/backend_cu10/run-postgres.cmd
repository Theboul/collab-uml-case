@echo off
rem Levanta el mismo backend contra la base PostgreSQL DEDICADA de este proyecto
rem (base y usuario `gestion_movil`, creados con create_dev_db.sql). Puerto 9000.
rem NUNCA usa el usuario `postgres` ni su contrasena.
rem
rem Uso:  mobile_app\backend_cu10\run-postgres.cmd
setlocal
if not defined JAVA_HOME set "JAVA_HOME=C:\Program Files\Java\jdk-21.0.12.1"
set "PATH=%JAVA_HOME%\bin;%PATH%"
set "HERE=%~dp0"
set "SPRING_DATASOURCE_URL=jdbc:postgresql://localhost:5432/gestion_movil"
set "SPRING_DATASOURCE_USERNAME=gestion_movil"
rem Contrasena SOLO de desarrollo local (la misma de create_dev_db.sql); no es un secreto real.
if not defined SPRING_DATASOURCE_PASSWORD set "SPRING_DATASOURCE_PASSWORD=gestion_movil_dev"
set "SPRING_JPA_HIBERNATE_DDL_AUTO=update"
call "%HERE%..\..\back_generator_uml\mvnw.cmd" -f "%HERE%pom.xml" spring-boot:run

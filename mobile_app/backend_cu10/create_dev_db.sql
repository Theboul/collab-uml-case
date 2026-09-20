-- Base y usuario DEDICADOS al proyecto móvil (CU12/CU13). No toca nada de tus otras bases.
-- Ejecutar UNA vez, como superusuario, escribiendo tu contraseña de postgres tú mismo:
--
--   & "C:\Program Files\PostgreSQL\17\bin\psql.exe" -U postgres -h localhost -f mobile_app\backend_cu10\create_dev_db.sql
--
-- (Desde una sesión de Claude Code puedes anteponer `! ` a ese comando.)
-- Para recrearla desde cero:  DROP DATABASE gestion_movil; DROP ROLE gestion_movil;  y volver a ejecutar este archivo.

-- Contraseña solo de desarrollo local; coincide con el valor por defecto de run-postgres.cmd.
CREATE ROLE gestion_movil LOGIN PASSWORD 'gestion_movil_dev' NOSUPERUSER NOCREATEDB NOCREATEROLE;
CREATE DATABASE gestion_movil OWNER gestion_movil ENCODING 'UTF8';

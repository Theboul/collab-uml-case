@echo off
rem Configura, SOLO para esta ventana de cmd, la toolchain instalada en C:\Users\alex\dev
rem (no modifica el PATH ni las variables de usuario/sistema de Windows).
rem
rem Uso:  call mobile_app\tool\dev-env.cmd
rem       flutter doctor
set "JAVA_HOME=C:\Program Files\Java\jdk-21.0.12.1"
set "ANDROID_HOME=C:\Users\alex\dev\android-sdk"
set "ANDROID_SDK_ROOT=%ANDROID_HOME%"
set "FLUTTER_ROOT=C:\Users\alex\dev\flutter"
set "PATH=%FLUTTER_ROOT%\bin;%ANDROID_HOME%\platform-tools;%ANDROID_HOME%\cmdline-tools\latest\bin;%JAVA_HOME%\bin;%PATH%"
rem Sin telemetria ni analisis de uso de Flutter/Dart.
set "FLUTTER_SUPPRESS_ANALYTICS=true"
set "CI_ANALYTICS_DISABLED=1"

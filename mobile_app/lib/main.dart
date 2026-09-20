import 'package:flutter/material.dart';

import 'app.dart';
import 'app_scope.dart';

Future<void> main() async {
  WidgetsFlutterBinding.ensureInitialized();
  // Abre el almacenamiento local, empieza a vigilar la conexión y sincroniza lo pendiente.
  final services = await AppServices.bootstrap();
  runApp(GestionApp(services: services));
}

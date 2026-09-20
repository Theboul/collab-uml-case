import 'package:flutter/material.dart';

import 'app_scope.dart';
import 'ui/home_screen.dart';

/// Raíz de la app de gestión (CU12). [services] permite inyectar otro cliente HTTP en los tests.
class GestionApp extends StatefulWidget {
  const GestionApp({super.key, required this.services});

  final AppServices services;

  @override
  State<GestionApp> createState() => _GestionAppState();
}

class _GestionAppState extends State<GestionApp> {
  @override
  Widget build(BuildContext context) {
    return AppScope(
      services: widget.services,
      child: MaterialApp(
        title: 'Gestión',
        debugShowCheckedModeBanner: false,
        theme: ThemeData(colorSchemeSeed: Colors.indigo, useMaterial3: true),
        home: const HomeScreen(),
      ),
    );
  }
}

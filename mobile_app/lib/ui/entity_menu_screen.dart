import 'package:flutter/material.dart';

import '../domain/entity_module.dart';
import 'record_form_screen.dart';
import 'record_list_screen.dart';
import 'widgets/sync_widgets.dart';

/// Selección de la operación de gestión sobre una entidad: crear, consultar, actualizar, eliminar.
class EntityMenuScreen extends StatelessWidget {
  const EntityMenuScreen({super.key, required this.module});

  final EntityModule module;

  @override
  Widget build(BuildContext context) {
    return Scaffold(
      appBar: AppBar(
        title: Text(module.labelPlural),
        actions: const [SyncActionButton()],
      ),
      body: Column(
        children: [
          const ConnectionBanner(),
          Expanded(
            child: ListView(
              padding: const EdgeInsets.all(12),
              children: [
                _OperationTile(
                  tileKey: const Key('op-crear'),
                  icon: Icons.add_circle_outline,
                  title: 'Crear',
                  subtitle: 'Registrar un nuevo ${module.label}',
                  onTap: () => Navigator.of(context).push(
                    MaterialPageRoute<void>(
                      builder: (_) => RecordFormScreen(module: module),
                    ),
                  ),
                ),
                for (final mode in OperationMode.values)
                  _OperationTile(
                    tileKey: Key('op-${mode.name}'),
                    icon: mode.icon,
                    title: mode.title,
                    subtitle: mode.subtitle(module),
                    onTap: () => Navigator.of(context).push(
                      MaterialPageRoute<void>(
                        builder: (_) =>
                            RecordListScreen(module: module, mode: mode),
                      ),
                    ),
                  ),
              ],
            ),
          ),
        ],
      ),
    );
  }
}

class _OperationTile extends StatelessWidget {
  const _OperationTile({
    required this.tileKey,
    required this.icon,
    required this.title,
    required this.subtitle,
    required this.onTap,
  });

  final Key tileKey;
  final IconData icon;
  final String title;
  final String subtitle;
  final VoidCallback onTap;

  @override
  Widget build(BuildContext context) {
    return Card(
      child: ListTile(
        key: tileKey,
        leading: Icon(icon),
        title: Text(title),
        subtitle: Text(subtitle),
        trailing: const Icon(Icons.chevron_right),
        onTap: onTap,
      ),
    );
  }
}

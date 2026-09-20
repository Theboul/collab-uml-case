import 'package:flutter/material.dart';

import '../../app_scope.dart';
import '../../data/sync/sync_controller.dart';
import '../sync_screen.dart';

/// Franja superior con el estado de la conexión y de la cola de sincronización.
///
/// Se oculta cuando hay conexión y no queda nada pendiente. Al tocarla abre la pantalla de
/// Sincronización.
class ConnectionBanner extends StatelessWidget {
  const ConnectionBanner({super.key});

  @override
  Widget build(BuildContext context) {
    final sync = AppScope.of(context).sync;
    return ListenableBuilder(
      listenable: sync,
      builder: (context, _) {
        final scheme = Theme.of(context).colorScheme;
        final pending = sync.pendingCount;
        final attention = sync.attentionCount;

        late final Key key;
        late final IconData icon;
        late final String text;
        late final Color background;
        if (!sync.online) {
          key = const Key('banner-offline');
          icon = Icons.cloud_off;
          text = pending + attention > 0
              ? 'Sin conexión · $pending pendiente(s) de sincronizar'
              : 'Sin conexión · trabajando con los datos guardados';
          background = scheme.tertiaryContainer;
        } else if (sync.syncing) {
          key = const Key('banner-syncing');
          icon = Icons.sync;
          text = 'Sincronizando…';
          background = scheme.secondaryContainer;
        } else if (pending + attention > 0) {
          key = const Key('banner-pending');
          icon = attention > 0 ? Icons.warning_amber : Icons.cloud_upload;
          text = attention > 0
              ? '$attention operación(es) requieren tu atención · $pending pendiente(s)'
              : '$pending pendiente(s) de sincronizar';
          background = attention > 0
              ? scheme.errorContainer
              : scheme.secondaryContainer;
        } else {
          return const SizedBox.shrink(key: Key('banner-hidden'));
        }

        return Material(
          color: background,
          child: InkWell(
            key: key,
            onTap: () => openSyncScreen(context),
            child: Padding(
              padding: const EdgeInsets.symmetric(horizontal: 16, vertical: 10),
              child: Row(
                children: [
                  Icon(icon, size: 18),
                  const SizedBox(width: 10),
                  Expanded(child: Text(text)),
                  const Icon(Icons.chevron_right, size: 18),
                ],
              ),
            ),
          ),
        );
      },
    );
  }
}

/// Icono de la barra con el contador de operaciones pendientes / por revisar.
class SyncActionButton extends StatelessWidget {
  const SyncActionButton({super.key});

  @override
  Widget build(BuildContext context) {
    final sync = AppScope.of(context).sync;
    return ListenableBuilder(
      listenable: sync,
      builder: (context, _) {
        final count = sync.pendingCount + sync.attentionCount;
        return IconButton(
          key: const Key('open-sync'),
          tooltip: 'Sincronización',
          onPressed: () => openSyncScreen(context),
          icon: Badge(
            isLabelVisible: count > 0,
            label: Text('$count'),
            child: Icon(
              sync.online ? Icons.cloud_done_outlined : Icons.cloud_off,
            ),
          ),
        );
      },
    );
  }
}

/// Recarga los datos de una pantalla cada vez que termina una sincronización.
mixin SyncRefreshMixin<T extends StatefulWidget> on State<T> {
  SyncController? _syncController;
  int _seenRevision = -1;

  /// Llamado cuando terminó una sincronización: la pantalla debe recargar sus datos.
  void onSyncCompleted();

  /// Llamar desde `didChangeDependencies`.
  void watchSync() {
    final controller = AppScope.of(context).sync;
    if (identical(controller, _syncController)) return;
    _syncController?.removeListener(_onChange);
    _syncController = controller;
    _seenRevision = controller.revision;
    controller.addListener(_onChange);
  }

  void _onChange() {
    if (!mounted) return;
    final revision = _syncController!.revision;
    if (revision != _seenRevision) {
      _seenRevision = revision;
      onSyncCompleted();
    }
  }

  @override
  void dispose() {
    _syncController?.removeListener(_onChange);
    super.dispose();
  }
}

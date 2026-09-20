import 'dart:async';

import 'package:flutter/material.dart';

import '../app_scope.dart';
import '../domain/entity_module.dart';
import '../domain/entity_values.dart';
import '../domain/pending_op.dart';
import 'widgets/sync_widgets.dart';

void openSyncScreen(BuildContext context) {
  Navigator.of(context)
      .push(MaterialPageRoute<void>(builder: (_) => const SyncScreen()));
}

/// Cola de sincronización: qué está pendiente, qué se sincronizó y qué fue rechazado (con motivo).
/// Desde aquí se decide sobre lo rechazado: descartar, aplicar igualmente o crear como nuevo.
class SyncScreen extends StatefulWidget {
  const SyncScreen({super.key});

  @override
  State<SyncScreen> createState() => _SyncScreenState();
}

class _SyncScreenState extends State<SyncScreen> {
  Future<List<PendingOp>>? _ops;
  StreamSubscription<void>? _sub;

  @override
  void didChangeDependencies() {
    super.didChangeDependencies();
    final services = AppScope.of(context);
    _ops ??= services.store.allOps();
    _sub ??= services.store.changes.listen((_) {
      if (mounted) {
        setState(() {
          _ops = services.store.allOps();
        });
      }
    });
  }

  @override
  void dispose() {
    unawaited(_sub?.cancel());
    super.dispose();
  }

  @override
  Widget build(BuildContext context) {
    final services = AppScope.of(context);
    return Scaffold(
      appBar: AppBar(
        title: const Text('Sincronización'),
        actions: [
          ListenableBuilder(
            listenable: services.sync,
            builder: (context, _) => IconButton(
              key: const Key('sync-now'),
              tooltip: 'Sincronizar ahora',
              onPressed: services.sync.syncing
                  ? null
                  : () => unawaited(services.sync.syncNow()),
              icon: const Icon(Icons.sync),
            ),
          ),
        ],
      ),
      body: Column(
        children: [
          const ConnectionBanner(),
          Expanded(
            child: FutureBuilder<List<PendingOp>>(
              future: _ops,
              builder: (context, snapshot) {
                if (!snapshot.hasData) {
                  return const Center(child: CircularProgressIndicator());
                }
                final ops = snapshot.data!.reversed.toList();
                if (ops.isEmpty) {
                  return const Center(
                    child: Text(
                      'No hay operaciones pendientes.',
                      key: Key('sync-empty'),
                    ),
                  );
                }
                return ListView.builder(
                  padding: const EdgeInsets.all(12),
                  itemCount: ops.length,
                  itemBuilder: (context, index) => _OpCard(op: ops[index]),
                );
              },
            ),
          ),
        ],
      ),
    );
  }
}

class _OpCard extends StatelessWidget {
  const _OpCard({required this.op});

  final PendingOp op;

  static const _kinds = {
    OpKind.create: 'Crear',
    OpKind.update: 'Actualizar',
    OpKind.delete: 'Eliminar',
  };

  @override
  Widget build(BuildContext context) {
    final module = moduleByPath(op.module);
    final scheme = Theme.of(context).colorScheme;
    final (label, color) = switch (op.status) {
      OpStatus.pending => ('Pendiente', scheme.secondaryContainer),
      OpStatus.sending => ('Enviando', scheme.secondaryContainer),
      OpStatus.uncertain => ('Por verificar', scheme.tertiaryContainer),
      OpStatus.needsReview => ('Requiere revisión', scheme.errorContainer),
      OpStatus.synced => ('Sincronizada', scheme.primaryContainer),
      OpStatus.rejected => ('Rechazada', scheme.errorContainer),
      OpStatus.failed => ('Falló', scheme.errorContainer),
    };
    final id = op.targetId < 0 ? '(nuevo)' : '${op.targetId}';

    return Card(
      key: Key('op-${op.opId}'),
      child: Padding(
        padding: const EdgeInsets.all(12),
        child: Column(
          crossAxisAlignment: CrossAxisAlignment.start,
          children: [
            Row(
              children: [
                Expanded(
                  child: Text(
                    '${_kinds[op.kind]} ${module.label} $id',
                    style: Theme.of(context).textTheme.titleSmall,
                  ),
                ),
                Chip(
                  key: Key('status-${op.status.name}'),
                  label: Text(label),
                  backgroundColor: color,
                  visualDensity: VisualDensity.compact,
                ),
              ],
            ),
            Text(EntityValues.describe(module, op.values)),
            if (op.detail != null) ...[
              const SizedBox(height: 6),
              Text(
                op.detail!,
                key: const Key('op-detail'),
                style: TextStyle(color: scheme.error),
              ),
            ],
            _Actions(op: op),
          ],
        ),
      ),
    );
  }
}

class _Actions extends StatelessWidget {
  const _Actions({required this.op});

  final PendingOp op;

  @override
  Widget build(BuildContext context) {
    final services = AppScope.of(context);
    final engine = services.engine;

    Widget button(
      String key,
      String text,
      Future<void> Function() action, {
      bool primary = false,
    }) {
      Future<void> run() async {
        await action();
        unawaited(services.sync.syncNow());
      }

      return primary
          ? FilledButton(key: Key(key), onPressed: run, child: Text(text))
          : TextButton(key: Key(key), onPressed: run, child: Text(text));
    }

    final buttons = <Widget>[
      switch ((op.status, op.reason, op.kind)) {
        (OpStatus.rejected, OpReason.deletedRemotely, OpKind.update) => button(
          'act-create-as-new',
          'Crear como nuevo',
          () => engine.createAsNew(op.opId),
          primary: true,
        ),
        (OpStatus.rejected, OpReason.modifiedRemotely, _) => button(
          'act-apply-anyway',
          op.kind == OpKind.delete
              ? 'Eliminar igualmente'
              : 'Aplicar igualmente',
          () => engine.applyAnyway(op.opId),
          primary: true,
        ),
        (OpStatus.failed, _, _) => button(
          'act-retry',
          'Reintentar',
          () => engine.retry(op.opId),
          primary: true,
        ),
        (OpStatus.needsReview, _, _) => button(
          'act-resend',
          'Reenviar igualmente',
          () => engine.resendAnyway(op.opId),
          primary: true,
        ),
        _ => const SizedBox.shrink(),
      },
      if (op.needsAttention || op.status == OpStatus.synced)
        button(
          'act-discard',
          op.status == OpStatus.synced ? 'Quitar' : 'Descartar',
          () => engine.discard(op.opId),
        ),
    ];

    if (buttons.every((w) => w is SizedBox)) return const SizedBox.shrink();
    return Padding(
      padding: const EdgeInsets.only(top: 6),
      child: Wrap(spacing: 8, children: buttons),
    );
  }
}

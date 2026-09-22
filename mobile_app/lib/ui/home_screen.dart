import 'dart:async';

import 'package:flutter/material.dart';

import '../app_scope.dart';
import '../data/failures.dart';
import '../domain/entity_module.dart';
import 'entity_menu_screen.dart';
import 'voice/voice_assistant_screen.dart';
import 'widgets/sync_widgets.dart';

/// Resultado de cargar una entidad al iniciar la app.
class _ModuleSummary {
  const _ModuleSummary(
    this.module, {
    this.count,
    this.fromCache = false,
    this.pending = 0,
    this.failure,
  });

  final EntityModule module;
  final int? count;

  /// Los datos vienen de este dispositivo (sin conexión), no del servidor.
  final bool fromCache;

  /// Registros con cambios pendientes de sincronizar.
  final int pending;
  final Object? failure;
}

/// Pantalla de inicio: carga desde el backend real el listado de cada entidad del modelo.
class HomeScreen extends StatefulWidget {
  const HomeScreen({super.key});

  @override
  State<HomeScreen> createState() => _HomeScreenState();
}

class _HomeScreenState extends State<HomeScreen>
    with SyncRefreshMixin<HomeScreen> {
  Future<List<_ModuleSummary>>? _summaries;

  @override
  void didChangeDependencies() {
    super.didChangeDependencies();
    watchSync();
    _summaries ??= _load();
  }

  @override
  void onSyncCompleted() {
    unawaited(_refresh());
  }

  Future<List<_ModuleSummary>> _load() {
    final services = AppScope.of(context);
    return Future.wait([
      for (final module in allModules)
        () async {
          try {
            final result = await services.repositoryFor(module).list();
            return _ModuleSummary(
              module,
              count: result.items.length,
              fromCache: result.fromCache,
              pending: result.pendingIds.length,
            );
          } on AppFailure catch (failure) {
            return _ModuleSummary(module, failure: failure);
          }
        }(),
    ]);
  }

  Future<void> _refresh() async {
    final next = _load();
    setState(() {
      _summaries = next;
    });
    await next;
  }

  @override
  Widget build(BuildContext context) {
    return Scaffold(
      appBar: AppBar(
        title: const Text('Gestión'),
        actions: [
          const SyncActionButton(),
          IconButton(
            key: const Key('open-voice'),
            tooltip: 'Asistente de voz',
            icon: const Icon(Icons.mic_none),
            onPressed: () async {
              await Navigator.of(context).push(
                MaterialPageRoute<void>(
                  builder: (_) => const VoiceAssistantScreen(),
                ),
              );
              await _refresh();
            },
          ),
          IconButton(
            key: const Key('refresh'),
            tooltip: 'Recargar',
            icon: const Icon(Icons.refresh),
            onPressed: _refresh,
          ),
        ],
      ),
      body: Column(
        children: [
          const ConnectionBanner(),
          Expanded(
            child: FutureBuilder<List<_ModuleSummary>>(
              future: _summaries,
              builder: (context, snapshot) {
                if (snapshot.connectionState != ConnectionState.done) {
                  return const Center(child: CircularProgressIndicator());
                }
                final summaries = snapshot.data ?? const <_ModuleSummary>[];
                return RefreshIndicator(
                  onRefresh: _refresh,
                  child: ListView(
                    physics: const AlwaysScrollableScrollPhysics(),
                    padding: const EdgeInsets.all(12),
                    children: [
                      const Padding(
                        padding: EdgeInsets.fromLTRB(4, 4, 4, 12),
                        child: Text(
                          'Elige una entidad para gestionar sus registros.',
                        ),
                      ),
                      for (final summary in summaries)
                        _ModuleCard(summary: summary, onBack: _refresh),
                    ],
                  ),
                );
              },
            ),
          ),
        ],
      ),
    );
  }
}

class _ModuleCard extends StatelessWidget {
  const _ModuleCard({required this.summary, required this.onBack});

  final _ModuleSummary summary;
  final Future<void> Function() onBack;

  @override
  Widget build(BuildContext context) {
    final module = summary.module;
    final failure = summary.failure;
    final subtitle = failure != null
        ? (failure is AppFailure ? failure.userMessage : '$failure')
        : '${summary.count} registro(s)'
              '${summary.fromCache ? ' · datos locales' : ''}'
              '${summary.pending > 0 ? ' · ${summary.pending} pendiente(s)' : ''}';
    return Card(
      child: ListTile(
        key: Key('module-${module.path}'),
        leading: Icon(failure != null ? Icons.error_outline : Icons.table_rows),
        title: Text(module.labelPlural),
        subtitle: Text(subtitle, key: Key('module-${module.path}-subtitle')),
        trailing: const Icon(Icons.chevron_right),
        onTap: () async {
          await Navigator.of(context).push(
            MaterialPageRoute<void>(
              builder: (_) => EntityMenuScreen(module: module),
            ),
          );
          await onBack();
        },
      ),
    );
  }
}

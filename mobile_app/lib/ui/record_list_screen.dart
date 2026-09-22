import 'dart:async';

import 'package:flutter/material.dart';

import '../app_scope.dart';
import '../data/entity_gateway.dart';
import '../data/failures.dart';
import '../domain/entity_module.dart';
import '../domain/field_spec.dart';
import '../domain/validators.dart';
import '../models/entity.dart';
import 'record_detail_screen.dart';
import 'record_form_screen.dart';
import 'widgets/feedback.dart';
import 'widgets/sync_widgets.dart';

/// Operaciones que se eligen sobre un registro existente (crear tiene su propio flujo).
enum OperationMode {
  consultar(Icons.search, 'Consultar'),
  actualizar(Icons.edit_outlined, 'Actualizar'),
  eliminar(Icons.delete_outline, 'Eliminar');

  const OperationMode(this.icon, this.title);

  final IconData icon;
  final String title;

  String subtitle(EntityModule module) => switch (this) {
    OperationMode.consultar =>
      'Ver ${module.labelPlural.toLowerCase()} o buscar uno por ID',
    OperationMode.actualizar => 'Modificar un ${module.label} existente',
    OperationMode.eliminar => 'Borrar un ${module.label} existente',
  };
}

/// Listado de una entidad para consultar, actualizar o eliminar un registro (según [mode]),
/// con búsqueda directa por ID.
class RecordListScreen extends StatefulWidget {
  const RecordListScreen({super.key, required this.module, required this.mode});

  final EntityModule module;
  final OperationMode mode;

  @override
  State<RecordListScreen> createState() => _RecordListScreenState();
}

class _RecordListScreenState extends State<RecordListScreen>
    with SyncRefreshMixin<RecordListScreen> {
  static const FieldSpec _idField = FieldSpec(
    name: 'id',
    label: 'El ID',
    type: FieldType.integer,
  );

  final _idController = TextEditingController();
  final _idFocus = FocusNode();
  Future<ListResult>? _future;
  String? _idError;
  bool _busy = false;

  @override
  void didChangeDependencies() {
    super.didChangeDependencies();
    watchSync();
    _future ??= _load();
  }

  @override
  void onSyncCompleted() => _reload();

  @override
  void dispose() {
    _idController.dispose();
    _idFocus.dispose();
    super.dispose();
  }

  Future<ListResult> _load() =>
      AppScope.of(context).repositoryFor(widget.module).list();

  void _reload() => setState(() {
    _future = _load();
  });

  Future<void> _searchById() async {
    final error = FieldValidator.validate(_idField, _idController.text);
    setState(() => _idError = error);
    if (error != null) return;
    _idFocus.unfocus();
    await _onSelected(
      FieldValidator.parse(_idField, _idController.text) as int,
    );
  }

  /// Ejecuta la operación elegida sobre el registro [id]. Ante cualquier fallo informa y no
  /// modifica nada: los datos guardados quedan como estaban.
  Future<void> _onSelected(int id) async {
    if (_busy) return;
    setState(() => _busy = true);
    final repository = AppScope.of(context).repositoryFor(widget.module);
    final module = widget.module;
    try {
      switch (widget.mode) {
        case OperationMode.consultar:
          await Navigator.of(context).push(
            MaterialPageRoute<void>(
              builder: (_) => RecordDetailScreen(module: module, id: id),
            ),
          );
        case OperationMode.actualizar:
          final current = await repository.getById(
            id,
          ); // consulta real: valida que exista
          if (!mounted) return;
          await Navigator.of(context).push(
            MaterialPageRoute<void>(
              builder: (_) =>
                  RecordFormScreen(module: module, existing: current),
            ),
          );
        case OperationMode.eliminar:
          final current = await repository.getById(id);
          if (!mounted) return;
          setState(
            () => _busy = false,
          ); // esperando al usuario: no hay nada en curso
          final confirmed = await _confirmDelete(current);
          if (confirmed != true || !mounted) return;
          setState(() => _busy = true);
          final outcome = await repository.delete(id);
          if (!mounted) return;
          showResult(context, outcome.deletedText(module, id));
      }
      if (mounted) _reload();
    } on AppFailure catch (failure) {
      if (!mounted) return;
      showResult(context, failure.userMessage, error: true);
      _reload(); // refleja el estado real (p. ej. el registro ya no existe)
    } finally {
      if (mounted) setState(() => _busy = false);
    }
  }

  Future<bool?> _confirmDelete(Entity entity) {
    final module = widget.module;
    return showDialog<bool>(
      context: context,
      builder: (context) => AlertDialog(
        title: Text('Eliminar ${module.label} ${entity.id}'),
        content: Text(
          '${module.title(entity)}\n${module.subtitle(entity)}\n\n'
          'Esta acción no se puede deshacer y elimina también sus relaciones.',
        ),
        actions: [
          TextButton(
            key: const Key('cancel-delete'),
            onPressed: () => Navigator.pop(context, false),
            child: const Text('Cancelar'),
          ),
          FilledButton(
            key: const Key('confirm-delete'),
            onPressed: () => Navigator.pop(context, true),
            child: const Text('Eliminar'),
          ),
        ],
      ),
    );
  }

  @override
  Widget build(BuildContext context) {
    final module = widget.module;
    return Scaffold(
      appBar: AppBar(
        title: Text('${widget.mode.title} · ${module.labelPlural}'),
        actions: const [SyncActionButton()],
      ),
      body: Column(
        children: [
          const ConnectionBanner(),
          Padding(
            padding: const EdgeInsets.fromLTRB(12, 12, 12, 4),
            child: Row(
              crossAxisAlignment: CrossAxisAlignment.start,
              children: [
                Expanded(
                  child: TextField(
                    key: const Key('search-id'),
                    controller: _idController,
                    focusNode: _idFocus,
                    keyboardType: TextInputType.number,
                    textInputAction: TextInputAction.search,
                    onSubmitted: (_) => _searchById(),
                    decoration: InputDecoration(
                      labelText: 'Buscar por ID',
                      border: const OutlineInputBorder(),
                      errorText: _idError,
                    ),
                  ),
                ),
                const SizedBox(width: 8),
                Padding(
                  padding: const EdgeInsets.only(top: 6),
                  child: FilledButton(
                    key: const Key('search-by-id'),
                    onPressed: _busy ? null : _searchById,
                    child: Text(widget.mode.title),
                  ),
                ),
              ],
            ),
          ),
          if (_busy) const LinearProgressIndicator(),
          Expanded(
            child: FutureBuilder<ListResult>(
              future: _future,
              builder: (context, snapshot) {
                if (snapshot.connectionState != ConnectionState.done) {
                  return const Center(child: CircularProgressIndicator());
                }
                if (snapshot.hasError) {
                  return ErrorMessage(
                    failure: snapshot.error!,
                    onRetry: _reload,
                  );
                }
                final result = snapshot.data!;
                final items = result.items;
                if (items.isEmpty) {
                  return const Center(
                    child: Text('No hay registros.', key: Key('empty')),
                  );
                }
                return RefreshIndicator(
                  onRefresh: () async => _reload(),
                  child: ListView.builder(
                    physics: const AlwaysScrollableScrollPhysics(),
                    itemCount: items.length,
                    itemBuilder: (context, index) {
                      final item = items[index];
                      return ListTile(
                        key: Key('item-${item.id}'),
                        title: Text(module.title(item)),
                        subtitle: Text(module.subtitle(item)),
                        trailing: result.pendingIds.contains(item.id)
                            ? Chip(
                                key: Key('pending-${item.id}'),
                                label: const Text('Pendiente'),
                                visualDensity: VisualDensity.compact,
                              )
                            : Icon(widget.mode.icon),
                        onTap: item.id == null
                            ? null
                            : () => _onSelected(item.id!),
                      );
                    },
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

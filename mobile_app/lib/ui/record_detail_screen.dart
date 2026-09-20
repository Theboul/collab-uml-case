import 'package:flutter/material.dart';

import '../app_scope.dart';
import '../domain/entity_module.dart';
import '../models/entity.dart';
import 'widgets/feedback.dart';

/// Consulta de un registro por id: siempre pide el dato fresco al backend (no reutiliza el listado).
class RecordDetailScreen extends StatefulWidget {
  const RecordDetailScreen({super.key, required this.module, required this.id});

  final EntityModule module;
  final int id;

  @override
  State<RecordDetailScreen> createState() => _RecordDetailScreenState();
}

class _RecordDetailScreenState extends State<RecordDetailScreen> {
  Future<Entity>? _future;

  @override
  void didChangeDependencies() {
    super.didChangeDependencies();
    _future ??= _load();
  }

  Future<Entity> _load() =>
      AppScope.of(context).repositoryFor(widget.module).getById(widget.id);

  @override
  Widget build(BuildContext context) {
    final module = widget.module;
    return Scaffold(
      appBar: AppBar(title: Text('${module.label} ${widget.id}')),
      body: FutureBuilder<Entity>(
        future: _future,
        builder: (context, snapshot) {
          if (snapshot.connectionState != ConnectionState.done) {
            return const Center(child: CircularProgressIndicator());
          }
          if (snapshot.hasError) {
            return ErrorMessage(
              failure: snapshot.error!,
              onRetry: () => setState(() {
                _future = _load();
              }),
            );
          }
          final entity = snapshot.data!;
          final values = module.valuesOf(entity);
          return ListView(
            padding: const EdgeInsets.all(16),
            children: [
              _Row(label: 'ID', value: '${entity.id}'),
              for (final field in module.fields)
                _Row(label: field.label, value: '${values[field.name] ?? '—'}'),
            ],
          );
        },
      ),
    );
  }
}

class _Row extends StatelessWidget {
  const _Row({required this.label, required this.value});

  final String label;
  final String value;

  @override
  Widget build(BuildContext context) {
    return Padding(
      padding: const EdgeInsets.symmetric(vertical: 8),
      child: Row(
        crossAxisAlignment: CrossAxisAlignment.start,
        children: [
          SizedBox(
            width: 110,
            child: Text(label, style: Theme.of(context).textTheme.labelLarge),
          ),
          Expanded(child: Text(value, key: Key('detail-$label'))),
        ],
      ),
    );
  }
}

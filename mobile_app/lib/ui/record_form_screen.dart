import 'package:flutter/material.dart';

import '../app_scope.dart';
import '../data/entity_gateway.dart';
import '../data/failures.dart';
import '../domain/entity_module.dart';
import '../domain/field_spec.dart';
import '../domain/validators.dart';
import '../models/entity.dart';
import 'widgets/feedback.dart';

/// Formulario para crear ([existing] == null) o actualizar un registro.
///
/// La validación por tipo corre **antes** de enviar: si algún campo es inválido no se hace ninguna
/// petición. Si el servidor falla, el formulario conserva lo escrito y muestra el motivo; los datos
/// ya guardados no se tocan.
class RecordFormScreen extends StatefulWidget {
  const RecordFormScreen({super.key, required this.module, this.existing});

  final EntityModule module;
  final Entity? existing;

  @override
  State<RecordFormScreen> createState() => _RecordFormScreenState();
}

class _RecordFormScreenState extends State<RecordFormScreen> {
  final _formKey = GlobalKey<FormState>();
  final Map<String, TextEditingController> _controllers = {};
  final Map<String, int?> _references = {};
  Future<Map<String, List<Entity>>>? _options;
  bool _saving = false;
  String? _serverError;

  bool get _isEdit => widget.existing != null;

  @override
  void initState() {
    super.initState();
    final current = widget.existing == null
        ? null
        : widget.module.valuesOf(widget.existing!);
    for (final field in widget.module.fields) {
      final value = current?[field.name];
      if (field.type == FieldType.reference) {
        _references[field.name] = value as int?;
      } else {
        _controllers[field.name] = TextEditingController(
          text: value == null ? '' : '$value',
        );
      }
    }
  }

  @override
  void didChangeDependencies() {
    super.didChangeDependencies();
    _options ??= _loadReferenceOptions();
  }

  @override
  void dispose() {
    for (final controller in _controllers.values) {
      controller.dispose();
    }
    super.dispose();
  }

  /// Carga (del backend real) las entidades que pueden referenciarse desde este formulario.
  Future<Map<String, List<Entity>>> _loadReferenceOptions() async {
    final services = AppScope.of(context);
    final result = <String, List<Entity>>{};
    for (final field in widget.module.fields) {
      if (field.type != FieldType.reference) continue;
      final target = moduleByPath(field.referenceTo!);
      result[field.name] = (await services.repositoryFor(target).list()).items;
    }
    return result;
  }

  Future<void> _submit() async {
    setState(() => _serverError = null);
    if (!_formKey.currentState!.validate()) {
      return; // inválido: no se envía nada
    }

    final module = widget.module;
    final values = <String, Object?>{
      for (final field in module.fields)
        field.name: field.type == FieldType.reference
            ? _references[field.name]
            : FieldValidator.parse(field, _controllers[field.name]!.text),
    };
    final repository = AppScope.of(context).repositoryFor(module);

    setState(() => _saving = true);
    try {
      final id = widget.existing?.id;
      final outcome = id == null
          ? await repository.create(module.fromValues(null, values))
          : await repository.update(id, module.fromValues(id, values));
      if (!mounted) return;
      showResult(
        context,
        _isEdit ? outcome.updatedText(module) : outcome.createdText(module),
      );
      Navigator.of(context).pop(outcome.entity);
    } on AppFailure catch (failure) {
      if (!mounted) return;
      // El formulario conserva lo escrito; solo se informa el motivo.
      setState(() {
        _serverError = failure.userMessage;
        _saving = false;
      });
    }
  }

  @override
  Widget build(BuildContext context) {
    final module = widget.module;
    return Scaffold(
      appBar: AppBar(
        title: Text(
          _isEdit
              ? 'Actualizar ${module.label} ${widget.existing!.id}'
              : 'Crear ${module.label}',
        ),
      ),
      body: FutureBuilder<Map<String, List<Entity>>>(
        future: _options,
        builder: (context, snapshot) {
          if (snapshot.connectionState != ConnectionState.done) {
            return const Center(child: CircularProgressIndicator());
          }
          if (snapshot.hasError) {
            return ErrorMessage(
              failure: snapshot.error!,
              onRetry: () => setState(() {
                _options = _loadReferenceOptions();
              }),
            );
          }
          final options = snapshot.data ?? const <String, List<Entity>>{};
          return Form(
            key: _formKey,
            child: ListView(
              padding: const EdgeInsets.all(16),
              children: [
                if (_serverError != null)
                  Card(
                    color: Theme.of(context).colorScheme.errorContainer,
                    child: Padding(
                      padding: const EdgeInsets.all(12),
                      child: Text(_serverError!, key: const Key('form-error')),
                    ),
                  ),
                for (final field in module.fields) ...[
                  _buildField(field, options),
                  const SizedBox(height: 16),
                ],
                FilledButton(
                  key: const Key('submit'),
                  onPressed: _saving ? null : _submit,
                  child: _saving
                      ? const SizedBox(
                          width: 20,
                          height: 20,
                          child: CircularProgressIndicator(strokeWidth: 2),
                        )
                      : Text(_isEdit ? 'Actualizar' : 'Crear'),
                ),
              ],
            ),
          );
        },
      ),
    );
  }

  Widget _buildField(FieldSpec field, Map<String, List<Entity>> options) {
    if (field.type == FieldType.reference) {
      final target = moduleByPath(field.referenceTo!);
      final items = options[field.name] ?? const <Entity>[];
      return DropdownButtonFormField<int>(
        key: Key('field-${field.name}'),
        initialValue: items.any((e) => e.id == _references[field.name])
            ? _references[field.name]
            : null,
        decoration: InputDecoration(
          labelText: field.label,
          border: const OutlineInputBorder(),
        ),
        items: [
          for (final item in items)
            DropdownMenuItem<int>(
              value: item.id,
              child: Text('${target.title(item)} · ${target.subtitle(item)}'),
            ),
        ],
        onChanged: (value) => setState(() => _references[field.name] = value),
        validator: (value) => FieldValidator.validate(field, value?.toString()),
      );
    }
    final numeric = field.type != FieldType.text;
    return TextFormField(
      key: Key('field-${field.name}'),
      controller: _controllers[field.name],
      keyboardType: numeric
          ? const TextInputType.numberWithOptions(decimal: true, signed: true)
          : TextInputType.text,
      autovalidateMode: AutovalidateMode.onUserInteraction,
      decoration: InputDecoration(
        labelText: field.label,
        border: const OutlineInputBorder(),
      ),
      validator: (value) => FieldValidator.validate(field, value),
    );
  }
}

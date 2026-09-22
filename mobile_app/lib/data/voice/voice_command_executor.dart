import '../../domain/entity_module.dart';
import '../../domain/field_spec.dart';
import '../../domain/validators.dart';
import '../../domain/voice/voice_command.dart';
import '../../models/entity.dart';
import '../entity_gateway.dart';
import '../failures.dart';

/// Qué pasó al ejecutar un [VoiceCommand].
sealed class VoiceExecution {
  const VoiceExecution();
}

/// Se ejecutó. [outcome] es lo que devolvió el repositorio en una escritura (puede estar
/// pendiente de sincronizar); [items] son los registros de una consulta.
final class VoiceExecuted extends VoiceExecution {
  const VoiceExecuted(this.message, {this.outcome, this.items = const []});

  final String message;
  final WriteOutcome? outcome;
  final List<Entity> items;
}

/// Un slot no supera la validación de la app: no se escribió nada. Es `datosFaltantes`.
final class VoiceRejected extends VoiceExecution {
  const VoiceRejected(this.failure);

  final VoiceFailure failure;
}

/// El repositorio falló (no existe el registro, servidor, conflicto…): el mismo [AppFailure] que
/// vería el usuario en las pantallas manuales.
final class VoiceExecutionError extends VoiceExecution {
  const VoiceExecutionError(this.failure);

  final AppFailure failure;
}

/// Traduce un [VoiceCommand] a las MISMAS llamadas que hacen las pantallas manuales de CU12 contra
/// el repositorio offline-first ([EntityGateway]): `create`, `getById` + `update`, `getById` +
/// `delete`, `list` y `getById`. No hay ningún método nuevo de repositorio ni otra validación:
/// los slots pasan por `FieldValidator`, igual que el formulario.
class VoiceCommandExecutor {
  const VoiceCommandExecutor({required this.gatewayFor});

  final EntityGateway Function(EntityModule module) gatewayFor;

  /// Comprueba los slots con `FieldValidator` ANTES de ejecutar (y de pedir confirmación).
  /// `null` = son válidos; si no, es un `datosFaltantes` con lo que no valida y por qué.
  VoiceFailure? validate(VoiceCommand command) {
    final module = command.module;
    final fields = switch (command.intent) {
      VoiceIntent.crear => module.fields,
      VoiceIntent.actualizar => [
        for (final f in module.fields)
          if (command.values.containsKey(f.name)) f,
      ],
      _ => const <FieldSpec>[],
    };
    final invalid = _invalidFields(fields, command.values);
    return invalid.isEmpty ? null : _rejected(command, invalid);
  }

  Future<VoiceExecution> execute(VoiceCommand command) async {
    final invalid = validate(command);
    if (invalid != null) return VoiceRejected(invalid);
    final module = command.module;
    final gateway = gatewayFor(module);
    try {
      return switch (command.intent) {
        VoiceIntent.crear => await _create(command, module, gateway),
        VoiceIntent.actualizar => await _update(command, module, gateway),
        VoiceIntent.eliminar => await _delete(command, module, gateway),
        VoiceIntent.consultar => await _query(command, module, gateway),
      };
    } on AppFailure catch (failure) {
      return VoiceExecutionError(failure);
    }
  }

  Future<VoiceExecution> _create(
    VoiceCommand command,
    EntityModule module,
    EntityGateway gateway,
  ) async {
    final values = _typed(module.fields, command.values);
    final outcome = await gateway.create(module.fromValues(null, values));
    return VoiceExecuted(outcome.createdText(module), outcome: outcome);
  }

  Future<VoiceExecution> _update(
    VoiceCommand command,
    EntityModule module,
    EntityGateway gateway,
  ) async {
    final id = command.id!;
    final fields = [
      for (final f in module.fields)
        if (command.values.containsKey(f.name)) f,
    ];
    // Como la pantalla manual: se parte del registro actual (consulta real) y se cambia el campo.
    final current = await gateway.getById(id);
    final values = {
      ...module.valuesOf(current),
      ..._typed(fields, command.values),
    };
    final outcome = await gateway.update(id, module.fromValues(id, values));
    return VoiceExecuted(outcome.updatedText(module), outcome: outcome);
  }

  Future<VoiceExecution> _delete(
    VoiceCommand command,
    EntityModule module,
    EntityGateway gateway,
  ) async {
    final id = command.id!;
    await gateway.getById(
      id,
    ); // la pantalla manual comprueba que exista antes de confirmar
    final outcome = await gateway.delete(id);
    return VoiceExecuted(outcome.deletedText(module, id), outcome: outcome);
  }

  Future<VoiceExecution> _query(
    VoiceCommand command,
    EntityModule module,
    EntityGateway gateway,
  ) async {
    final id = command.id;
    if (id != null) {
      final entity = await gateway.getById(id);
      return VoiceExecuted(
        '${module.title(entity)} · ${module.subtitle(entity)}',
        items: [entity],
      );
    }
    final result = await gateway.list();
    return VoiceExecuted(
      '${module.labelPlural}: ${result.items.length} registro(s)'
      '${result.fromCache ? ' (datos guardados en este dispositivo)' : ''}.',
      items: result.items,
    );
  }

  /// Error de validación por campo, con el mensaje del MISMO validador que el formulario.
  Map<FieldSpec, String> _invalidFields(
    Iterable<FieldSpec> fields,
    Map<String, String> raw,
  ) {
    final errors = <FieldSpec, String>{};
    for (final field in fields) {
      final error = FieldValidator.validate(field, raw[field.name]);
      if (error != null) errors[field] = error;
    }
    return errors;
  }

  Map<String, Object?> _typed(
    Iterable<FieldSpec> fields,
    Map<String, String> raw,
  ) => {
    for (final field in fields)
      field.name: FieldValidator.parse(field, raw[field.name]!),
  };

  VoiceFailure _rejected(
    VoiceCommand command,
    Map<FieldSpec, String> invalid,
  ) => VoiceFailure(
    VoiceErrorKind.datosFaltantes,
    understood: [
      'Acción: ${command.intent.name}',
      'Entidad: ${command.module.label}',
      for (final f in command.module.fields)
        if (command.values.containsKey(f.name))
          '${f.label}: ${command.values[f.name]}',
    ],
    missing: [for (final f in invalid.keys) f.label],
    detail: invalid.values.join(' '),
  );
}

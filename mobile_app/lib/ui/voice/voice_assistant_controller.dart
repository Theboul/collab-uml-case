import 'package:flutter/foundation.dart';

import '../../data/connectivity_monitor.dart';
import '../../data/voice/speech_input.dart';
import '../../data/voice/voice_command_executor.dart';
import '../../domain/voice/original_text.dart';
import '../../domain/voice/text_normalizer.dart';
import '../../domain/voice/voice_command.dart';
import '../../domain/voice/voice_command_parser.dart';

/// Fases explícitas del flujo del asistente.
enum VoicePhase {
  /// Esperando una entrada.
  idle('Listo'),

  /// Se está escribiendo el comando.
  typing('Escribiendo…'),

  /// El micrófono está abierto.
  listening('Escuchando…'),

  /// Interpretando la frase.
  processing('Procesando…'),

  /// Esperando que el usuario confirme lo que se entendió.
  confirming('Confirmando'),

  /// Ejecutando contra el repositorio.
  executing('Ejecutando…'),

  executed('Ejecutado'),

  failed('Error');

  const VoicePhase(this.label);

  final String label;
}

/// De dónde vino el texto: el mismo [VoiceCommandParser] atiende las dos entradas.
enum VoiceSource { voice, text }

/// Sin red no se intenta ni escuchar: la voz de este dispositivo necesita conexión.
const VoiceFailure voiceNeedsNetwork = VoiceFailure(
  VoiceErrorKind.recursosInsuficientes,
  detail: 'El reconocimiento de voz necesita conexión en este dispositivo — usa el campo de texto.',
);

/// Orquesta el asistente: voz o texto → normalizar → parsear → (confirmar) → ejecutar.
///
/// No contiene lógica de negocio: parsea con [VoiceCommandParser], valida y ejecuta con
/// [VoiceCommandExecutor], que llama al repositorio offline-first existente.
class VoiceAssistantController extends ChangeNotifier {
  VoiceAssistantController({
    required this.executor,
    required this.monitor,
    required this.speech,
    this.parser = const VoiceCommandParser(),
  });

  final VoiceCommandExecutor executor;
  final ConnectivityMonitor monitor;
  final SpeechInput speech;
  final VoiceCommandParser parser;

  VoicePhase _phase = VoicePhase.idle;
  VoiceSource? _source;
  String? _transcript;
  VoiceCommand? _command;
  VoiceFailure? _failure;
  String? _errorMessage;
  VoiceExecuted? _executed;
  bool _disposed = false;
  bool _micReady = false;
  String? _voiceLocale;

  /// Identifica cada escucha: el resultado tardío de una escucha cancelada se ignora.
  int _session = 0;

  VoicePhase get phase => _phase;

  VoiceSource? get source => _source;

  /// Lo que se dijo (transcrito) o escribió.
  String? get transcript => _transcript;

  /// Comando entendido, pendiente de confirmar o ya ejecutado.
  VoiceCommand? get command => _command;

  /// Una de las 5 excepciones de la ficha (fase [VoicePhase.failed]).
  VoiceFailure? get failure => _failure;

  /// Fallo del repositorio al ejecutar (no existe el registro, servidor…): el mismo texto que ven
  /// las pantallas manuales.
  String? get errorMessage => _errorMessage;

  VoiceExecuted? get executed => _executed;

  /// Idioma de reconocimiento elegido (`es_BO`); `null` = automático (el del dispositivo).
  String? get voiceLocale => _voiceLocale;

  set voiceLocale(String? value) {
    _voiceLocale = value;
    if (!_disposed) notifyListeners();
  }

  /// En la fase [VoicePhase.listening]: ¿el micrófono ya está abierto? Antes de eso hablar pierde
  /// las primeras palabras, así que la pantalla dice "Abriendo micrófono…".
  bool get micReady => _micReady;

  bool get busy =>
      _phase == VoicePhase.listening ||
      _phase == VoicePhase.processing ||
      _phase == VoicePhase.executing;

  void _set(VoicePhase phase) {
    _phase = phase;
    if (!_disposed) notifyListeners();
  }

  /// El usuario está escribiendo.
  void typingChanged(String text) {
    if (busy || _phase == VoicePhase.confirming) return;
    _set(text.trim().isEmpty ? VoicePhase.idle : VoicePhase.typing);
  }

  /// Entrada de voz. Antes de escuchar comprueba la conexión con el monitor de CU13.
  Future<void> startListening() async {
    if (busy) return;
    _begin(VoiceSource.voice);
    if (!await monitor.refresh()) {
      _fail(voiceNeedsNetwork);
      return;
    }
    _micReady = false;
    _set(VoicePhase.listening);
    final session = ++_session;
    final capture = await speech.listen(
      localeId: _voiceLocale,
      onReady: () {
        if (_session != session || _phase != VoicePhase.listening) return;
        _micReady = true;
        if (!_disposed) notifyListeners();
      },
    );
    if (_session != session || _phase != VoicePhase.listening) {
      return; // se canceló mientras escuchaba
    }
    switch (capture) {
      case SpeechFailed(:final failure):
        _fail(failure);
      case SpeechHeard(:final transcript):
        await _interpret(transcript);
    }
  }

  /// Entrada de texto: exactamente el mismo parser.
  Future<void> submitText(String text) async {
    if (busy) return;
    _begin(VoiceSource.text);
    await _interpret(text);
  }

  void _begin(VoiceSource source) {
    _source = source;
    _transcript = null;
    _command = null;
    _failure = null;
    _errorMessage = null;
    _executed = null;
  }

  Future<void> _interpret(String text) async {
    _transcript = text.trim();
    _set(VoicePhase.processing);
    final parsed = parser.parse(normalizeText(text));
    switch (parsed) {
      case VoiceFailure():
        _fail(parsed);
      case VoiceCommand():
        // Mayúsculas y tildes vuelven a los campos de texto (el parser trabaja normalizado).
        final command = restoreOriginalText(parsed, text);
        final invalid = executor.validate(command);
        if (invalid != null) {
          _fail(invalid); // no se pide confirmar algo que se va a rechazar
          return;
        }
        _command = command;
        if (command.intent == VoiceIntent.consultar) {
          await _run(); // leer no modifica nada: no hace falta confirmar
        } else {
          _set(VoicePhase.confirming);
        }
    }
  }

  /// El usuario confirma lo que se entendió.
  Future<void> confirm() async {
    if (_phase != VoicePhase.confirming) return;
    await _run();
  }

  Future<void> _run() async {
    final command = _command;
    if (command == null) return;
    _set(VoicePhase.executing);
    final result = await executor.execute(command);
    switch (result) {
      case VoiceExecuted():
        _executed = result;
        _set(VoicePhase.executed);
      case VoiceRejected(:final failure):
        _fail(failure);
      case VoiceExecutionError(:final failure):
        _errorMessage = failure.userMessage;
        _set(VoicePhase.failed);
    }
  }

  /// Descarta lo entendido (o deja de escuchar) sin ejecutar nada.
  Future<void> cancel() async {
    if (_phase == VoicePhase.listening) {
      _session++; // así startListening ignora el resultado que llegue
      _phase = VoicePhase.idle;
      await speech.cancel();
    }
    reset();
  }

  void reset() {
    _begin(VoiceSource.text);
    _source = null;
    _set(VoicePhase.idle);
  }

  void _fail(VoiceFailure failure) {
    _failure = failure;
    _set(VoicePhase.failed);
  }

  @override
  void dispose() {
    _disposed = true;
    super.dispose();
  }
}

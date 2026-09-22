import 'dart:async';

import 'package:gestion_movil/data/voice/speech_input.dart';

/// [SpeechInput] de test: devuelve lo que se le indique, sin micrófono ni red.
///
/// Con [hold] la escucha queda abierta hasta que el test llame a [complete]: sirve para ver la
/// fase "escuchando" en pantalla.
class FakeSpeechInput implements SpeechInput {
  FakeSpeechInput([this.next]);

  /// Lo que devolverá la próxima escucha.
  SpeechCapture? next;

  bool hold = false;

  /// Con `true` el micrófono "tarda en abrirse": `onReady` no se llama hasta [markReady].
  bool deferReady = false;
  void Function()? _ready;

  /// El plugin real completa la escucha al cancelar; ponlo en `false` para simular que un resultado
  /// llega DESPUÉS de cancelar.
  bool completeOnCancel = true;
  int listenCalls = 0;

  /// Idioma con el que se pidió la última escucha (`null` = automático).
  String? lastLocale;
  int cancelCalls = 0;
  Completer<SpeechCapture>? _pending;

  void markReady() => _ready?.call();

  @override
  Future<SpeechCapture> listen({void Function()? onReady, String? localeId}) {
    listenCalls++;
    lastLocale = localeId;
    if (deferReady) {
      _ready = onReady;
    } else {
      onReady?.call();
    }
    if (hold) return (_pending = Completer<SpeechCapture>()).future;
    return Future.value(next ?? const SpeechHeard(''));
  }

  void complete(SpeechCapture capture) {
    final pending = _pending;
    if (pending != null && !pending.isCompleted) pending.complete(capture);
  }

  @override
  Future<void> cancel() async {
    cancelCalls++;
    if (completeOnCancel) complete(const SpeechHeard(''));
  }
}

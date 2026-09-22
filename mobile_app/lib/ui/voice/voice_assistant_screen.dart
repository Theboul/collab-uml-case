import 'package:flutter/material.dart';

import '../../app_scope.dart';
import '../../domain/voice/voice_command.dart';
import '../widgets/sync_widgets.dart';
import 'voice_assistant_controller.dart';
import 'voice_failure_messages.dart';

/// Asistente de comandos por **voz o texto**. Las dos entradas alimentan el mismo parser y el mismo
/// repositorio que las pantallas manuales; solo la voz necesita red (ver `docs/decisions.md`).
class VoiceAssistantScreen extends StatefulWidget {
  const VoiceAssistantScreen({super.key});

  @override
  State<VoiceAssistantScreen> createState() => _VoiceAssistantScreenState();
}

class _VoiceAssistantScreenState extends State<VoiceAssistantScreen> {
  VoiceAssistantController? _controller;
  final _text = TextEditingController();

  @override
  void didChangeDependencies() {
    super.didChangeDependencies();
    final services = AppScope.of(context);
    _controller ??= VoiceAssistantController(
      executor: services.voiceExecutor,
      monitor: services.monitor,
      speech: services.speech,
    );
  }

  @override
  void dispose() {
    _controller?.dispose();
    _text.dispose();
    super.dispose();
  }

  void _submit(VoiceAssistantController c) {
    final text = _text.text;
    if (text.trim().isEmpty || c.busy) return;
    FocusScope.of(context).unfocus();
    c.submitText(text);
  }

  void _startOver(VoiceAssistantController c) {
    _text.clear();
    c.reset();
  }

  @override
  Widget build(BuildContext context) {
    final c = _controller!;
    return Scaffold(
      appBar: AppBar(
        title: const Text('Asistente de voz'),
        actions: const [SyncActionButton()],
      ),
      body: Column(
        children: [
          const ConnectionBanner(),
          Expanded(
            child: ListenableBuilder(
              listenable: c,
              builder: (context, _) => ListView(
                padding: const EdgeInsets.all(16),
                children: [
                  _PhaseBar(phase: c.phase, micReady: c.micReady),
                  const SizedBox(height: 12),
                  _InputRow(
                    controller: _text,
                    assistant: c,
                    onSubmit: () => _submit(c),
                  ),
                  const SizedBox(height: 16),
                  if (c.transcript != null) _TranscriptCard(controller: c),
                  if (c.phase == VoicePhase.confirming)
                    _ConfirmCard(controller: c),
                  if (c.phase == VoicePhase.executed)
                    _ResultCard(controller: c, onNew: () => _startOver(c)),
                  if (c.phase == VoicePhase.failed)
                    _FailureCard(controller: c, onNew: () => _startOver(c)),
                  if (c.phase == VoicePhase.idle ||
                      c.phase == VoicePhase.typing)
                    const Padding(
                      padding: EdgeInsets.only(top: 8),
                      child: Text(voiceExamples, key: Key('voice-help')),
                    ),
                ],
              ),
            ),
          ),
        ],
      ),
    );
  }
}

class _PhaseBar extends StatelessWidget {
  const _PhaseBar({required this.phase, required this.micReady});

  final VoicePhase phase;

  /// Solo importa en [VoicePhase.listening].
  final bool micReady;

  @override
  Widget build(BuildContext context) {
    return Align(
      alignment: Alignment.centerLeft,
      child: Chip(
        key: Key('phase-${phase.name}'),
        avatar:
            (phase == VoicePhase.listening ||
                phase == VoicePhase.processing ||
                phase == VoicePhase.executing)
            ? const SizedBox(
                width: 14,
                height: 14,
                child: CircularProgressIndicator(strokeWidth: 2),
              )
            : Icon(switch (phase) {
                VoicePhase.executed => Icons.check_circle_outline,
                VoicePhase.failed => Icons.error_outline,
                VoicePhase.confirming => Icons.help_outline,
                _ => Icons.circle_outlined,
              }, size: 16),
        label: Text(
          phase == VoicePhase.listening && !micReady
              ? 'Abriendo micrófono…'
              : phase.label,
          key: const Key('voice-phase'),
        ),
      ),
    );
  }
}

/// Idiomas de reconocimiento que se pueden elegir. `auto` = el del dispositivo. Un acento que el
/// reconocedor no espera se entiende peor: permitir cambiarlo evita quedarse sin voz por eso.
const List<(String, String)> _voiceLocales = [
  ('auto', 'Automático (idioma del dispositivo)'),
  ('es_BO', 'Español (Bolivia)'),
  ('es_419', 'Español (Latinoamérica)'),
  ('es_ES', 'Español (España)'),
  ('es_MX', 'Español (México)'),
  ('es_US', 'Español (Estados Unidos)'),
];

class _InputRow extends StatelessWidget {
  const _InputRow({
    required this.controller,
    required this.assistant,
    required this.onSubmit,
  });

  final TextEditingController controller;
  final VoiceAssistantController assistant;
  final VoidCallback onSubmit;

  @override
  Widget build(BuildContext context) {
    final listening = assistant.phase == VoicePhase.listening;
    return Column(
      crossAxisAlignment: CrossAxisAlignment.stretch,
      children: [
        Row(
          crossAxisAlignment: CrossAxisAlignment.start,
          children: [
            Expanded(
              child: TextField(
                key: const Key('voice-text'),
                controller: controller,
                enabled: !assistant.busy,
                textInputAction: TextInputAction.send,
                onChanged: assistant.typingChanged,
                onSubmitted: (_) => onSubmit(),
                decoration: const InputDecoration(
                  labelText: 'Escribe un comando',
                  hintText: 'crear producto camisa 20',
                  border: OutlineInputBorder(),
                ),
              ),
            ),
            const SizedBox(width: 8),
            Padding(
              padding: const EdgeInsets.only(top: 6),
              child: FilledButton(
                key: const Key('voice-send'),
                onPressed: assistant.busy ? null : onSubmit,
                child: const Text('Enviar'),
              ),
            ),
          ],
        ),
        const SizedBox(height: 12),
        FilledButton.tonalIcon(
          key: const Key('voice-mic'),
          onPressed: listening
              ? assistant.cancel
              : (assistant.busy ? null : assistant.startListening),
          icon: Icon(listening ? Icons.stop : Icons.mic),
          label: Text(listening ? 'Detener' : 'Hablar (requiere conexión)'),
        ),
        Row(
          children: [
            const Icon(Icons.language, size: 18),
            const SizedBox(width: 8),
            Expanded(
              child: DropdownButton<String>(
                key: const Key('voice-locale'),
                isExpanded: true,
                value: assistant.voiceLocale ?? 'auto',
                onChanged: assistant.busy
                    ? null
                    : (value) => assistant.voiceLocale = value == 'auto'
                          ? null
                          : value,
                items: [
                  for (final (id, label) in _voiceLocales)
                    DropdownMenuItem(value: id, child: Text(label)),
                ],
              ),
            ),
          ],
        ),
      ],
    );
  }
}

class _TranscriptCard extends StatelessWidget {
  const _TranscriptCard({required this.controller});

  final VoiceAssistantController controller;

  @override
  Widget build(BuildContext context) => Card(
    child: ListTile(
      leading: Icon(
        controller.source == VoiceSource.voice ? Icons.mic : Icons.keyboard,
      ),
      title: Text(
        controller.source == VoiceSource.voice ? 'Dijiste' : 'Escribiste',
      ),
      subtitle: Text(
        '"${controller.transcript}"',
        key: const Key('voice-transcript'),
      ),
    ),
  );
}

class _ConfirmCard extends StatelessWidget {
  const _ConfirmCard({required this.controller});

  final VoiceAssistantController controller;

  @override
  Widget build(BuildContext context) {
    final command = controller.command!;
    return Card(
      color: Theme.of(context).colorScheme.secondaryContainer,
      child: Padding(
        padding: const EdgeInsets.all(16),
        child: Column(
          crossAxisAlignment: CrossAxisAlignment.start,
          children: [
            const Text('¿Confirmas esta acción?'),
            const SizedBox(height: 8),
            Text(
              command.summary,
              key: const Key('voice-summary'),
              style: Theme.of(context).textTheme.titleMedium,
            ),
            if (command.intent == VoiceIntent.eliminar) ...[
              const SizedBox(height: 8),
              const Text(
                'Esta acción no se puede deshacer y elimina también sus relaciones.',
                key: Key('voice-delete-warning'),
              ),
            ],
            const SizedBox(height: 12),
            Row(
              mainAxisAlignment: MainAxisAlignment.end,
              children: [
                TextButton(
                  key: const Key('voice-cancel'),
                  onPressed: controller.cancel,
                  child: const Text('Cancelar'),
                ),
                const SizedBox(width: 8),
                FilledButton(
                  key: const Key('voice-confirm'),
                  onPressed: controller.confirm,
                  child: const Text('Confirmar'),
                ),
              ],
            ),
          ],
        ),
      ),
    );
  }
}

class _ResultCard extends StatelessWidget {
  const _ResultCard({required this.controller, required this.onNew});

  final VoiceAssistantController controller;
  final VoidCallback onNew;

  @override
  Widget build(BuildContext context) {
    final executed = controller.executed!;
    final module = controller.command!.module;
    return Card(
      child: Padding(
        padding: const EdgeInsets.all(16),
        child: Column(
          crossAxisAlignment: CrossAxisAlignment.start,
          children: [
            Row(
              children: [
                const Icon(Icons.check_circle, color: Colors.green),
                const SizedBox(width: 8),
                Expanded(
                  child: Text(executed.message, key: const Key('voice-result')),
                ),
              ],
            ),
            for (final item in executed.items.take(20))
              ListTile(
                dense: true,
                key: Key('voice-item-${item.id}'),
                title: Text(module.title(item)),
                subtitle: Text(module.subtitle(item)),
              ),
            Align(
              alignment: Alignment.centerRight,
              child: TextButton(
                key: const Key('voice-new'),
                onPressed: onNew,
                child: const Text('Nuevo comando'),
              ),
            ),
          ],
        ),
      ),
    );
  }
}

class _FailureCard extends StatelessWidget {
  const _FailureCard({required this.controller, required this.onNew});

  final VoiceAssistantController controller;
  final VoidCallback onNew;

  @override
  Widget build(BuildContext context) {
    final failure = controller.failure;
    final message = failure == null ? null : voiceMessageFor(failure);
    final scheme = Theme.of(context).colorScheme;
    return Card(
      key: Key(
        failure == null ? 'voice-error' : 'voice-failure-${failure.kind.name}',
      ),
      color: scheme.errorContainer,
      child: Padding(
        padding: const EdgeInsets.all(16),
        child: Column(
          crossAxisAlignment: CrossAxisAlignment.start,
          children: [
            Row(
              children: [
                Icon(message?.icon ?? Icons.error_outline, color: scheme.error),
                const SizedBox(width: 8),
                Expanded(
                  child: Text(
                    message?.title ?? 'No se pudo completar',
                    key: const Key('voice-failure-title'),
                    style: Theme.of(context).textTheme.titleMedium,
                  ),
                ),
              ],
            ),
            const SizedBox(height: 8),
            Text(
              message?.body ?? controller.errorMessage ?? '',
              key: const Key('voice-failure-body'),
            ),
            Align(
              alignment: Alignment.centerRight,
              child: TextButton(
                key: const Key('voice-new'),
                onPressed: onNew,
                child: const Text('Nuevo comando'),
              ),
            ),
          ],
        ),
      ),
    );
  }
}

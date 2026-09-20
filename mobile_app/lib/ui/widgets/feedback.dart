import 'package:flutter/material.dart';

import '../../data/failures.dart';

/// Mensaje de error con botón opcional para reintentar (carga fallida de una pantalla).
class ErrorMessage extends StatelessWidget {
  const ErrorMessage({super.key, required this.failure, this.onRetry});

  final Object failure;
  final VoidCallback? onRetry;

  @override
  Widget build(BuildContext context) {
    final text = failure is AppFailure
        ? (failure as AppFailure).userMessage
        : '$failure';
    return Center(
      child: Padding(
        padding: const EdgeInsets.all(24),
        child: Column(
          mainAxisSize: MainAxisSize.min,
          children: [
            Icon(
              Icons.cloud_off,
              size: 48,
              color: Theme.of(context).colorScheme.error,
            ),
            const SizedBox(height: 12),
            Text(
              text,
              textAlign: TextAlign.center,
              key: const Key('error-message'),
            ),
            if (onRetry != null) ...[
              const SizedBox(height: 12),
              FilledButton.icon(
                key: const Key('retry'),
                onPressed: onRetry,
                icon: const Icon(Icons.refresh),
                label: const Text('Reintentar'),
              ),
            ],
          ],
        ),
      ),
    );
  }
}

/// Confirmación / error breve para el usuario que sobrevive al cierre de la pantalla actual.
void showResult(BuildContext context, String message, {bool error = false}) {
  final scheme = Theme.of(context).colorScheme;
  ScaffoldMessenger.of(context)
    ..hideCurrentSnackBar()
    ..showSnackBar(
      SnackBar(
        key: Key(error ? 'snack-error' : 'snack-ok'),
        content: Text(message),
        backgroundColor: error ? scheme.error : null,
        duration: Duration(seconds: error ? 6 : 4),
      ),
    );
}

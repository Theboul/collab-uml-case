import 'dart:developer' as developer;
import 'dart:io';
import 'package:flutter_test/flutter_test.dart';
import 'package:integration_test/integration_test.dart';
import 'package:llm_llamacpp/llm_llamacpp.dart';

void main() {
  IntegrationTestWidgetsFlutterBinding.ensureInitialized();

  test(
    'Spike LLM On-Device Benchmark',
    () async {
    developer.log('>>> INICIANDO SPIKE LLM ON-DEVICE <<<');

    // Rutas candidatas para el archivo GGUF en el dispositivo
    const candidates = [
      '/data/user/0/com.example.gestion_movil/files/Qwen3-0.6B-Q4_K_M.gguf',
      '/data/data/com.example.gestion_movil/files/Qwen3-0.6B-Q4_K_M.gguf',
      '/sdcard/Download/Qwen3-0.6B-Q4_K_M.gguf',
      '/sdcard/Qwen3-0.6B-Q4_K_M.gguf',
    ];

    String? resolvedPath;
    for (final path in candidates) {
      final f = File(path);
      if (f.existsSync()) {
        resolvedPath = path;
        developer.log('Modelo encontrado en: $path (${f.lengthSync()} bytes)');
        break;
      }
    }

    if (resolvedPath == null) {
      fail('El modelo Qwen3-0.6B-Q4_K_M.gguf no se encontró en ninguna de las rutas: $candidates');
    }

    final modelFile = File(resolvedPath);
    final modelSizeBytes = modelFile.lengthSync();
    developer.log('Tamaño del modelo en disco: ${(modelSizeBytes / (1024 * 1024)).toStringAsFixed(2)} MB');

    final rssPreLoad = ProcessInfo.currentRss;
    final maxRssPreLoad = ProcessInfo.maxRss;
    developer.log('RAM previa a carga: ${(rssPreLoad / (1024 * 1024)).toStringAsFixed(2)} MB (Max RSS: ${(maxRssPreLoad / (1024 * 1024)).toStringAsFixed(2)} MB)');

    // 1. Medir tiempo de carga
    developer.log('Iniciando carga del modelo con LlamaCppChatRepository...');
    final loadSw = Stopwatch()..start();
    final repo = LlamaCppChatRepository(
      contextSize: 512, // Contexto prudente para 2GB RAM
      nGpuLayers: 0,    // CPU pura
    );

    try {
      // ignore: deprecated_member_use
      await repo.loadModel(resolvedPath);
    } catch (e, stack) {
      developer.log('ERROR CRÍTICO AL CARGAR EL MODELO: $e\n$stack');
      rethrow;
    }
    loadSw.stop();
    final loadTimeMs = loadSw.elapsedMilliseconds;
    developer.log('Modelo cargado exitosamente en ${loadTimeMs}ms (${(loadTimeMs / 1000).toStringAsFixed(2)}s)');

    final rssPostLoad = ProcessInfo.currentRss;
    final maxRssPostLoad = ProcessInfo.maxRss;
    developer.log('RAM tras carga: ${(rssPostLoad / (1024 * 1024)).toStringAsFixed(2)} MB (Max RSS: ${(maxRssPostLoad / (1024 * 1024)).toStringAsFixed(2)} MB)');

    // 2. Ejecutar inferencia con el prompt solicitado
    const prompt = 'crear un pedido con producto X cantidad 2';
    developer.log('Enviando prompt de prueba: "$prompt"');

    final inferSw = Stopwatch()..start();
    int? firstTokenMs;
    int chunkCount = 0;
    final responseBuffer = StringBuffer();

    try {
      final stream = repo.streamChat(
        'qwen3',
        messages: [
          LLMMessage(role: LLMRole.user, content: prompt),
        ],
      );

      await for (final chunk in stream) {
        if (firstTokenMs == null) {
          firstTokenMs = inferSw.elapsedMilliseconds;
          developer.log('Primer token recibido en ${firstTokenMs}ms (${(firstTokenMs / 1000).toStringAsFixed(2)}s)');
        }
        final text = chunk.message?.content ?? '';
        if (text.isNotEmpty) {
          responseBuffer.write(text);
          chunkCount++;
        }
      }
    } catch (e, stack) {
      developer.log('ERROR CRÍTICO DURANTE INFERENCIA: $e\n$stack');
      rethrow;
    } finally {
      inferSw.stop();
      repo.dispose();
    }

    final totalInferMs = inferSw.elapsedMilliseconds;
    final fullText = responseBuffer.toString();
    final rssPostInfer = ProcessInfo.currentRss;
    final maxRssPostInfer = ProcessInfo.maxRss;

    // Tokens estimados a partir de chunks generados
    final tokensGenerated = chunkCount;
    final tokensPerSec = totalInferMs > 0
        ? (tokensGenerated / (totalInferMs / 1000.0))
        : 0.0;

    developer.log('>>> RESULTADOS DEL SPIKE <<<');
    developer.log('Texto generado: "$fullText"');
    developer.log('Tiempo de carga: $loadTimeMs ms (${(loadTimeMs / 1000).toStringAsFixed(2)} s)');
    developer.log('Tiempo primer token: ${firstTokenMs ?? -1} ms (${((firstTokenMs ?? 0) / 1000).toStringAsFixed(2)} s)');
    developer.log('Tiempo total inferencia: $totalInferMs ms (${(totalInferMs / 1000).toStringAsFixed(2)} s)');
    developer.log('Tokens/chunks generados: $tokensGenerated');
    developer.log('Tokens por segundo: ${tokensPerSec.toStringAsFixed(2)} tok/s');
    developer.log('RAM final: ${(rssPostInfer / (1024 * 1024)).toStringAsFixed(2)} MB');
    developer.log('RAM Pico (Max RSS): ${(maxRssPostInfer / (1024 * 1024)).toStringAsFixed(2)} MB');
    developer.log('Delta RAM proceso: ${((maxRssPostInfer - maxRssPreLoad) / (1024 * 1024)).toStringAsFixed(2)} MB');

    // Imprimir bloque delimitado para parser
    // ignore: avoid_print
    print('=== LLM_BENCHMARK_RESULTS ===');
    // ignore: avoid_print
    print('modelPath: $resolvedPath');
    // ignore: avoid_print
    print('modelSizeBytes: $modelSizeBytes');
    // ignore: avoid_print
    print('loadTimeMs: $loadTimeMs');
    // ignore: avoid_print
    print('firstTokenMs: ${firstTokenMs ?? -1}');
    // ignore: avoid_print
    print('totalInferMs: $totalInferMs');
    // ignore: avoid_print
    print('tokensGenerated: $tokensGenerated');
    // ignore: avoid_print
    print('tokensPerSec: ${tokensPerSec.toStringAsFixed(2)}');
    // ignore: avoid_print
    print('ramPreLoadMb: ${(rssPreLoad / (1024 * 1024)).toStringAsFixed(2)}');
    // ignore: avoid_print
    print('ramPostLoadMb: ${(rssPostLoad / (1024 * 1024)).toStringAsFixed(2)}');
    // ignore: avoid_print
    print('ramPeakMb: ${(maxRssPostInfer / (1024 * 1024)).toStringAsFixed(2)}');
    // ignore: avoid_print
    print('responseText: ${fullText.replaceAll('\n', ' ')}');
    // ignore: avoid_print
    print('=== END_LLM_BENCHMARK_RESULTS ===');
  }, timeout: const Timeout(Duration(minutes: 5)));
}

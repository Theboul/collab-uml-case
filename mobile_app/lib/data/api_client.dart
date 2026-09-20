import 'dart:async';
import 'dart:convert';
import 'dart:io';

import 'package:http/http.dart' as http;

import '../config/api_config.dart';
import 'failures.dart';

/// Respuesta HTTP cruda: el repositorio decide qué significa cada estado.
class ApiResponse {
  const ApiResponse(this.status, this.body);

  final int status;
  final String body;
}

/// Cliente HTTP mínimo hacia el backend. No interpreta estados; solo traduce los fallos de red
/// (sin conexión, timeout, servidor apagado) a [NetworkFailure].
class ApiClient {
  ApiClient({http.Client? client, String? baseUrl, Duration? timeout})
    : _client = client ?? http.Client(),
      baseUrl = baseUrl ?? ApiConfig.baseUrl,
      timeout = timeout ?? ApiConfig.timeout;

  final http.Client _client;
  final String baseUrl;
  final Duration timeout;

  /// Envía `method` a `{baseUrl}/{path}` con `jsonBody` opcional (se serializa a JSON).
  Future<ApiResponse> send(
    String method,
    String path, {
    Object? jsonBody,
  }) async {
    final request = http.Request(method, Uri.parse('$baseUrl/$path'))
      ..headers['Content-Type'] = 'application/json; charset=utf-8'
      ..headers['Accept'] = 'application/json';
    if (jsonBody != null) request.body = jsonEncode(jsonBody);

    try {
      final streamed = await _client.send(request).timeout(timeout);
      final response = await http.Response.fromStream(streamed)
          .timeout(timeout);
      return ApiResponse(response.statusCode, utf8.decode(response.bodyBytes));
    } on TimeoutException {
      throw const NetworkFailure('timeout');
    } on SocketException catch (e) {
      throw NetworkFailure(e.message);
    } on http.ClientException catch (e) {
      throw NetworkFailure(e.message);
    } on HandshakeException catch (e) {
      throw NetworkFailure(e.message);
    }
  }

  void close() => _client.close();
}

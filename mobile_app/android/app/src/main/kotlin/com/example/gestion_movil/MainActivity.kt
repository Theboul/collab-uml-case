package com.example.gestion_movil

import io.flutter.embedding.android.FlutterActivity
import io.flutter.embedding.engine.FlutterEngine
import io.flutter.plugin.common.MethodChannel

class MainActivity : FlutterActivity() {
    override fun configureFlutterEngine(flutterEngine: FlutterEngine) {
        super.configureFlutterEngine(flutterEngine)
        MethodChannel(flutterEngine.dartExecutor.binaryMessenger, "gestion_movil/asr_probe")
            .setMethodCallHandler { call, result ->
                when (call.method) {
                    "check" -> AsrProbe.check(this, call.argument<String>("tag") ?: "es-ES", result)
                    "listen" -> AsrProbe.listen(
                        this,
                        call.argument<String>("tag") ?: "es-ES",
                        call.argument<Boolean>("preferOffline") ?: true,
                        call.argument<Int>("seconds") ?: 15,
                        result,
                    )
                    else -> result.notImplemented()
                }
            }
    }
}

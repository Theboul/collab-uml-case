package com.example.gestion_movil

import android.content.Context
import android.content.Intent
import android.os.Build
import android.speech.RecognitionSupport
import android.speech.RecognitionSupportCallback
import android.speech.RecognizerIntent
import android.speech.SpeechRecognizer
import io.flutter.plugin.common.MethodChannel

/**
 * Diagnóstico de reconocimiento de voz OFFLINE (CU14, Fase 0).
 *
 * NO es parte de la app en producción: es la herramienta de medición que se usó para decidir el
 * alcance de CU14 (ver `mobile_app/docs/decisions.md`, sección CU14) y que se conserva para poder
 * repetir la medición en otro dispositivo. `VoiceAssistantScreen` no la usa ni depende de ella; la
 * app real habla con el reconocedor a través del plugin `speech_to_text`
 * (`lib/data/voice/speech_input.dart`), con `onDevice: false`.
 *
 * El plugin speech_to_text no expone qué idiomas tiene descargados el dispositivo, y con
 * `onDevice: true` cae EN SILENCIO al reconocedor por defecto si no hay reconocimiento local.
 * Esta consulta responde con la API del sistema (Android 13+): isOnDeviceRecognitionAvailable y
 * checkRecognitionSupport(installed / pending / supported).
 */
object AsrProbe {
    private val errorNames = mapOf(
        1 to "ERROR_NETWORK_TIMEOUT", 2 to "ERROR_NETWORK", 3 to "ERROR_AUDIO", 4 to "ERROR_SERVER",
        5 to "ERROR_CLIENT", 6 to "ERROR_SPEECH_TIMEOUT", 7 to "ERROR_NO_MATCH", 8 to "ERROR_RECOGNIZER_BUSY",
        9 to "ERROR_INSUFFICIENT_PERMISSIONS", 10 to "ERROR_TOO_MANY_REQUESTS", 11 to "ERROR_SERVER_DISCONNECTED",
        12 to "ERROR_LANGUAGE_NOT_SUPPORTED", 13 to "ERROR_LANGUAGE_UNAVAILABLE",
        14 to "ERROR_CANNOT_CHECK_SUPPORT", 15 to "ERROR_CANNOT_LISTEN_TO_DOWNLOAD_EVENTS",
    )

    /**
     * Escucha DIRECTA con SpeechRecognizer (sin el plugin) y devuelve cada callback con su tiempo.
     * Sirve para saber si el reconocedor del sistema funciona y con qué código falla.
     */
    fun listen(
        context: Context,
        languageTag: String,
        preferOffline: Boolean,
        seconds: Int,
        result: MethodChannel.Result,
    ) {
        val started = android.os.SystemClock.elapsedRealtime()
        val events = mutableListOf<String>()
        val transcripts = mutableListOf<String>()
        var rmsCount = 0
        var rmsMax = -100f
        var finished = false
        val handler = android.os.Handler(android.os.Looper.getMainLooper())
        val recognizer = SpeechRecognizer.createSpeechRecognizer(context)
        fun log(text: String) { events.add("+${android.os.SystemClock.elapsedRealtime() - started}ms $text") }
        lateinit var finish: (String) -> Unit
        finish = { why ->
            if (!finished) {
                finished = true
                handler.removeCallbacksAndMessages(null)
                log("FIN: $why")
                try { recognizer.destroy() } catch (_: Exception) {}
                result.success(mapOf(
                    "events" to events, "transcripts" to transcripts, "rmsCount" to rmsCount, "rmsMax" to rmsMax,
                    "languageTag" to languageTag, "preferOffline" to preferOffline, "finishedBecause" to why,
                ))
            }
        }
        recognizer.setRecognitionListener(object : android.speech.RecognitionListener {
            override fun onReadyForSpeech(params: android.os.Bundle?) = log("onReadyForSpeech")
            override fun onBeginningOfSpeech() = log("onBeginningOfSpeech")
            override fun onRmsChanged(rmsdB: Float) { rmsCount++; if (rmsdB > rmsMax) rmsMax = rmsdB }
            override fun onBufferReceived(buffer: ByteArray?) = log("onBufferReceived")
            override fun onEndOfSpeech() = log("onEndOfSpeech")
            override fun onPartialResults(partialResults: android.os.Bundle?) {
                val l = partialResults?.getStringArrayList(SpeechRecognizer.RESULTS_RECOGNITION)
                log("onPartialResults $l")
            }
            override fun onEvent(eventType: Int, params: android.os.Bundle?) = log("onEvent $eventType")
            override fun onResults(results: android.os.Bundle?) {
                val l = results?.getStringArrayList(SpeechRecognizer.RESULTS_RECOGNITION) ?: arrayListOf()
                transcripts.addAll(l)
                log("onResults $l")
                finish("onResults")
            }
            override fun onError(error: Int) {
                log("onError $error ${errorNames[error] ?: "?"}")
                finish("onError:${errorNames[error] ?: error}")
            }
        })
        val intent = Intent(RecognizerIntent.ACTION_RECOGNIZE_SPEECH)
            .putExtra(RecognizerIntent.EXTRA_LANGUAGE_MODEL, RecognizerIntent.LANGUAGE_MODEL_FREE_FORM)
            .putExtra(RecognizerIntent.EXTRA_LANGUAGE, languageTag)
            .putExtra(RecognizerIntent.EXTRA_PARTIAL_RESULTS, false)
            .putExtra(RecognizerIntent.EXTRA_PREFER_OFFLINE, preferOffline)
            .putExtra(RecognizerIntent.EXTRA_MAX_RESULTS, 3)
            .putExtra(RecognizerIntent.EXTRA_CALLING_PACKAGE, context.packageName)
        log("startListening tag=$languageTag preferOffline=$preferOffline")
        handler.postDelayed({ finish("timeout_${seconds}s") }, seconds * 1000L)
        recognizer.startListening(intent)
    }

    fun check(context: Context, languageTag: String, result: MethodChannel.Result) {
        val out = mutableMapOf<String, Any?>(
            "sdk" to Build.VERSION.SDK_INT,
            "languageTag" to languageTag,
            "recognitionAvailable" to SpeechRecognizer.isRecognitionAvailable(context),
        )
        if (Build.VERSION.SDK_INT < Build.VERSION_CODES.S) {
            out["onDeviceAvailable"] = false
            result.success(out)
            return
        }
        val onDevice = SpeechRecognizer.isOnDeviceRecognitionAvailable(context)
        out["onDeviceAvailable"] = onDevice
        if (!onDevice || Build.VERSION.SDK_INT < Build.VERSION_CODES.TIRAMISU) {
            result.success(out)
            return
        }
        val recognizer = SpeechRecognizer.createOnDeviceSpeechRecognizer(context)
        val intent = Intent(RecognizerIntent.ACTION_RECOGNIZE_SPEECH)
            .putExtra(RecognizerIntent.EXTRA_LANGUAGE, languageTag)
        recognizer.checkRecognitionSupport(
            intent,
            context.mainExecutor,
            object : RecognitionSupportCallback {
                override fun onSupportResult(support: RecognitionSupport) {
                    out["installedOnDevice"] = support.installedOnDeviceLanguages
                    out["pendingOnDevice"] = support.pendingOnDeviceLanguages
                    out["supportedOnDevice"] = support.supportedOnDeviceLanguages
                    out["online"] = support.onlineLanguages
                    recognizer.destroy()
                    result.success(out)
                }

                override fun onError(error: Int) {
                    out["supportError"] = error
                    recognizer.destroy()
                    result.success(out)
                }
            },
        )
    }
}

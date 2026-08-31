import 'dart:async';

import 'package:flutter/material.dart';
import 'package:flutter/services.dart';

import '../../../core/api/api_client.dart';
import '../../../core/localization/app_language.dart';
import '../../../core/localization/app_strings.dart';
import '../../../core/theme/app_theme.dart';
import '../controllers/catalogue_flow_controller.dart';
import '../models/catalogue_models.dart';
import 'catalogue_generation_screen.dart';

class VoiceDescriptionScreen extends StatefulWidget {
  const VoiceDescriptionScreen({
    super.key,
    required this.controller,
    required this.language,
  });

  final CatalogueFlowController controller;
  final AppLanguage language;

  @override
  State<VoiceDescriptionScreen> createState() => _VoiceDescriptionScreenState();
}

class _VoiceDescriptionScreenState extends State<VoiceDescriptionScreen> {
  Timer? _timer;
  LocalMediaFile? _recording;
  int _seconds = 0;
  bool _isRecording = false;
  bool _uploading = false;
  String? _error;

  @override
  void dispose() {
    _timer?.cancel();
    if (_isRecording) widget.controller.cancelRecording();
    super.dispose();
  }

  Future<void> _start() async {
    setState(() => _error = null);
    try {
      await widget.controller.startRecording();
      if (!mounted) return;
      setState(() {
        _recording = null;
        _seconds = 0;
        _isRecording = true;
      });
      _timer = Timer.periodic(const Duration(seconds: 1), (_) {
        if (!mounted) return;
        final next = _seconds + 1;
        setState(() => _seconds = next);
        if (next >= 120) _stop();
      });
    } on PlatformException catch (error) {
      if (mounted) {
        setState(() {
          final strings = AppStrings(widget.language);
          _error = error.code == 'PERMISSION_DENIED'
              ? strings.microphonePermission
              : (error.message ?? strings.recordingStartFailed);
        });
      }
    }
  }

  Future<void> _stop() async {
    if (!_isRecording) return;
    _timer?.cancel();
    setState(() => _isRecording = false);
    try {
      final recording = await widget.controller.stopRecording();
      if (mounted) setState(() => _recording = recording);
    } on PlatformException catch (error) {
      if (mounted) {
        setState(
          () => _error =
              error.message ?? AppStrings(widget.language).recordingSaveFailed,
        );
      }
    }
  }

  Future<void> _recordAgain() async {
    setState(() {
      _recording = null;
      _seconds = 0;
      _error = null;
    });
    await _start();
  }

  Future<void> _continue() async {
    final recording = _recording;
    if (recording == null || _uploading) return;
    setState(() {
      _uploading = true;
      _error = null;
    });
    try {
      final operation = await widget.controller.uploadVoiceAndGenerate(
        recording,
      );
      if (!mounted) return;
      await Navigator.of(context).push(
        MaterialPageRoute<void>(
          builder: (_) => CatalogueGenerationScreen(
            controller: widget.controller,
            initialOperation: operation,
            language: widget.language,
          ),
        ),
      );
    } on ApiException catch (error) {
      if (error.code == 'CONSENT_REQUIRED' && mounted) {
        final accepted = await _requestConsent();
        if (accepted && mounted) {
          setState(() => _uploading = false);
          await _continue();
          return;
        }
      }
      if (mounted) setState(() => _error = _messageFor(error.code));
    } finally {
      if (mounted) setState(() => _uploading = false);
    }
  }

  Future<bool> _requestConsent() async {
    final strings = AppStrings(widget.language);
    final accepted = await showDialog<bool>(
      context: context,
      builder: (context) => AlertDialog(
        title: Text(strings.voiceConsentTitle),
        content: Text(strings.voiceConsentBody),
        actions: [
          TextButton(
            onPressed: () => Navigator.of(context).pop(false),
            child: Text(strings.notNow),
          ),
          FilledButton(
            onPressed: () => Navigator.of(context).pop(true),
            child: Text(strings.consentAgree),
          ),
        ],
      ),
    );
    if (accepted != true) return false;
    await widget.controller.acceptMediaProcessingConsent();
    return true;
  }

  String _messageFor(String code) {
    final strings = AppStrings(widget.language);
    return switch (code) {
      'UPLOAD_TOO_LARGE' => strings.recordingTooLarge,
      'UNSUPPORTED_MEDIA_TYPE' => strings.unsupportedRecording,
      'AI_SERVICE_UNAVAILABLE' => strings.generationUnavailable,
      _ => strings.recordingUploadFailed,
    };
  }

  String get _timerText {
    final minutes = (_seconds ~/ 60).toString().padLeft(2, '0');
    final seconds = (_seconds % 60).toString().padLeft(2, '0');
    return '$minutes:$seconds';
  }

  @override
  Widget build(BuildContext context) {
    final hasRecording = _recording != null;
    final strings = AppStrings(widget.language);
    return Scaffold(
      appBar: AppBar(
        backgroundColor: AppColors.background,
        surfaceTintColor: Colors.transparent,
        title: Text(strings.productDescription),
      ),
      body: SafeArea(
        child: Padding(
          padding: const EdgeInsets.fromLTRB(24, 20, 24, 28),
          child: Column(
            crossAxisAlignment: CrossAxisAlignment.stretch,
            children: [
              Text(
                strings.describeInHindi,
                textAlign: TextAlign.center,
                style: Theme.of(context).textTheme.headlineSmall
                    ?.copyWith(fontSize: 28),
              ),
              const SizedBox(height: 10),
              Text(
                strings.descriptionExample,
                textAlign: TextAlign.center,
                style: Theme.of(context).textTheme.bodyMedium,
              ),
              const Spacer(),
              if (_isRecording) _Waveform(tick: _seconds),
              const SizedBox(height: 24),
              Text(
                _timerText,
                textAlign: TextAlign.center,
                style: const TextStyle(
                  color: AppColors.text,
                  fontSize: 24,
                  fontWeight: FontWeight.w600,
                ),
              ),
              const SizedBox(height: 20),
              Center(
                child: SizedBox.square(
                  dimension: 88,
                  child: IconButton.filled(
                    key: const Key('voiceRecordButton'),
                    tooltip: _isRecording
                        ? strings.stopRecording
                        : strings.record,
                    onPressed: _uploading
                        ? null
                        : (_isRecording
                              ? _stop
                              : (hasRecording ? null : _start)),
                    style: IconButton.styleFrom(
                      backgroundColor: _isRecording
                          ? AppColors.darkAccent
                          : AppColors.accent,
                      foregroundColor: Colors.white,
                    ),
                    iconSize: 42,
                    icon: Icon(
                      _isRecording ? Icons.stop_rounded : Icons.mic_rounded,
                    ),
                  ),
                ),
              ),
              const SizedBox(height: 16),
              Text(
                _isRecording
                    ? strings.stopWhenDone
                    : hasRecording
                    ? strings.voiceRecorded
                    : strings.tapMicToStart,
                textAlign: TextAlign.center,
                style: Theme.of(context).textTheme.bodyMedium,
              ),
              const Spacer(),
              if (_error != null) ...[
                Text(
                  _error!,
                  textAlign: TextAlign.center,
                  style: const TextStyle(color: AppColors.error),
                ),
                const SizedBox(height: 12),
              ],
              if (hasRecording)
                Row(
                  children: [
                    Expanded(
                      child: OutlinedButton(
                        onPressed: _uploading ? null : _recordAgain,
                        child: Text(strings.recordAgain),
                      ),
                    ),
                    const SizedBox(width: 12),
                    Expanded(
                      child: FilledButton(
                        key: const Key('continueFromVoiceButton'),
                        onPressed: _uploading ? null : _continue,
                        child: _uploading
                            ? const SizedBox.square(
                                dimension: 22,
                                child: CircularProgressIndicator(
                                  strokeWidth: 2,
                                  color: Colors.white,
                                ),
                              )
                            : Text(strings.generateCatalogue),
                      ),
                    ),
                  ],
                )
              else
                Text(
                  strings.maximumTwoMinutes,
                  textAlign: TextAlign.center,
                  style: const TextStyle(
                    color: AppColors.mutedText,
                    fontSize: 12,
                  ),
                ),
            ],
          ),
        ),
      ),
    );
  }
}

class _Waveform extends StatelessWidget {
  const _Waveform({required this.tick});

  final int tick;

  @override
  Widget build(BuildContext context) {
    const heights = [18.0, 30.0, 42.0, 24.0, 36.0, 20.0, 46.0, 28.0, 38.0];
    return SizedBox(
      height: 48,
      child: Row(
        mainAxisAlignment: MainAxisAlignment.center,
        crossAxisAlignment: CrossAxisAlignment.center,
        children: [
          for (var index = 0; index < heights.length; index++)
            AnimatedContainer(
              duration: const Duration(milliseconds: 280),
              width: 4,
              height: heights[(index + tick) % heights.length],
              margin: const EdgeInsets.symmetric(horizontal: 3),
              decoration: BoxDecoration(
                color: AppColors.accent.withValues(alpha: 0.72),
                borderRadius: BorderRadius.circular(2),
              ),
            ),
        ],
      ),
    );
  }
}

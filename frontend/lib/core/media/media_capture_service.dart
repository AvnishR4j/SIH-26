import 'dart:io';

import 'package:flutter/services.dart';

import '../../features/catalogue/models/catalogue_models.dart';

abstract interface class MediaCaptureService {
  Future<LocalMediaFile?> capturePhoto();
  Future<LocalMediaFile?> pickPhoto();
  Future<void> startVoiceRecording();
  Future<LocalMediaFile?> stopVoiceRecording();
  Future<void> cancelVoiceRecording();
  Future<LocalMediaFile> createDemoPhoto();
}

class PlatformMediaCaptureService implements MediaCaptureService {
  static const _channel = MethodChannel('in.kalasetu/media');

  @override
  Future<LocalMediaFile?> capturePhoto() => _photo('capturePhoto');

  @override
  Future<LocalMediaFile?> pickPhoto() => _photo('pickPhoto');

  @override
  Future<void> startVoiceRecording() =>
      _channel.invokeMethod<void>('startVoiceRecording');

  @override
  Future<LocalMediaFile?> stopVoiceRecording() async {
    final path = await _channel.invokeMethod<String>('stopVoiceRecording');
    return path == null
        ? null
        : LocalMediaFile(path: path, mimeType: 'audio/mp4');
  }

  @override
  Future<void> cancelVoiceRecording() =>
      _channel.invokeMethod<void>('cancelVoiceRecording');

  @override
  Future<LocalMediaFile> createDemoPhoto() async {
    final file = File(
      '${Directory.systemTemp.path}${Platform.pathSeparator}kalasetu_demo_photo.jpg',
    );
    if (!await file.exists()) {
      await file.writeAsBytes(const [255, 216, 255, 217]);
    }
    return LocalMediaFile(path: file.path, mimeType: 'image/jpeg');
  }

  Future<LocalMediaFile?> _photo(String method) async {
    final path = await _channel.invokeMethod<String>(method);
    return path == null
        ? null
        : LocalMediaFile(path: path, mimeType: _photoMimeType(path));
  }

  String _photoMimeType(String path) {
    final extension = path.split('.').last.toLowerCase();
    return switch (extension) {
      'png' => 'image/png',
      'webp' => 'image/webp',
      _ => 'image/jpeg',
    };
  }
}

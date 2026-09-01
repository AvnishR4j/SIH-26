import 'dart:io';

import 'package:flutter/material.dart';
import 'package:flutter/services.dart';

import '../../../core/api/api_client.dart';
import '../../../core/localization/app_language.dart';
import '../../../core/localization/app_strings.dart';
import '../../../core/theme/app_theme.dart';
import '../controllers/catalogue_flow_controller.dart';
import '../models/catalogue_models.dart';
import 'voice_description_screen.dart';

class ProductPhotoScreen extends StatefulWidget {
  const ProductPhotoScreen({
    super.key,
    required this.controller,
    required this.language,
  });

  final CatalogueFlowController controller;
  final AppLanguage language;

  @override
  State<ProductPhotoScreen> createState() => _ProductPhotoScreenState();
}

class _ProductPhotoScreenState extends State<ProductPhotoScreen> {
  LocalMediaFile? _photo;
  bool _busy = false;
  String? _error;

  Future<void> _getPhoto({required bool gallery}) async {
    setState(() => _error = null);
    try {
      final photo = gallery
          ? await widget.controller.pickPhoto()
          : await widget.controller.capturePhoto();
      if (mounted && photo != null) setState(() => _photo = photo);
    } on PlatformException catch (error) {
      if (mounted) {
        setState(
          () => _error =
              error.message ?? AppStrings(widget.language).photoCaptureFailed,
        );
      }
    }
  }

  Future<void> _useDemoPhoto() async {
    setState(() => _error = null);
    try {
      final photo = await widget.controller.media.createDemoPhoto();
      if (mounted) setState(() => _photo = photo);
    } on PlatformException catch (error) {
      if (mounted) {
        setState(
          () => _error =
              error.message ?? AppStrings(widget.language).demoPhotoFailed,
        );
      }
    }
  }

  Future<void> _continue() async {
    final photo = _photo;
    if (photo == null || _busy) return;
    setState(() {
      _busy = true;
      _error = null;
    });
    try {
      await widget.controller.uploadPhotoAndStartEnhancement(photo);
      if (!mounted) return;
      await Navigator.of(context).push(
        MaterialPageRoute<void>(
          builder: (_) => VoiceDescriptionScreen(
            controller: widget.controller,
            language: widget.language,
          ),
        ),
      );
    } on ApiException catch (error) {
      if (error.code == 'CONSENT_REQUIRED' && mounted) {
        final accepted = await _requestConsent();
        if (accepted && mounted) {
          setState(() => _busy = false);
          await _continue();
          return;
        }
      } else if (mounted) {
        setState(() => _error = _messageFor(error.code));
      }
    } finally {
      if (mounted) setState(() => _busy = false);
    }
  }

  Future<bool> _requestConsent() async {
    final strings = AppStrings(widget.language);
    final result = await showModalBottomSheet<bool>(
      context: context,
      backgroundColor: AppColors.surface,
      showDragHandle: true,
      builder: (context) => SafeArea(
        child: Padding(
          padding: const EdgeInsets.fromLTRB(24, 8, 24, 24),
          child: Column(
            mainAxisSize: MainAxisSize.min,
            crossAxisAlignment: CrossAxisAlignment.stretch,
            children: [
              Text(
                strings.mediaConsentTitle,
                style: Theme.of(context).textTheme.titleLarge,
              ),
              const SizedBox(height: 10),
              Text(strings.mediaConsentBody),
              const SizedBox(height: 20),
              FilledButton(
                onPressed: () => Navigator.of(context).pop(true),
                child: Text(strings.consentAgree),
              ),
            ],
          ),
        ),
      ),
    );
    if (result != true) return false;
    await widget.controller.acceptMediaProcessingConsent();
    return true;
  }

  String _messageFor(String code) {
    final strings = AppStrings(widget.language);
    return switch (code) {
      'UPLOAD_TOO_LARGE' => strings.photoTooLarge,
      'UNSUPPORTED_MEDIA_TYPE' => strings.unsupportedPhoto,
      'STORAGE_UNAVAILABLE' => strings.photoStorageFailed,
      'IMAGE_TOO_SMALL' ||
      'IMAGE_NOT_CLEAR' ||
      'IMAGE_TOO_DARK' ||
      'IMAGE_TOO_BRIGHT' ||
      'IMAGE_BLURRY' ||
      'IMAGE_SUBJECT_NOT_CLEAR' => strings.photoNeedsRetake,
      _ => strings.photoUploadFailed,
    };
  }

  @override
  Widget build(BuildContext context) {
    final photo = _photo;
    final strings = AppStrings(widget.language);
    return Scaffold(
      appBar: AppBar(
        backgroundColor: AppColors.background,
        surfaceTintColor: Colors.transparent,
        title: Text(strings.productPhoto),
      ),
      body: SafeArea(
        child: photo == null ? _buildCapture() : _buildPreview(photo),
      ),
    );
  }

  Widget _buildCapture() {
    final strings = AppStrings(widget.language);
    return Padding(
      padding: const EdgeInsets.fromLTRB(24, 18, 24, 28),
      child: Column(
        crossAxisAlignment: CrossAxisAlignment.stretch,
        children: [
          Text(
            strings.photoLighting,
            style: Theme.of(context).textTheme.headlineSmall,
          ),
          const SizedBox(height: 8),
          Text(
            strings.photoFraming,
            style: Theme.of(context).textTheme.bodyMedium,
          ),
          const SizedBox(height: 24),
          Expanded(
            child: Container(
              decoration: BoxDecoration(
                color: const Color(0xFF332F2B),
                borderRadius: BorderRadius.circular(10),
              ),
              child: const Center(
                child: Icon(
                  Icons.center_focus_strong,
                  size: 68,
                  color: Color(0x99FFFFFF),
                ),
              ),
            ),
          ),
          if (_error != null) ...[
            const SizedBox(height: 12),
            Text(_error!, style: const TextStyle(color: AppColors.error)),
          ],
          const SizedBox(height: 22),
          Row(
            mainAxisAlignment: MainAxisAlignment.spaceBetween,
            children: [
              IconButton.filledTonal(
                tooltip: strings.chooseFromGallery,
                onPressed: () => _getPhoto(gallery: true),
                icon: const Icon(Icons.photo_library_outlined),
              ),
              SizedBox.square(
                dimension: 76,
                child: IconButton.filled(
                  key: const Key('capturePhotoButton'),
                  tooltip: strings.takePhoto,
                  onPressed: () => _getPhoto(gallery: false),
                  style: IconButton.styleFrom(
                    backgroundColor: AppColors.accent,
                    foregroundColor: Colors.white,
                  ),
                  iconSize: 38,
                  icon: const Icon(Icons.camera_alt_outlined),
                ),
              ),
              const SizedBox.square(dimension: 48),
            ],
          ),
          const SizedBox(height: 12),
          OutlinedButton.icon(
            key: const Key('useDemoPhotoButton'),
            onPressed: _useDemoPhoto,
            icon: const Icon(Icons.auto_awesome_outlined),
            label: Text(strings.useDemoPhoto),
          ),
        ],
      ),
    );
  }

  Widget _buildPreview(LocalMediaFile photo) {
    final strings = AppStrings(widget.language);
    return Padding(
      padding: const EdgeInsets.fromLTRB(24, 18, 24, 28),
      child: Column(
        crossAxisAlignment: CrossAxisAlignment.stretch,
        children: [
          Text(
            strings.reviewPhoto,
            style: Theme.of(context).textTheme.headlineSmall,
          ),
          const SizedBox(height: 20),
          Expanded(
            child: ClipRRect(
              borderRadius: BorderRadius.circular(10),
              child: Image.file(
                File(photo.path),
                fit: BoxFit.contain,
                errorBuilder: (_, _, _) => const ColoredBox(
                  color: AppColors.surface,
                  child: Center(
                    child: Icon(Icons.image_not_supported_outlined),
                  ),
                ),
              ),
            ),
          ),
          if (_error != null) ...[
            const SizedBox(height: 12),
            Text(_error!, style: const TextStyle(color: AppColors.error)),
          ],
          const SizedBox(height: 20),
          Row(
            children: [
              Expanded(
                child: OutlinedButton(
                  onPressed: _busy ? null : () => setState(() => _photo = null),
                  child: Text(strings.retake),
                ),
              ),
              const SizedBox(width: 12),
              Expanded(
                child: FilledButton(
                  key: const Key('continueFromPhotoButton'),
                  onPressed: _busy ? null : _continue,
                  child: _busy
                      ? const SizedBox.square(
                          dimension: 22,
                          child: CircularProgressIndicator(
                            strokeWidth: 2,
                            color: Colors.white,
                          ),
                        )
                      : Text(strings.continueLabel),
                ),
              ),
            ],
          ),
        ],
      ),
    );
  }
}

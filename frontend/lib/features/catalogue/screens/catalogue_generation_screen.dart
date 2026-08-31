import 'dart:async';
import 'dart:io';

import 'package:flutter/material.dart';

import '../../../core/localization/app_language.dart';
import '../../../core/localization/app_strings.dart';
import '../../../core/theme/app_theme.dart';
import '../controllers/catalogue_flow_controller.dart';
import '../models/catalogue_models.dart';
import 'catalogue_review_screen.dart';

class CatalogueGenerationScreen extends StatefulWidget {
  const CatalogueGenerationScreen({
    super.key,
    required this.controller,
    required this.initialOperation,
    required this.language,
  });

  final CatalogueFlowController controller;
  final ApiOperation initialOperation;
  final AppLanguage language;

  @override
  State<CatalogueGenerationScreen> createState() =>
      _CatalogueGenerationScreenState();
}

class _CatalogueGenerationScreenState extends State<CatalogueGenerationScreen> {
  late ApiOperation _operation;
  late DateTime _foregroundDeadline;
  Timer? _pollTimer;
  bool _polling = false;
  bool _timedOut = false;
  bool _success = false;
  String? _error;

  @override
  void initState() {
    super.initState();
    _operation = widget.initialOperation;
    _foregroundDeadline = DateTime.now().add(const Duration(seconds: 60));
    _scheduleNextPoll();
  }

  @override
  void dispose() {
    _pollTimer?.cancel();
    super.dispose();
  }

  void _scheduleNextPoll() {
    _pollTimer?.cancel();
    if (!_operation.isPending || _success || _timedOut) return;
    if (DateTime.now().isAfter(_foregroundDeadline)) {
      setState(() => _timedOut = true);
      return;
    }
    final delay = _operation.pollAfterSeconds.clamp(1, 10);
    _pollTimer = Timer(Duration(seconds: delay), _poll);
  }

  Future<void> _poll() async {
    if (_polling || !mounted) return;
    _polling = true;
    try {
      final operation = await widget.controller.getOperation(_operation.id);
      if (!mounted) return;
      setState(() {
        _operation = operation;
        _error = null;
      });
      if (operation.status == 'succeeded') {
        await widget.controller.refreshDraft();
        if (mounted) setState(() => _success = true);
      } else if (operation.status == 'failed') {
        if (mounted) {
          setState(() {
            _error =
                operation.error?.message ??
                AppStrings(widget.language).generationFailed;
          });
        }
      } else {
        _scheduleNextPoll();
      }
    } catch (_) {
      if (mounted) {
        setState(() {
          _error = AppStrings(widget.language).connectionFailed;
        });
      }
    } finally {
      _polling = false;
    }
  }

  Future<void> _retry() async {
    setState(() {
      _error = null;
      _timedOut = false;
      _foregroundDeadline = DateTime.now().add(const Duration(seconds: 60));
    });
    try {
      if (_operation.status == 'failed') {
        final operation = await widget.controller.retryFailedGeneration();
        if (!mounted) return;
        setState(() => _operation = operation);
      } else {
        await _poll();
      }
      _scheduleNextPoll();
    } catch (_) {
      if (mounted) {
        setState(() => _error = AppStrings(widget.language).retryFailed);
      }
    }
  }

  void _leave() {
    _pollTimer?.cancel();
    Navigator.of(context).popUntil((route) => route.isFirst);
  }

  Future<void> _review() async {
    _pollTimer?.cancel();
    await Navigator.of(context).pushReplacement(
      MaterialPageRoute<void>(
        builder: (_) => CatalogueReviewScreen(
          controller: widget.controller,
          language: widget.language,
        ),
      ),
    );
  }

  @override
  Widget build(BuildContext context) {
    final imagePath = widget.controller.state.localImagePath;
    final strings = AppStrings(widget.language);
    return Scaffold(
      appBar: AppBar(
        backgroundColor: AppColors.background,
        surfaceTintColor: Colors.transparent,
        automaticallyImplyLeading: false,
        title: Text(strings.generatingCatalogue),
      ),
      body: SafeArea(
        child: Padding(
          padding: const EdgeInsets.fromLTRB(24, 20, 24, 28),
          child: Column(
            crossAxisAlignment: CrossAxisAlignment.stretch,
            children: [
              const Spacer(),
              Center(
                child: ClipRRect(
                  borderRadius: BorderRadius.circular(10),
                  child: SizedBox.square(
                    dimension: 220,
                    child: imagePath == null
                        ? const ColoredBox(
                            color: AppColors.surface,
                            child: Icon(Icons.image_outlined, size: 56),
                          )
                        : Image.file(
                            File(imagePath),
                            fit: BoxFit.cover,
                            errorBuilder: (_, _, _) => const ColoredBox(
                              color: AppColors.surface,
                              child: Icon(Icons.image_outlined, size: 56),
                            ),
                          ),
                  ),
                ),
              ),
              const SizedBox(height: 32),
              if (_success) ...[
                const Icon(
                  Icons.check_circle_outline,
                  color: AppColors.accent,
                  size: 44,
                ),
                const SizedBox(height: 16),
                Text(
                  strings.catalogueReady,
                  textAlign: TextAlign.center,
                  style: Theme.of(context).textTheme.headlineSmall,
                ),
                const SizedBox(height: 8),
                Text(
                  strings.readyForReview,
                  textAlign: TextAlign.center,
                  style: Theme.of(context).textTheme.bodyMedium,
                ),
              ] else if (_error != null) ...[
                Text(
                  _error!,
                  textAlign: TextAlign.center,
                  style: Theme.of(context).textTheme.titleLarge,
                ),
                const SizedBox(height: 18),
                OutlinedButton(
                  onPressed: _retry,
                  child: Text(strings.tryAgain),
                ),
              ] else if (_timedOut) ...[
                Text(
                  strings.workContinues,
                  textAlign: TextAlign.center,
                  style: Theme.of(context).textTheme.headlineSmall,
                ),
                const SizedBox(height: 8),
                Text(
                  strings.reopenDraftLater,
                  textAlign: TextAlign.center,
                  style: Theme.of(context).textTheme.bodyMedium,
                ),
              ] else ...[
                const Center(
                  child: CircularProgressIndicator(color: AppColors.accent),
                ),
                const SizedBox(height: 24),
                Text(
                  strings.catalogueBeingPrepared,
                  textAlign: TextAlign.center,
                  style: Theme.of(context).textTheme.headlineSmall,
                ),
                const SizedBox(height: 8),
                Text(
                  strings.bilingualDescription,
                  textAlign: TextAlign.center,
                  style: Theme.of(context).textTheme.bodyMedium,
                ),
              ],
              const Spacer(),
              if (_success)
                FilledButton(
                  key: const Key('reviewGeneratedCatalogueButton'),
                  onPressed: _review,
                  child: Text(
                    widget.language == AppLanguage.hindi
                        ? 'कैटलॉग की समीक्षा करें'
                        : 'Review catalogue',
                  ),
                )
              else
                TextButton(onPressed: _leave, child: Text(strings.viewLater)),
            ],
          ),
        ),
      ),
    );
  }
}

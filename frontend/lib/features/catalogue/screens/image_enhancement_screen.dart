import 'package:flutter/material.dart';

import '../../../core/api/api_client.dart';
import '../../../core/localization/app_language.dart';
import '../../../core/theme/app_theme.dart';
import '../../../shared/widgets/product_image.dart';
import '../controllers/catalogue_flow_controller.dart';
import 'pricing_assistant_screen.dart';

class ImageEnhancementScreen extends StatefulWidget {
  const ImageEnhancementScreen({
    super.key,
    required this.controller,
    required this.language,
  });

  final CatalogueFlowController controller;
  final AppLanguage language;

  @override
  State<ImageEnhancementScreen> createState() => _ImageEnhancementScreenState();
}

class _ImageEnhancementScreenState extends State<ImageEnhancementScreen> {
  bool _loading = true;
  bool _saving = false;
  String? _selected;
  String? _error;

  bool get _hi => widget.language == AppLanguage.hindi;
  String _t(String hi, String en) => _hi ? hi : en;

  @override
  void initState() {
    super.initState();
    _loadEnhancement();
  }

  Future<void> _loadEnhancement() async {
    setState(() {
      _loading = true;
      _error = null;
    });
    try {
      await widget.controller.waitForEnhancement();
    } on ApiException catch (error) {
      _error = error.message;
    } catch (_) {
      _error = _t(
        'सुधरी हुई फोटो अभी तैयार नहीं हो सकी।',
        'The enhanced photo is not ready yet.',
      );
    } finally {
      if (mounted) setState(() => _loading = false);
    }
  }

  Future<void> _retry() async {
    try {
      await widget.controller.retryEnhancement();
      await _loadEnhancement();
    } on ApiException catch (error) {
      if (mounted) setState(() => _error = error.message);
    }
  }

  Future<void> _continue() async {
    final selected = _selected;
    if (selected == null || _saving) return;
    setState(() {
      _saving = true;
      _error = null;
    });
    try {
      await widget.controller.selectImageVariant(selected);
      if (!mounted) return;
      await Navigator.of(context).pushReplacement(
        MaterialPageRoute<void>(
          builder: (_) => PricingAssistantScreen(
            controller: widget.controller,
            language: widget.language,
          ),
        ),
      );
    } on ApiException catch (error) {
      if (mounted) setState(() => _error = error.message);
    } finally {
      if (mounted) setState(() => _saving = false);
    }
  }

  @override
  Widget build(BuildContext context) {
    final image = widget.controller.state.draft.images.first;
    final succeeded =
        image.enhancementStatus == 'succeeded' && image.enhancedUrl != null;
    return Scaffold(
      appBar: AppBar(
        backgroundColor: AppColors.background,
        surfaceTintColor: Colors.transparent,
        title: Text(_t('मार्केटप्लेस फोटो', 'Marketplace-ready photo')),
      ),
      body: SafeArea(
        child: ListView(
          padding: const EdgeInsets.fromLTRB(24, 16, 24, 112),
          children: [
            Text(
              _t('कौन-सी फोटो इस्तेमाल करें?', 'Which photo should be used?'),
              style: Theme.of(context).textTheme.headlineSmall,
            ),
            const SizedBox(height: 8),
            Text(
              _t(
                'मूल फोटो हमेशा सुरक्षित रहेगी। कोई विकल्प पहले से नहीं चुना गया है।',
                'Your original photo stays preserved. No option is selected for you.',
              ),
              style: Theme.of(context).textTheme.bodyMedium,
            ),
            const SizedBox(height: 20),
            _ImageChoice(
              label: _t('मूल फोटो', 'Original'),
              selected: _selected == 'original',
              onTap: () => setState(() => _selected = 'original'),
              child: ProductImage(
                localPath: widget.controller.state.localImagePath,
                networkUrl: image.originalUrl,
              ),
            ),
            const SizedBox(height: 18),
            if (_loading)
              const Padding(
                padding: EdgeInsets.symmetric(vertical: 48),
                child: Center(
                  child: CircularProgressIndicator(color: AppColors.accent),
                ),
              )
            else if (succeeded)
              _ImageChoice(
                label: _t('AI से सुधरी फोटो', 'AI-enhanced'),
                selected: _selected == 'enhanced',
                onTap: () => setState(() => _selected = 'enhanced'),
                child: ProductImage(
                  networkUrl: image.enhancedUrl,
                  localPath: widget.controller.state.localImagePath,
                  preferNetwork: true,
                ),
              )
            else ...[
              Text(
                _t(
                  'सुधरी फोटो उपलब्ध नहीं है। आप मूल फोटो के साथ आगे बढ़ सकते हैं।',
                  'The enhanced photo is unavailable. You can continue with the original.',
                ),
                style: const TextStyle(color: AppColors.text),
              ),
              const SizedBox(height: 10),
              OutlinedButton.icon(
                onPressed: _retry,
                icon: const Icon(Icons.refresh),
                label: Text(_t('फिर सुधारें', 'Retry enhancement')),
              ),
            ],
            if (_error != null) ...[
              const SizedBox(height: 14),
              Text(_error!, style: const TextStyle(color: AppColors.error)),
            ],
          ],
        ),
      ),
      bottomNavigationBar: SafeArea(
        child: Padding(
          padding: const EdgeInsets.fromLTRB(24, 10, 24, 18),
          child: FilledButton(
            key: const Key('continueFromImageSelectionButton'),
            onPressed: _selected == null || _saving ? null : _continue,
            child: _saving
                ? const SizedBox.square(
                    dimension: 22,
                    child: CircularProgressIndicator(
                      strokeWidth: 2,
                      color: Colors.white,
                    ),
                  )
                : Text(_t('लागत और कीमत बताएं', 'Continue to pricing')),
          ),
        ),
      ),
    );
  }
}

class _ImageChoice extends StatelessWidget {
  const _ImageChoice({
    required this.label,
    required this.selected,
    required this.onTap,
    required this.child,
  });

  final String label;
  final bool selected;
  final VoidCallback onTap;
  final Widget child;

  @override
  Widget build(BuildContext context) {
    return InkWell(
      onTap: onTap,
      borderRadius: BorderRadius.circular(8),
      child: Container(
        padding: const EdgeInsets.all(8),
        decoration: BoxDecoration(
          border: Border.all(
            color: selected ? AppColors.accent : AppColors.border,
            width: selected ? 2 : 1,
          ),
          borderRadius: BorderRadius.circular(8),
        ),
        child: Column(
          crossAxisAlignment: CrossAxisAlignment.stretch,
          children: [
            AspectRatio(aspectRatio: 4 / 3, child: child),
            const SizedBox(height: 10),
            Row(
              children: [
                Expanded(
                  child: Text(
                    label,
                    style: const TextStyle(fontWeight: FontWeight.w700),
                  ),
                ),
                if (selected)
                  const Icon(Icons.check_circle, color: AppColors.accent),
              ],
            ),
          ],
        ),
      ),
    );
  }
}

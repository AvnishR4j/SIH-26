import 'package:flutter/material.dart';

import '../../../core/api/api_client.dart';
import '../../../core/localization/app_language.dart';
import '../../../core/theme/app_theme.dart';
import '../../../shared/widgets/product_image.dart';
import '../controllers/catalogue_flow_controller.dart';
import '../models/catalogue_models.dart';
import 'image_enhancement_screen.dart';

class CatalogueReviewScreen extends StatefulWidget {
  const CatalogueReviewScreen({
    super.key,
    required this.controller,
    required this.language,
  });

  final CatalogueFlowController controller;
  final AppLanguage language;

  @override
  State<CatalogueReviewScreen> createState() => _CatalogueReviewScreenState();
}

class _CatalogueReviewScreenState extends State<CatalogueReviewScreen> {
  final _formKey = GlobalKey<FormState>();
  late final Map<String, TextEditingController> _fields;
  bool _saving = false;
  String? _error;

  bool get _hi => widget.language == AppLanguage.hindi;
  String _t(String hi, String en) => _hi ? hi : en;

  @override
  void initState() {
    super.initState();
    final draft = widget.controller.state.draft;
    final listing = draft.listing!;
    final facts = draft.fields;
    _fields = {
      'titleHi': TextEditingController(text: listing.titleHi),
      'titleEn': TextEditingController(text: listing.titleEn),
      'descriptionHi': TextEditingController(text: listing.descriptionHi),
      'descriptionEn': TextEditingController(text: listing.descriptionEn),
      'productType': TextEditingController(text: facts.productType),
      'material': TextEditingController(text: facts.material),
      'technique': TextEditingController(text: facts.technique),
      'color': TextEditingController(text: facts.color),
      'dimensions': TextEditingController(text: facts.dimensions),
      'quantity': TextEditingController(
        text: facts.quantityAvailable?.toString(),
      ),
      'productionDays': TextEditingController(
        text: facts.productionTimeDays?.toString(),
      ),
      'care': TextEditingController(text: facts.care),
      'origin': TextEditingController(text: facts.origin),
    };
  }

  @override
  void dispose() {
    for (final controller in _fields.values) {
      controller.dispose();
    }
    super.dispose();
  }

  String? _required(String? value) => value == null || value.trim().isEmpty
      ? _t('यह जानकारी ज़रूरी है', 'This information is required')
      : null;

  Future<void> _continue() async {
    if (!_formKey.currentState!.validate() || _saving) return;
    setState(() {
      _saving = true;
      _error = null;
    });
    try {
      final current = widget.controller.state.draft;
      final listing = current.listing!;
      await widget.controller.updateDraft(
        DraftFields(
          productType: _fields['productType']!.text.trim(),
          material: _fields['material']!.text.trim(),
          technique: _fields['technique']!.text.trim(),
          color: _fields['color']!.text.trim(),
          dimensions: _fields['dimensions']!.text.trim(),
          quantityAvailable: int.parse(_fields['quantity']!.text),
          productionTimeDays: int.parse(_fields['productionDays']!.text),
          care: _fields['care']!.text.trim(),
          origin: _fields['origin']!.text.trim(),
        ),
        listing.copyWith(
          titleHi: _fields['titleHi']!.text.trim(),
          titleEn: _fields['titleEn']!.text.trim(),
          descriptionHi: _fields['descriptionHi']!.text.trim(),
          descriptionEn: _fields['descriptionEn']!.text.trim(),
        ),
      );
      if (!mounted) return;
      await Navigator.of(context).pushReplacement(
        MaterialPageRoute<void>(
          builder: (_) => ImageEnhancementScreen(
            controller: widget.controller,
            language: widget.language,
          ),
        ),
      );
    } on ApiException catch (error) {
      if (error.code == 'VERSION_CONFLICT') {
        await widget.controller.refreshDraft();
      }
      if (mounted) setState(() => _error = error.message);
    } finally {
      if (mounted) setState(() => _saving = false);
    }
  }

  @override
  Widget build(BuildContext context) {
    final draft = widget.controller.state.draft;
    final image = draft.images.first;
    return Scaffold(
      appBar: AppBar(
        backgroundColor: AppColors.background,
        surfaceTintColor: Colors.transparent,
        title: Text(_t('कैटलॉग की समीक्षा', 'Review catalogue')),
      ),
      body: SafeArea(
        child: Form(
          key: _formKey,
          child: ListView(
            padding: const EdgeInsets.fromLTRB(24, 16, 24, 112),
            children: [
              SizedBox(
                height: 150,
                child: ProductImage(
                  localPath: widget.controller.state.localImagePath,
                  networkUrl: image.originalUrl,
                  fit: BoxFit.contain,
                ),
              ),
              const SizedBox(height: 22),
              Text(
                _t('नाम और विवरण', 'Titles and descriptions'),
                style: Theme.of(context).textTheme.titleLarge,
              ),
              const SizedBox(height: 14),
              _input('titleHi', 'हिंदी शीर्षक', required: true),
              _input('titleEn', 'English title', required: true),
              _input('descriptionHi', 'हिंदी विवरण', required: true, lines: 3),
              _input(
                'descriptionEn',
                'English description',
                required: true,
                lines: 3,
              ),
              const Divider(height: 36, color: AppColors.divider),
              Text(
                _t('उत्पाद की जानकारी', 'Product details'),
                style: Theme.of(context).textTheme.titleLarge,
              ),
              const SizedBox(height: 14),
              _input(
                'productType',
                _t('उत्पाद प्रकार', 'Product type'),
                required: true,
              ),
              _input('material', _t('सामग्री', 'Material'), required: true),
              _input('technique', _t('तकनीक', 'Technique'), required: true),
              _input(
                'dimensions',
                _t('आकार / नाप', 'Dimensions'),
                required: true,
              ),
              Row(
                children: [
                  Expanded(
                    child: _input(
                      'quantity',
                      _t('मात्रा', 'Quantity'),
                      required: true,
                      number: true,
                    ),
                  ),
                  const SizedBox(width: 12),
                  Expanded(
                    child: _input(
                      'productionDays',
                      _t('बनाने के दिन', 'Production days'),
                      required: true,
                      number: true,
                    ),
                  ),
                ],
              ),
              _input('color', _t('रंग (वैकल्पिक)', 'Colour (optional)')),
              _input('care', _t('देखभाल (वैकल्पिक)', 'Care (optional)')),
              _input('origin', _t('स्थान (वैकल्पिक)', 'Origin (optional)')),
              if (_error != null) ...[
                const SizedBox(height: 4),
                Text(_error!, style: const TextStyle(color: AppColors.error)),
              ],
            ],
          ),
        ),
      ),
      bottomNavigationBar: SafeArea(
        child: Padding(
          padding: const EdgeInsets.fromLTRB(24, 10, 24, 18),
          child: FilledButton(
            key: const Key('continueFromReviewButton'),
            onPressed: _saving ? null : _continue,
            child: _saving
                ? const SizedBox.square(
                    dimension: 22,
                    child: CircularProgressIndicator(
                      strokeWidth: 2,
                      color: Colors.white,
                    ),
                  )
                : Text(_t('फोटो चुनें', 'Choose product image')),
          ),
        ),
      ),
    );
  }

  Widget _input(
    String key,
    String label, {
    bool required = false,
    bool number = false,
    int lines = 1,
  }) {
    return Padding(
      padding: const EdgeInsets.only(bottom: 12),
      child: TextFormField(
        controller: _fields[key],
        decoration: InputDecoration(labelText: label),
        keyboardType: number ? TextInputType.number : TextInputType.text,
        maxLines: lines,
        validator: required
            ? (value) {
                final missing = _required(value);
                if (missing != null) return missing;
                if (number && int.tryParse(value!) == null) {
                  return _t('सही संख्या डालें', 'Enter a valid number');
                }
                return null;
              }
            : null,
      ),
    );
  }
}

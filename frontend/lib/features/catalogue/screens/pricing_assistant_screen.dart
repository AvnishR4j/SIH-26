import 'package:flutter/material.dart';
import 'package:flutter/services.dart';

import '../../../core/api/api_client.dart';
import '../../../core/localization/app_language.dart';
import '../../../core/theme/app_theme.dart';
import '../../../core/utils/money.dart';
import '../controllers/catalogue_flow_controller.dart';
import '../models/catalogue_models.dart';
import 'final_approval_screen.dart';

class PricingAssistantScreen extends StatefulWidget {
  const PricingAssistantScreen({
    super.key,
    required this.controller,
    required this.language,
  });

  final CatalogueFlowController controller;
  final AppLanguage language;

  @override
  State<PricingAssistantScreen> createState() => _PricingAssistantScreenState();
}

class _PricingAssistantScreenState extends State<PricingAssistantScreen> {
  final _costFormKey = GlobalKey<FormState>();
  final _finalFormKey = GlobalKey<FormState>();
  final _material = TextEditingController(text: '300');
  final _hours = TextEditingController(text: '8');
  final _hourlyRate = TextEditingController(text: '50');
  final _packaging = TextEditingController(text: '50');
  final _logistics = TextEditingController(text: '0');
  final _customPrice = TextEditingController();
  final _overrideReason = TextEditingController();
  PricingSuggestion? _suggestion;
  bool _loading = false;
  bool _useRecommended = true;
  String? _error;

  bool get _hi => widget.language == AppLanguage.hindi;
  String _t(String hi, String en) => _hi ? hi : en;

  @override
  void initState() {
    super.initState();
    widget.controller.beginNewPriceSuggestion();
  }

  @override
  void dispose() {
    _material.dispose();
    _hours.dispose();
    _hourlyRate.dispose();
    _packaging.dispose();
    _logistics.dispose();
    _customPrice.dispose();
    _overrideReason.dispose();
    super.dispose();
  }

  String? _moneyValidator(String? value) =>
      Money.rupeesTextToPaise(value ?? '') == null
      ? _t('सही राशि डालें', 'Enter a valid amount')
      : null;

  Future<void> _calculate() async {
    if (!_costFormKey.currentState!.validate() || _loading) return;
    setState(() {
      _loading = true;
      _error = null;
    });
    try {
      final suggestion = await widget.controller.suggestPrice(
        PriceSuggestionInput(
          version: widget.controller.state.draft.version,
          materialCostPaise: Money.rupeesTextToPaise(_material.text)!,
          labourHours: double.parse(_hours.text),
          hourlyRatePaise: Money.rupeesTextToPaise(_hourlyRate.text)!,
          packagingCostPaise: Money.rupeesTextToPaise(_packaging.text)!,
          logisticsBufferPaise: Money.rupeesTextToPaise(_logistics.text)!,
          benchmarkCategory:
              widget.controller.state.draft.fields.productType ??
              widget.controller.state.draft.craftCategory,
          material: widget.controller.state.draft.fields.material,
        ),
      );
      if (mounted) {
        setState(() {
          _suggestion = suggestion;
          _customPrice.text = (suggestion.recommendedPaise / 100)
              .toStringAsFixed(0);
        });
      }
    } on ApiException catch (error) {
      if (mounted) setState(() => _error = error.message);
    } finally {
      if (mounted) setState(() => _loading = false);
    }
  }

  Future<void> _continue() async {
    final suggestion = _suggestion!;
    if (!_finalFormKey.currentState!.validate()) return;
    final price = _useRecommended
        ? suggestion.recommendedPaise
        : Money.rupeesTextToPaise(_customPrice.text)!;
    final outside =
        price < suggestion.suggestedMinPaise ||
        price > suggestion.suggestedMaxPaise;
    if (outside && _overrideReason.text.trim().isEmpty) {
      setState(() {
        _error = _t(
          'सुझाई सीमा से बाहर कीमत के लिए छोटा कारण लिखें।',
          'Add a short reason for a price outside the suggested range.',
        );
      });
      return;
    }
    widget.controller.chooseFinalPrice(
      price,
      outside ? _overrideReason.text.trim() : null,
    );
    await Navigator.of(context).push(
      MaterialPageRoute<void>(
        builder: (_) => FinalApprovalScreen(
          controller: widget.controller,
          language: widget.language,
        ),
      ),
    );
  }

  @override
  Widget build(BuildContext context) {
    final suggestion = _suggestion;
    return Scaffold(
      appBar: AppBar(
        backgroundColor: AppColors.background,
        surfaceTintColor: Colors.transparent,
        title: Text(_t('कीमत की सलाह', 'Price recommendation')),
      ),
      body: SafeArea(
        child: suggestion == null ? _costInput() : _recommendation(suggestion),
      ),
    );
  }

  Widget _costInput() {
    return Form(
      key: _costFormKey,
      child: ListView(
        padding: const EdgeInsets.fromLTRB(24, 16, 24, 28),
        children: [
          Text(
            _t('अपनी लागत बताइए', 'Tell us your costs'),
            style: Theme.of(context).textTheme.headlineSmall,
          ),
          const SizedBox(height: 8),
          Text(
            _t(
              'आपकी लागत और संदर्भ बाज़ार जानकारी से समझाने योग्य कीमत मिलेगी।',
              'Your costs and a dated market reference are used to explain the recommendation.',
            ),
            style: Theme.of(context).textTheme.bodyMedium,
          ),
          const SizedBox(height: 22),
          _amountField(_material, _t('सामग्री की लागत', 'Material cost')),
          _numberField(_hours, _t('काम के घंटे', 'Labour hours')),
          _amountField(
            _hourlyRate,
            _t('प्रति घंटे की दर', 'Hourly labour rate'),
          ),
          _amountField(_packaging, _t('पैकिंग की लागत', 'Packaging cost')),
          _amountField(
            _logistics,
            _t('लॉजिस्टिक्स / बफर', 'Logistics / buffer'),
          ),
          if (_error != null) ...[
            Text(_error!, style: const TextStyle(color: AppColors.error)),
            const SizedBox(height: 12),
          ],
          FilledButton(
            key: const Key('calculatePriceButton'),
            onPressed: _loading ? null : _calculate,
            child: _loading
                ? const SizedBox.square(
                    dimension: 22,
                    child: CircularProgressIndicator(
                      strokeWidth: 2,
                      color: Colors.white,
                    ),
                  )
                : Text(_t('कीमत सुझाएं', 'Suggest a price')),
          ),
        ],
      ),
    );
  }

  Widget _recommendation(PricingSuggestion suggestion) {
    final outside =
        !_useRecommended &&
        Money.rupeesTextToPaise(_customPrice.text) != null &&
        (Money.rupeesTextToPaise(_customPrice.text)! <
                suggestion.suggestedMinPaise ||
            Money.rupeesTextToPaise(_customPrice.text)! >
                suggestion.suggestedMaxPaise);
    return Form(
      key: _finalFormKey,
      child: ListView(
        padding: const EdgeInsets.fromLTRB(24, 16, 24, 28),
        children: [
          Text(
            _t('सुझाई गई सीमा', 'Suggested range'),
            style: Theme.of(context).textTheme.bodyMedium,
          ),
          const SizedBox(height: 4),
          Text(
            '${Money.formatPaise(suggestion.suggestedMinPaise, decimals: false)} – ${Money.formatPaise(suggestion.suggestedMaxPaise, decimals: false)}',
            style: Theme.of(context).textTheme.titleLarge,
          ),
          const SizedBox(height: 22),
          Text(
            _t('सुझाई कीमत', 'Recommended price'),
            style: Theme.of(context).textTheme.bodyMedium,
          ),
          Text(
            Money.formatPaise(suggestion.recommendedPaise, decimals: false),
            style: const TextStyle(
              fontSize: 42,
              fontWeight: FontWeight.w700,
              color: AppColors.text,
            ),
          ),
          const Divider(height: 36, color: AppColors.divider),
          Text(
            _t('यह कैसे तय हुआ?', 'How was this decided?'),
            style: Theme.of(context).textTheme.titleLarge,
          ),
          const SizedBox(height: 10),
          for (final reason in suggestion.reasons)
            Padding(
              padding: const EdgeInsets.only(bottom: 8),
              child: Text('• $reason'),
            ),
          Text(
            '${_t('विश्वास', 'Confidence')}: ${_confidenceLabel(suggestion.confidence)}',
            style: const TextStyle(fontWeight: FontWeight.w600),
          ),
          const SizedBox(height: 6),
          Text(
            '${suggestion.benchmarkSourceLabel} · ${suggestion.benchmarkSourceDate.toIso8601String().substring(0, 10)}',
            style: Theme.of(context).textTheme.bodyMedium,
          ),
          if (suggestion.materialRate case final materialRate?) ...[
            const SizedBox(height: 6),
            Text(
              '${_t('सामग्री दर', 'Material rate')}: '
              '${Money.formatPaise(materialRate.ratePaisePerUnit, decimals: false)} '
              '/ ${materialRate.unit} · ${materialRate.sourceLabel}',
              style: Theme.of(context).textTheme.bodyMedium,
            ),
          ],
          if (suggestion.isDemoData)
            Padding(
              padding: const EdgeInsets.only(top: 8),
              child: Text(
                _t(
                  'यह डेमो/संदर्भ बाज़ार डेटा है, लाइव बाज़ार मूल्य नहीं।',
                  'This uses demo/reference benchmark data, not live market pricing.',
                ),
                style: const TextStyle(
                  color: AppColors.darkAccent,
                  fontWeight: FontWeight.w600,
                ),
              ),
            ),
          const Divider(height: 36, color: AppColors.divider),
          SegmentedButton<bool>(
            segments: [
              ButtonSegment<bool>(
                value: true,
                label: Text(_t('सुझाई कीमत', 'Recommended')),
              ),
              ButtonSegment<bool>(
                value: false,
                label: Text(_t('अपनी कीमत', 'Custom price')),
              ),
            ],
            selected: {_useRecommended},
            onSelectionChanged: (value) {
              setState(() => _useRecommended = value.first);
            },
          ),
          const SizedBox(height: 14),
          if (!_useRecommended) ...[
            _amountField(
              _customPrice,
              _t('अंतिम कीमत', 'Final price'),
              onChanged: (_) => setState(() {}),
            ),
            if (outside)
              TextFormField(
                controller: _overrideReason,
                maxLines: 2,
                decoration: InputDecoration(
                  labelText: _t(
                    'अलग कीमत का कारण',
                    'Reason for different price',
                  ),
                ),
              ),
          ],
          if (_error != null) ...[
            const SizedBox(height: 12),
            Text(_error!, style: const TextStyle(color: AppColors.error)),
          ],
          const SizedBox(height: 22),
          FilledButton(
            key: const Key('continueFromPricingButton'),
            onPressed: _continue,
            child: Text(_t('अंतिम कैटलॉग देखें', 'Review final catalogue')),
          ),
        ],
      ),
    );
  }

  Widget _amountField(
    TextEditingController controller,
    String label, {
    ValueChanged<String>? onChanged,
  }) {
    return Padding(
      padding: const EdgeInsets.only(bottom: 14),
      child: TextFormField(
        controller: controller,
        decoration: InputDecoration(prefixText: '₹ ', labelText: label),
        keyboardType: const TextInputType.numberWithOptions(decimal: true),
        inputFormatters: [FilteringTextInputFormatter.allow(RegExp(r'[0-9.]'))],
        validator: _moneyValidator,
        onChanged: onChanged,
      ),
    );
  }

  Widget _numberField(TextEditingController controller, String label) {
    return Padding(
      padding: const EdgeInsets.only(bottom: 14),
      child: TextFormField(
        controller: controller,
        decoration: InputDecoration(labelText: label),
        keyboardType: const TextInputType.numberWithOptions(decimal: true),
        inputFormatters: [FilteringTextInputFormatter.allow(RegExp(r'[0-9.]'))],
        validator: (value) {
          final number = double.tryParse(value ?? '');
          return number == null || number <= 0
              ? _t('सही घंटे डालें', 'Enter valid hours')
              : null;
        },
      ),
    );
  }

  String _confidenceLabel(String value) => switch (value) {
    'high' => _t('उच्च', 'High'),
    'medium' => _t('मध्यम', 'Medium'),
    'low' => _t('कम', 'Low'),
    _ => value,
  };
}

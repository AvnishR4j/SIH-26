import 'package:flutter/material.dart';

import '../../../core/api/api_client.dart';
import '../../../core/localization/app_language.dart';
import '../../../core/theme/app_theme.dart';
import '../../../core/utils/idempotency_key.dart';
import '../../../core/utils/money.dart';
import '../../../shared/widgets/brand_mark.dart';
import '../../../shared/widgets/product_image.dart';
import '../controllers/catalogue_flow_controller.dart';
import '../models/catalogue_models.dart';

class PublicCatalogueScreen extends StatefulWidget {
  const PublicCatalogueScreen({
    super.key,
    required this.controller,
    required this.publicShareId,
    required this.language,
  });

  final CatalogueFlowController controller;
  final String publicShareId;
  final AppLanguage language;

  @override
  State<PublicCatalogueScreen> createState() => _PublicCatalogueScreenState();
}

class _PublicCatalogueScreenState extends State<PublicCatalogueScreen> {
  final _formKey = GlobalKey<FormState>();
  final _name = TextEditingController();
  final _phone = TextEditingController(text: '+91');
  final _quantity = TextEditingController(text: '1');
  final _message = TextEditingController();
  late String _idempotencyKey;
  ShareCard? _card;
  bool _loading = true;
  bool _submitting = false;
  bool _consent = false;
  bool _submitted = false;
  String? _error;

  bool get _hi => widget.language == AppLanguage.hindi;
  String _t(String hi, String en) => _hi ? hi : en;

  @override
  void initState() {
    super.initState();
    _idempotencyKey = newIdempotencyKey();
    _load();
  }

  @override
  void dispose() {
    _name.dispose();
    _phone.dispose();
    _quantity.dispose();
    _message.dispose();
    super.dispose();
  }

  Future<void> _load() async {
    setState(() {
      _loading = true;
      _error = null;
    });
    try {
      final card = await widget.controller.getShareCard(widget.publicShareId);
      if (mounted) setState(() => _card = card);
    } on ApiException catch (error) {
      if (mounted) setState(() => _error = error.message);
    } finally {
      if (mounted) setState(() => _loading = false);
    }
  }

  Future<void> _submit() async {
    if (!_formKey.currentState!.validate()) return;
    if (!_consent) {
      setState(
        () => _error = _t(
          'संपर्क की सहमति दें।',
          'Please provide contact consent.',
        ),
      );
      return;
    }
    if (_submitting) return;
    setState(() {
      _submitting = true;
      _error = null;
    });
    try {
      await widget.controller.submitEnquiry(
        widget.publicShareId,
        BuyerEnquiryInput(
          buyerName: _name.text.trim(),
          buyerPhone: _phone.text.trim(),
          quantityRequested: int.parse(_quantity.text),
          message: _message.text.trim().isEmpty ? null : _message.text.trim(),
          consentToContact: _consent,
        ),
        idempotencyKey: _idempotencyKey,
      );
      if (mounted) setState(() => _submitted = true);
    } on ApiException catch (error) {
      if (mounted) {
        setState(() {
          _error = error.code == 'RATE_LIMITED'
              ? _t(
                  'कुछ देर बाद फिर कोशिश करें।',
                  'Please wait before trying again.',
                )
              : error.message;
        });
      }
    } finally {
      if (mounted) setState(() => _submitting = false);
    }
  }

  @override
  Widget build(BuildContext context) {
    return Scaffold(
      appBar: AppBar(
        backgroundColor: AppColors.background,
        surfaceTintColor: Colors.transparent,
        title: const Row(
          mainAxisSize: MainAxisSize.min,
          children: [
            BrandMark(compact: true),
            SizedBox(width: 10),
            Text('KalaSetu', style: TextStyle(fontWeight: FontWeight.w700)),
          ],
        ),
      ),
      body: SafeArea(child: _body()),
    );
  }

  Widget _body() {
    if (_loading) {
      return const Center(
        child: CircularProgressIndicator(color: AppColors.accent),
      );
    }
    final card = _card;
    if (card == null) {
      return Center(
        child: Padding(
          padding: const EdgeInsets.all(24),
          child: Column(
            mainAxisSize: MainAxisSize.min,
            children: [
              const Icon(Icons.link_off, size: 44, color: AppColors.mutedText),
              const SizedBox(height: 14),
              Text(
                _t(
                  'यह कैटलॉग उपलब्ध नहीं है।',
                  'This catalogue is unavailable.',
                ),
                textAlign: TextAlign.center,
                style: Theme.of(context).textTheme.titleLarge,
              ),
              const SizedBox(height: 14),
              OutlinedButton(
                onPressed: _load,
                child: Text(_t('फिर कोशिश करें', 'Retry')),
              ),
            ],
          ),
        ),
      );
    }
    return LayoutBuilder(
      builder: (context, constraints) => Align(
        alignment: Alignment.topCenter,
        child: SizedBox(
          width: constraints.maxWidth.clamp(0, 720),
          height: constraints.maxHeight,
          child: ListView(
            padding: const EdgeInsets.fromLTRB(24, 12, 24, 36),
            children: [
              AspectRatio(
                aspectRatio: 1,
                child: ProductImage(
                  networkUrl: card.imageUrl,
                  localPath: widget.controller.state.localImagePath,
                  preferNetwork: true,
                ),
              ),
              const SizedBox(height: 22),
              Text(
                card.title,
                style: Theme.of(context).textTheme.headlineSmall,
              ),
              const SizedBox(height: 10),
              Text(
                Money.formatPaise(card.pricePaise, decimals: false),
                style: const TextStyle(
                  fontSize: 30,
                  fontWeight: FontWeight.w700,
                  color: AppColors.text,
                ),
              ),
              const SizedBox(height: 16),
              Text(
                card.description,
                style: Theme.of(context).textTheme.bodyLarge,
              ),
              const SizedBox(height: 18),
              Text(
                '${_t('उपलब्ध मात्रा', 'Available quantity')}: ${card.quantityAvailable}',
                style: const TextStyle(fontWeight: FontWeight.w600),
              ),
              const Divider(height: 36, color: AppColors.divider),
              Text(
                card.artisan.displayName,
                style: Theme.of(context).textTheme.titleLarge,
              ),
              if (card.artisan.cluster != null)
                Text(
                  card.artisan.cluster!,
                  style: Theme.of(context).textTheme.bodyMedium,
                ),
              if (card.enquiryEnabled) ...[
                const Divider(height: 40, color: AppColors.divider),
                if (_submitted) _success() else _enquiryForm(),
              ],
            ],
          ),
        ),
      ),
    );
  }

  Widget _success() {
    return Column(
      children: [
        const Icon(
          Icons.check_circle_outline,
          size: 48,
          color: AppColors.accent,
        ),
        const SizedBox(height: 12),
        Text(
          _t('आपकी पूछताछ भेज दी गई है', 'Your enquiry has been sent'),
          textAlign: TextAlign.center,
          style: Theme.of(context).textTheme.titleLarge,
        ),
      ],
    );
  }

  Widget _enquiryForm() {
    return Form(
      key: _formKey,
      child: Column(
        crossAxisAlignment: CrossAxisAlignment.stretch,
        children: [
          Text(
            _t('खरीदार पूछताछ', 'Buyer enquiry'),
            style: Theme.of(context).textTheme.headlineSmall,
          ),
          const SizedBox(height: 16),
          TextFormField(
            controller: _name,
            decoration: InputDecoration(labelText: _t('आपका नाम', 'Your name')),
            validator: (value) => value == null || value.trim().isEmpty
                ? _t('नाम डालें', 'Enter your name')
                : null,
          ),
          const SizedBox(height: 12),
          TextFormField(
            controller: _phone,
            keyboardType: TextInputType.phone,
            decoration: InputDecoration(
              labelText: _t('फोन नंबर', 'Phone number'),
            ),
            validator: (value) =>
                !RegExp(r'^\+[1-9]\d{7,14}$').hasMatch(value?.trim() ?? '')
                ? _t(
                    '+91 के साथ सही नंबर डालें',
                    'Enter a valid number with country code',
                  )
                : null,
          ),
          const SizedBox(height: 12),
          TextFormField(
            controller: _quantity,
            keyboardType: TextInputType.number,
            decoration: InputDecoration(
              labelText: _t('कितनी मात्रा चाहिए', 'Quantity requested'),
            ),
            validator: (value) {
              final quantity = int.tryParse(value ?? '');
              return quantity == null || quantity < 1
                  ? _t('सही मात्रा डालें', 'Enter a valid quantity')
                  : null;
            },
          ),
          const SizedBox(height: 12),
          TextFormField(
            controller: _message,
            maxLines: 3,
            decoration: InputDecoration(
              labelText: _t('संदेश (वैकल्पिक)', 'Message (optional)'),
            ),
          ),
          CheckboxListTile(
            value: _consent,
            contentPadding: EdgeInsets.zero,
            controlAffinity: ListTileControlAffinity.leading,
            title: Text(
              _t(
                'कारीगर मुझसे संपर्क कर सकते हैं।',
                'I agree to be contacted by the artisan.',
              ),
            ),
            onChanged: (value) => setState(() => _consent = value ?? false),
          ),
          if (_error != null) ...[
            Text(_error!, style: const TextStyle(color: AppColors.error)),
            const SizedBox(height: 12),
          ],
          FilledButton(
            key: const Key('submitEnquiryButton'),
            onPressed: _submitting ? null : _submit,
            child: _submitting
                ? const SizedBox.square(
                    dimension: 22,
                    child: CircularProgressIndicator(
                      strokeWidth: 2,
                      color: Colors.white,
                    ),
                  )
                : Text(_t('पूछताछ भेजें', 'Send enquiry')),
          ),
        ],
      ),
    );
  }
}

import 'package:flutter/material.dart';

import '../../../core/api/api_client.dart';
import '../../../core/localization/app_language.dart';
import '../../../core/theme/app_theme.dart';
import '../../../core/utils/money.dart';
import '../../../shared/widgets/detail_row.dart';
import '../../../shared/widgets/product_image.dart';
import '../controllers/catalogue_flow_controller.dart';
import 'catalogue_review_screen.dart';
import 'image_enhancement_screen.dart';
import 'pricing_assistant_screen.dart';
import 'published_catalogue_screen.dart';

class FinalApprovalScreen extends StatefulWidget {
  const FinalApprovalScreen({
    super.key,
    required this.controller,
    required this.language,
  });

  final CatalogueFlowController controller;
  final AppLanguage language;

  @override
  State<FinalApprovalScreen> createState() => _FinalApprovalScreenState();
}

class _FinalApprovalScreenState extends State<FinalApprovalScreen> {
  bool _submitting = false;
  String? _error;

  bool get _hi => widget.language == AppLanguage.hindi;
  String _t(String hi, String en) => _hi ? hi : en;

  Future<void> _approve() async {
    if (_submitting) return;
    setState(() {
      _submitting = true;
      _error = null;
    });
    try {
      final approved = await widget.controller.approveDraft();
      String? shopifyError;
      try {
        await widget.controller.syncDraftToShopify(approved.draftId);
      } on ApiException catch (error) {
        shopifyError = error.message;
      }
      if (!mounted) return;
      if (shopifyError != null) {
        ScaffoldMessenger.of(context).showSnackBar(
          SnackBar(
            content: Text(
              _t(
                'कैटलॉग तैयार है, लेकिन Shopify पर भेजा नहीं जा सका। $shopifyError',
                'Your catalogue is published, but Shopify could not be updated. $shopifyError',
              ),
            ),
          ),
        );
      }
      await Navigator.of(context).pushReplacement(
        MaterialPageRoute<void>(
          builder: (_) => PublishedCatalogueScreen(
            controller: widget.controller,
            catalogue: approved,
            language: widget.language,
          ),
        ),
      );
    } on ApiException catch (error) {
      if (mounted) setState(() => _error = error.message);
    } finally {
      if (mounted) setState(() => _submitting = false);
    }
  }

  @override
  Widget build(BuildContext context) {
    final draft = widget.controller.state.draft;
    final listing = draft.listing!;
    final facts = draft.fields;
    final image = draft.images.firstWhere((item) => item.isPrimary);
    final imageUrl = image.selectedVariant == 'enhanced'
        ? image.enhancedUrl
        : image.originalUrl;
    final finalPrice = widget.controller.state.approvedPricePaise!;
    return Scaffold(
      appBar: AppBar(
        backgroundColor: AppColors.background,
        surfaceTintColor: Colors.transparent,
        title: Text(_t('अंतिम मंज़ूरी', 'Final approval')),
      ),
      body: SafeArea(
        child: ListView(
          padding: const EdgeInsets.fromLTRB(24, 8, 24, 116),
          children: [
            AspectRatio(
              aspectRatio: 1,
              child: ProductImage(
                localPath: widget.controller.state.localImagePath,
                networkUrl: imageUrl,
                preferNetwork: image.selectedVariant == 'enhanced',
              ),
            ),
            Wrap(
              alignment: WrapAlignment.spaceBetween,
              spacing: 6,
              runSpacing: 2,
              children: [
                TextButton(
                  onPressed: () => _edit(
                    CatalogueReviewScreen(
                      controller: widget.controller,
                      language: widget.language,
                    ),
                  ),
                  child: Text(_t('जानकारी बदलें', 'Edit details')),
                ),
                TextButton(
                  onPressed: () => _edit(
                    ImageEnhancementScreen(
                      controller: widget.controller,
                      language: widget.language,
                    ),
                  ),
                  child: Text(_t('फोटो बदलें', 'Edit image')),
                ),
                TextButton(
                  onPressed: () => _edit(
                    PricingAssistantScreen(
                      controller: widget.controller,
                      language: widget.language,
                    ),
                  ),
                  child: Text(_t('कीमत बदलें', 'Edit price')),
                ),
              ],
            ),
            const SizedBox(height: 22),
            Text(
              listing.titleHi,
              style: Theme.of(context).textTheme.headlineSmall,
            ),
            const SizedBox(height: 4),
            Text(
              listing.titleEn,
              style: Theme.of(context).textTheme.bodyMedium,
            ),
            const SizedBox(height: 16),
            Text(
              Money.formatPaise(finalPrice, decimals: false),
              style: const TextStyle(
                fontSize: 30,
                fontWeight: FontWeight.w700,
                color: AppColors.text,
              ),
            ),
            const Divider(height: 36, color: AppColors.divider),
            Text(
              listing.descriptionHi,
              style: Theme.of(context).textTheme.bodyLarge,
            ),
            const SizedBox(height: 10),
            Text(
              listing.descriptionEn,
              style: Theme.of(context).textTheme.bodyMedium,
            ),
            if (listing.tags.isNotEmpty) ...[
              const SizedBox(height: 18),
              Wrap(
                spacing: 8,
                runSpacing: 8,
                children: [
                  for (final tag in listing.tags)
                    DecoratedBox(
                      decoration: BoxDecoration(
                        color: AppColors.surface,
                        border: Border.all(color: AppColors.border),
                        borderRadius: BorderRadius.circular(8),
                      ),
                      child: Padding(
                        padding: const EdgeInsets.symmetric(
                          horizontal: 10,
                          vertical: 6,
                        ),
                        child: Text('#$tag'),
                      ),
                    ),
                ],
              ),
            ],
            const Divider(height: 36, color: AppColors.divider),
            DetailRow(
              label: _t('उत्पाद', 'Product'),
              value: facts.productType!,
            ),
            DetailRow(label: _t('सामग्री', 'Material'), value: facts.material!),
            DetailRow(label: _t('तकनीक', 'Technique'), value: facts.technique!),
            DetailRow(label: _t('नाप', 'Dimensions'), value: facts.dimensions!),
            DetailRow(
              label: _t('उपलब्ध मात्रा', 'Available quantity'),
              value: '${facts.quantityAvailable}',
            ),
            DetailRow(
              label: _t('बनाने का समय', 'Production time'),
              value: '${facts.productionTimeDays} ${_t('दिन', 'days')}',
            ),
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
            key: const Key('approveCatalogueButton'),
            onPressed: _submitting ? null : _approve,
            child: _submitting
                ? const SizedBox.square(
                    dimension: 22,
                    child: CircularProgressIndicator(
                      strokeWidth: 2,
                      color: Colors.white,
                    ),
                  )
                : Text(_t('कैटलॉग मंज़ूर करें', 'Approve catalogue')),
          ),
        ),
      ),
    );
  }

  Future<void> _edit(Widget screen) async {
    await Navigator.of(context)
        .push(MaterialPageRoute<void>(builder: (_) => screen));
  }
}

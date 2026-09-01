import 'package:flutter/material.dart';
import 'package:flutter/services.dart';

import '../../../core/localization/app_language.dart';
import '../../../core/theme/app_theme.dart';
import '../../../core/utils/money.dart';
import '../../../shared/widgets/product_image.dart';
import '../controllers/catalogue_flow_controller.dart';
import '../models/catalogue_models.dart';
import 'public_catalogue_screen.dart';

class PublishedCatalogueScreen extends StatelessWidget {
  const PublishedCatalogueScreen({
    super.key,
    required this.controller,
    required this.catalogue,
    required this.language,
  });

  static const _shareChannel = MethodChannel('in.kalasetu/share');

  final CatalogueFlowController controller;
  final ApprovedCatalogue catalogue;
  final AppLanguage language;

  bool get _hi => language == AppLanguage.hindi;
  String _t(String hi, String en) => _hi ? hi : en;

  Future<void> _share(BuildContext context) async {
    try {
      await _shareChannel.invokeMethod<void>('shareText', {
        'text': catalogue.publicShareUrl,
      });
    } on PlatformException {
      if (!context.mounted) return;
      await _copy(context);
    }
  }

  Future<void> _copy(BuildContext context) async {
    await Clipboard.setData(ClipboardData(text: catalogue.publicShareUrl));
    if (!context.mounted) return;
    ScaffoldMessenger.of(context).showSnackBar(
      SnackBar(content: Text(_t('लिंक कॉपी हो गया', 'Link copied'))),
    );
  }

  void _home(BuildContext context) =>
      Navigator.of(context).popUntil((route) => route.isFirst);

  @override
  Widget build(BuildContext context) {
    final draft = controller.state.draft;
    final image = draft.images.firstWhere((item) => item.isPrimary);
    return Scaffold(
      appBar: AppBar(
        automaticallyImplyLeading: false,
        backgroundColor: AppColors.background,
        surfaceTintColor: Colors.transparent,
        actions: [
          IconButton(
            tooltip: _t('होम', 'Home'),
            onPressed: () => _home(context),
            icon: const Icon(Icons.close),
          ),
          const SizedBox(width: 12),
        ],
      ),
      body: SafeArea(
        child: ListView(
          padding: const EdgeInsets.fromLTRB(24, 12, 24, 28),
          children: [
            const Icon(
              Icons.check_circle_outline,
              size: 58,
              color: AppColors.accent,
            ),
            const SizedBox(height: 16),
            Text(
              _t('आपकी कैटलॉग तैयार है', 'Your catalogue is published'),
              textAlign: TextAlign.center,
              style: Theme.of(context).textTheme.headlineSmall,
            ),
            const SizedBox(height: 8),
            Text(
              _t(
                'अब इसे खरीदारों के साथ साझा करें।',
                'It is ready to share with buyers.',
              ),
              textAlign: TextAlign.center,
              style: Theme.of(context).textTheme.bodyMedium,
            ),
            const SizedBox(height: 24),
            SizedBox(
              height: 180,
              child: ProductImage(
                localPath: controller.state.localImagePath,
                networkUrl: image.selectedVariant == 'enhanced'
                    ? image.enhancedUrl
                    : image.originalUrl,
                fit: BoxFit.contain,
              ),
            ),
            const SizedBox(height: 12),
            Text(
              Money.formatPaise(catalogue.approvedPricePaise, decimals: false),
              textAlign: TextAlign.center,
              style: Theme.of(context).textTheme.titleLarge,
            ),
            const SizedBox(height: 26),
            FilledButton.icon(
              onPressed: () => _share(context),
              icon: const Icon(Icons.share_outlined),
              label: Text(_t('कैटलॉग साझा करें', 'Share catalogue')),
            ),
            const SizedBox(height: 10),
            OutlinedButton.icon(
              onPressed: () => _copy(context),
              icon: const Icon(Icons.copy_outlined),
              label: Text(_t('लिंक कॉपी करें', 'Copy link')),
            ),
            const SizedBox(height: 10),
            OutlinedButton.icon(
              key: const Key('viewBuyerPageButton'),
              onPressed: () => Navigator.of(context).push(
                MaterialPageRoute<void>(
                  builder: (_) => PublicCatalogueScreen(
                    controller: controller,
                    publicShareId: catalogue.publicShareId,
                    language: language,
                  ),
                ),
              ),
              icon: const Icon(Icons.open_in_new),
              label: Text(_t('खरीदार पेज देखें', 'View buyer page')),
            ),
            const SizedBox(height: 10),
            TextButton(
              onPressed: () => _home(context),
              child: Text(_t('होम पर जाएं', 'Back to home')),
            ),
          ],
        ),
      ),
    );
  }
}

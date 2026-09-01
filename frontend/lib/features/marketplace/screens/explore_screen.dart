import 'package:flutter/material.dart';

import '../../../core/api/api_client.dart';
import '../../../core/localization/app_language.dart';
import '../../../core/theme/app_theme.dart';
import '../../../core/utils/money.dart';
import '../../../shared/widgets/product_image.dart';
import '../../catalogue/controllers/catalogue_flow_controller.dart';
import '../../catalogue/models/catalogue_models.dart';
import '../../catalogue/screens/public_catalogue_screen.dart';

class ExploreScreen extends StatefulWidget {
  const ExploreScreen({
    super.key,
    required this.apiClient,
    required this.language,
    required this.isAdmin,
    required this.newCatalogueFlow,
  });

  final ApiClient apiClient;
  final AppLanguage language;
  final bool isAdmin;
  final CatalogueFlowController Function() newCatalogueFlow;

  @override
  State<ExploreScreen> createState() => _ExploreScreenState();
}

class _ExploreScreenState extends State<ExploreScreen> {
  List<MarketplaceCatalogue> _items = const [];
  String? _nextCursor;
  bool _loading = true;
  bool _loadingMore = false;
  String? _error;

  bool get _hi => widget.language == AppLanguage.hindi;
  String _t(String hi, String en) => _hi ? hi : en;

  @override
  void initState() {
    super.initState();
    _load();
  }

  @override
  void didUpdateWidget(covariant ExploreScreen oldWidget) {
    super.didUpdateWidget(oldWidget);
    if (oldWidget.language != widget.language) setState(() {});
  }

  Future<void> _load({bool refresh = false}) async {
    if (_loadingMore) return;
    setState(() {
      _loading = true;
      _error = null;
    });
    try {
      final page = await widget.apiClient.listMarketplaceCatalogues();
      if (!mounted) return;
      setState(() {
        _items = page.items;
        _nextCursor = page.nextCursor;
      });
    } on ApiException catch (error) {
      if (mounted) setState(() => _error = error.message);
    } finally {
      if (mounted) setState(() => _loading = false);
    }
  }

  Future<void> _loadMore() async {
    final cursor = _nextCursor;
    if (cursor == null || _loadingMore) return;
    setState(() => _loadingMore = true);
    try {
      final page = await widget.apiClient.listMarketplaceCatalogues(
        cursor: cursor,
      );
      if (!mounted) return;
      setState(() {
        _items = [..._items, ...page.items];
        _nextCursor = page.nextCursor;
      });
    } on ApiException catch (error) {
      if (mounted) setState(() => _error = error.message);
    } finally {
      if (mounted) setState(() => _loadingMore = false);
    }
  }

  Future<void> _open(MarketplaceCatalogue catalogue) =>
      Navigator.of(context).push(
        MaterialPageRoute<void>(
          builder: (_) => PublicCatalogueScreen(
            controller: widget.newCatalogueFlow(),
            publicShareId: catalogue.publicShareId,
            language: widget.language,
          ),
        ),
      );

  Future<void> _delete(MarketplaceCatalogue catalogue) async {
    final confirmed = await showDialog<bool>(
      context: context,
      builder: (context) => AlertDialog(
        title: Text(_t('कैटलॉग हटाएं?', 'Delete catalogue?')),
        content: Text(
          _t(
            'यह पोस्ट खोज और खरीदार पेज से हट जाएगा।',
            'This post will be removed from Explore and buyer pages.',
          ),
        ),
        actions: [
          TextButton(
            onPressed: () => Navigator.of(context).pop(false),
            child: Text(_t('रद्द करें', 'Cancel')),
          ),
          FilledButton(
            onPressed: () => Navigator.of(context).pop(true),
            child: Text(_t('हटाएं', 'Delete')),
          ),
        ],
      ),
    );
    if (confirmed != true || !mounted) return;
    try {
      await widget.apiClient.deleteMarketplaceCatalogue(
        catalogue.publicShareId,
      );
      if (!mounted) return;
      setState(
        () => _items = _items.where((item) => item != catalogue).toList(),
      );
      ScaffoldMessenger.of(context).showSnackBar(
        SnackBar(content: Text(_t('कैटलॉग हटा दिया गया', 'Catalogue deleted'))),
      );
    } on ApiException catch (error) {
      if (mounted) {
        ScaffoldMessenger.of(context)
            .showSnackBar(SnackBar(content: Text(error.message)));
      }
    }
  }

  @override
  Widget build(BuildContext context) {
    if (_loading) {
      return const Center(
        child: CircularProgressIndicator(color: AppColors.accent),
      );
    }
    if (_error != null && _items.isEmpty) {
      return Center(
        child: Padding(
          padding: const EdgeInsets.all(24),
          child: Column(
            mainAxisSize: MainAxisSize.min,
            children: [
              const Icon(
                Icons.cloud_off_outlined,
                size: 44,
                color: AppColors.mutedText,
              ),
              const SizedBox(height: 14),
              Text(_error!, textAlign: TextAlign.center),
              const SizedBox(height: 14),
              OutlinedButton.icon(
                onPressed: _load,
                icon: const Icon(Icons.refresh),
                label: Text(_t('फिर कोशिश करें', 'Try again')),
              ),
            ],
          ),
        ),
      );
    }
    return RefreshIndicator(
      color: AppColors.accent,
      onRefresh: () => _load(refresh: true),
      child: ListView(
        key: const Key('exploreCatalogueList'),
        padding: const EdgeInsets.fromLTRB(20, 24, 20, 32),
        children: [
          Text(
            _t('कारीगरों के उत्पाद', 'Explore products'),
            style: Theme.of(context).textTheme.headlineSmall,
          ),
          const SizedBox(height: 6),
          Text(
            _t(
              'देश भर के प्रकाशित कैटलॉग',
              'Published catalogues from artisans',
            ),
            style: Theme.of(context).textTheme.bodyMedium,
          ),
          const SizedBox(height: 20),
          if (_items.isEmpty)
            Padding(
              padding: const EdgeInsets.only(top: 64),
              child: Column(
                children: [
                  const Icon(
                    Icons.storefront_outlined,
                    size: 48,
                    color: AppColors.border,
                  ),
                  const SizedBox(height: 14),
                  Text(
                    _t(
                      'अभी कोई प्रकाशित कैटलॉग नहीं है',
                      'No published catalogues yet',
                    ),
                    textAlign: TextAlign.center,
                    style: Theme.of(context).textTheme.titleLarge,
                  ),
                ],
              ),
            )
          else ...[
            for (final catalogue in _items) ...[
              _MarketplaceCard(
                catalogue: catalogue,
                onTap: () => _open(catalogue),
                onDelete: widget.isAdmin ? () => _delete(catalogue) : null,
              ),
              const SizedBox(height: 14),
            ],
            if (_nextCursor != null)
              OutlinedButton(
                onPressed: _loadingMore ? null : _loadMore,
                child: _loadingMore
                    ? const SizedBox.square(
                        dimension: 20,
                        child: CircularProgressIndicator(
                          strokeWidth: 2,
                          color: AppColors.accent,
                        ),
                      )
                    : Text(_t('और देखें', 'Load more')),
              ),
          ],
        ],
      ),
    );
  }
}

class _MarketplaceCard extends StatelessWidget {
  const _MarketplaceCard({
    required this.catalogue,
    required this.onTap,
    required this.onDelete,
  });

  final MarketplaceCatalogue catalogue;
  final VoidCallback onTap;
  final VoidCallback? onDelete;

  @override
  Widget build(BuildContext context) {
    return Material(
      color: AppColors.surface,
      borderRadius: BorderRadius.circular(8),
      child: InkWell(
        onTap: onTap,
        borderRadius: BorderRadius.circular(8),
        child: Container(
          decoration: BoxDecoration(
            border: Border.all(color: AppColors.border),
            borderRadius: BorderRadius.circular(8),
          ),
          child: Row(
            crossAxisAlignment: CrossAxisAlignment.start,
            children: [
              SizedBox(
                width: 112,
                height: 112,
                child: ProductImage(
                  networkUrl: catalogue.imageUrl,
                  preferNetwork: true,
                ),
              ),
              Expanded(
                child: Padding(
                  padding: const EdgeInsets.fromLTRB(14, 14, 10, 12),
                  child: Column(
                    crossAxisAlignment: CrossAxisAlignment.start,
                    children: [
                      Text(
                        catalogue.title,
                        maxLines: 2,
                        overflow: TextOverflow.ellipsis,
                        style: const TextStyle(
                          fontSize: 16,
                          fontWeight: FontWeight.w700,
                        ),
                      ),
                      const SizedBox(height: 6),
                      Text(
                        Money.formatPaise(
                          catalogue.pricePaise,
                          decimals: false,
                        ),
                        style: const TextStyle(
                          color: AppColors.darkAccent,
                          fontWeight: FontWeight.w700,
                        ),
                      ),
                      const SizedBox(height: 7),
                      Text(
                        catalogue.artisan.displayName,
                        maxLines: 1,
                        overflow: TextOverflow.ellipsis,
                        style: Theme.of(context).textTheme.bodyMedium,
                      ),
                      if (catalogue.artisan.cluster != null)
                        Text(
                          catalogue.artisan.cluster!,
                          maxLines: 1,
                          overflow: TextOverflow.ellipsis,
                          style: Theme.of(context).textTheme.bodyMedium,
                        ),
                    ],
                  ),
                ),
              ),
              if (onDelete != null)
                Padding(
                  padding: const EdgeInsets.only(top: 36, right: 2),
                  child: PopupMenuButton<String>(
                    tooltip: 'Delete catalogue',
                    onSelected: (_) => onDelete!(),
                    itemBuilder: (context) => const [
                      PopupMenuItem<String>(
                        value: 'delete',
                        child: Row(
                          children: [
                            Icon(Icons.delete_outline),
                            SizedBox(width: 10),
                            Text('Delete catalogue'),
                          ],
                        ),
                      ),
                    ],
                  ),
                )
              else
                const Padding(
                  padding: EdgeInsets.only(top: 43, right: 4),
                  child: Icon(Icons.chevron_right, color: AppColors.mutedText),
                ),
            ],
          ),
        ),
      ),
    );
  }
}

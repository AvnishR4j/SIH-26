import 'package:flutter/material.dart';

import '../../../core/api/api_client.dart';
import '../../../core/localization/app_language.dart';
import '../../../core/localization/app_strings.dart';
import '../../../core/media/media_capture_service.dart';
import '../../../core/theme/app_theme.dart';
import '../../../shared/widgets/brand_mark.dart';
import '../../../shared/widgets/language_switch.dart';
import '../../../shared/widgets/product_image.dart';
import '../../auth/models/auth_models.dart';
import '../../catalogue/controllers/catalogue_flow_controller.dart';
import '../../catalogue/models/catalogue_models.dart';
import '../../catalogue/screens/public_catalogue_screen.dart';
import '../../catalogue/screens/product_photo_screen.dart';
import '../../marketplace/screens/explore_screen.dart';
import '../../profile/models/profile_models.dart';
import '../../profile/screens/profile_consent_screen.dart';
import '../controllers/home_controller.dart';

class DashboardScreen extends StatefulWidget {
  const DashboardScreen({
    super.key,
    required this.apiClient,
    required this.session,
    required this.profile,
    required this.language,
    required this.onLanguageChanged,
    required this.onLogout,
    this.mediaCaptureService,
  });

  final ApiClient apiClient;
  final AuthSession session;
  final ArtisanProfile profile;
  final AppLanguage language;
  final ValueChanged<AppLanguage> onLanguageChanged;
  final VoidCallback onLogout;
  final MediaCaptureService? mediaCaptureService;

  @override
  State<DashboardScreen> createState() => _DashboardScreenState();
}

class _DashboardScreenState extends State<DashboardScreen> {
  static const _demoCraftCategories = [
    'textile',
    'embroidery',
    'handloom',
    'pottery',
    'jewellery',
    'woodcraft',
    'metalcraft',
    'basketry',
    'painting',
    'leathercraft',
  ];

  late AppLanguage _language;
  late ArtisanProfile _profile;
  late final HomeController _controller;
  List<DraftSummary> _drafts = const [];
  bool _loadingDrafts = true;
  bool _draftLoadFailed = false;
  bool _creating = false;
  int _selectedTab = 0;
  String? _openingDraftId;
  String? _deletingDraftId;
  CatalogueFlowController? _pendingFlow;

  @override
  void initState() {
    super.initState();
    _language = widget.language;
    _profile = widget.profile;
    _controller = HomeController(
      widget.apiClient,
      media: widget.mediaCaptureService ?? PlatformMediaCaptureService(),
    );
    _loadDrafts();
  }

  Future<void> _loadDrafts() async {
    if (mounted) {
      setState(() {
        _loadingDrafts = true;
        _draftLoadFailed = false;
      });
    }
    try {
      final drafts = await _controller.loadRecentDrafts();
      if (mounted) setState(() => _drafts = drafts);
    } catch (_) {
      if (mounted) setState(() => _draftLoadFailed = true);
    } finally {
      if (mounted) setState(() => _loadingDrafts = false);
    }
  }

  Future<String?> _chooseCategory() async {
    final strings = AppStrings(_language);
    final categories = {
      ..._profile.craftCategories,
      ..._demoCraftCategories,
    }.toList(growable: false);
    if (categories.isEmpty) {
      await Navigator.of(context).push(
        MaterialPageRoute<void>(
          builder: (_) => ProfileConsentScreen(
            apiClient: widget.apiClient,
            profile: _profile,
            language: _language,
            allowBack: true,
            onComplete: (profile) {
              setState(() => _profile = profile);
              Navigator.of(context).pop();
            },
          ),
        ),
      );
      return null;
    }
    if (categories.length == 1) return categories.first;
    return showModalBottomSheet<String>(
      context: context,
      backgroundColor: AppColors.surface,
      showDragHandle: true,
      isScrollControlled: true,
      builder: (context) => SafeArea(
        child: SizedBox(
          height: MediaQuery.sizeOf(context).height * 0.72,
          child: Column(
            crossAxisAlignment: CrossAxisAlignment.stretch,
            children: [
              Padding(
                padding: const EdgeInsets.fromLTRB(24, 8, 24, 12),
                child: Text(
                  strings.categoryQuestion,
                  style: Theme.of(context).textTheme.titleLarge,
                ),
              ),
              const Divider(height: 1, color: AppColors.divider),
              Expanded(
                child: ListView.separated(
                  padding: const EdgeInsets.fromLTRB(24, 4, 24, 20),
                  itemCount: categories.length,
                  separatorBuilder: (_, _) =>
                      const Divider(height: 1, color: AppColors.divider),
                  itemBuilder: (context, index) {
                    final category = categories[index];
                    return ListTile(
                      contentPadding: EdgeInsets.zero,
                      title: Text(strings.categoryLabel(category)),
                      trailing: const Icon(Icons.chevron_right),
                      onTap: () => Navigator.of(context).pop(category),
                    );
                  },
                ),
              ),
            ],
          ),
        ),
      ),
    );
  }

  Future<void> _startCatalogue() async {
    if (_creating) return;
    final category = await _chooseCategory();
    if (category == null || !mounted) return;
    setState(() => _creating = true);
    final flow = _pendingFlow ??= _controller.newCatalogueFlow();
    try {
      await flow.createDraft(category);
      if (!mounted) return;
      _pendingFlow = null;
      await Navigator.of(context).push(
        MaterialPageRoute<void>(
          builder: (_) =>
              ProductPhotoScreen(controller: flow, language: _language),
        ),
      );
      await _loadDrafts();
    } on ApiException catch (error) {
      if (!mounted) return;
      ScaffoldMessenger.of(context)
          .showSnackBar(SnackBar(content: Text(error.message)));
    } finally {
      if (mounted) setState(() => _creating = false);
    }
  }

  Future<void> _openProfile() async {
    await Navigator.of(context).push(
      MaterialPageRoute<void>(
        builder: (_) => ProfileConsentScreen(
          apiClient: widget.apiClient,
          profile: _profile,
          language: _language,
          allowBack: true,
          onLogout: _logout,
          onComplete: (profile) {
            setState(() => _profile = profile);
            Navigator.of(context).pop();
          },
        ),
      ),
    );
  }

  void _logout() {
    widget.onLogout();
  }

  Future<void> _openPublishedCatalogue(DraftSummary draft) async {
    if (draft.status != 'approved' || _openingDraftId != null) return;
    setState(() => _openingDraftId = draft.id);
    try {
      final catalogue = await widget.apiClient.getPublishedCatalogue(draft.id);
      if (!mounted) return;
      await Navigator.of(context).push(
        MaterialPageRoute<void>(
          builder: (_) => PublicCatalogueScreen(
            controller: _controller.newCatalogueFlow(),
            publicShareId: catalogue.publicShareId,
            language: _language,
          ),
        ),
      );
    } on ApiException catch (error) {
      if (mounted) {
        ScaffoldMessenger.of(context)
            .showSnackBar(SnackBar(content: Text(error.message)));
      }
    } finally {
      if (mounted) setState(() => _openingDraftId = null);
    }
  }

  Future<void> _confirmDeleteDraft(DraftSummary draft) async {
    if (_deletingDraftId != null) return;
    final strings = AppStrings(_language);
    final confirmed = await showDialog<bool>(
      context: context,
      builder: (context) => AlertDialog(
        title: Text(strings.deleteCatalogue),
        content: Text(strings.deleteCatalogueQuestion),
        actions: [
          TextButton(
            onPressed: () => Navigator.of(context).pop(false),
            child: Text(strings.cancel),
          ),
          FilledButton(
            onPressed: () => Navigator.of(context).pop(true),
            child: Text(strings.deleteCatalogue),
          ),
        ],
      ),
    );
    if (confirmed != true || !mounted) return;

    setState(() => _deletingDraftId = draft.id);
    try {
      await widget.apiClient.deleteDraft(draft.id);
      if (!mounted) return;
      setState(
        () => _drafts = _drafts.where((item) => item.id != draft.id).toList(),
      );
      ScaffoldMessenger.of(context)
          .showSnackBar(SnackBar(content: Text(strings.catalogueDeleted)));
    } on ApiException catch (error) {
      if (mounted) {
        ScaffoldMessenger.of(context)
            .showSnackBar(SnackBar(content: Text(error.message)));
      }
    } catch (_) {
      if (mounted) {
        ScaffoldMessenger.of(context)
            .showSnackBar(SnackBar(content: Text(strings.deleteFailed)));
      }
    } finally {
      if (mounted) setState(() => _deletingDraftId = null);
    }
  }

  @override
  Widget build(BuildContext context) {
    final strings = AppStrings(_language);
    return Scaffold(
      appBar: AppBar(
        backgroundColor: AppColors.background,
        surfaceTintColor: Colors.transparent,
        titleSpacing: 20,
        title: const Row(
          mainAxisSize: MainAxisSize.min,
          children: [
            BrandMark(compact: true),
            SizedBox(width: 10),
            Text(
              'KalaSetu',
              style: TextStyle(fontWeight: FontWeight.w700, fontSize: 20),
            ),
          ],
        ),
        actions: [
          LanguageSwitch(
            language: _language,
            onChanged: (language) {
              setState(() => _language = language);
              widget.onLanguageChanged(language);
            },
          ),
          const SizedBox(width: 10),
          InkWell(
            key: const Key('profileAvatar'),
            borderRadius: BorderRadius.circular(20),
            onTap: _openProfile,
            child: CircleAvatar(
              radius: 18,
              backgroundColor: AppColors.accent,
              child: Text(
                _profile.name.isEmpty ? 'K' : _profile.name.characters.first,
                style: const TextStyle(
                  color: Colors.white,
                  fontWeight: FontWeight.w700,
                ),
              ),
            ),
          ),
          const SizedBox(width: 20),
        ],
      ),
      body: _selectedTab == 0
          ? SafeArea(
              child: RefreshIndicator(
                onRefresh: _loadDrafts,
                color: AppColors.accent,
                child: ListView(
                  padding: const EdgeInsets.fromLTRB(20, 24, 20, 32),
                  children: [
                    Text(
                      strings.greeting(_profile.name),
                      style: const TextStyle(
                        color: AppColors.darkAccent,
                        fontFamily: 'serif',
                        fontSize: 20,
                        fontWeight: FontWeight.w700,
                        height: 1.2,
                      ),
                    ),
                    const SizedBox(height: 24),
                    Container(
                      padding: const EdgeInsets.symmetric(vertical: 26),
                      decoration: const BoxDecoration(
                        border: Border.symmetric(
                          horizontal: BorderSide(color: AppColors.divider),
                        ),
                      ),
                      child: Column(
                        crossAxisAlignment: CrossAxisAlignment.start,
                        children: [
                          Text(
                            strings.addProduct,
                            style: Theme.of(context).textTheme.headlineSmall,
                          ),
                          const SizedBox(height: 6),
                          Text(
                            strings.photoAndVoice,
                            style: Theme.of(context).textTheme.bodyMedium,
                          ),
                          const SizedBox(height: 22),
                          FilledButton(
                            key: const Key('createCatalogueButton'),
                            onPressed: _creating ? null : _startCatalogue,
                            child: _creating
                                ? const SizedBox.square(
                                    dimension: 22,
                                    child: CircularProgressIndicator(
                                      strokeWidth: 2,
                                      color: Colors.white,
                                    ),
                                  )
                                : Row(
                                    children: [
                                      const Icon(Icons.add_a_photo_outlined),
                                      const SizedBox(width: 12),
                                      Expanded(
                                        child: Column(
                                          crossAxisAlignment:
                                              CrossAxisAlignment.start,
                                          children: [
                                            Text(strings.createCatalogue),
                                            const SizedBox(height: 2),
                                            Text(
                                              strings.catalogueVoiceCue,
                                              style: const TextStyle(
                                                fontSize: 12,
                                                fontWeight: FontWeight.w500,
                                              ),
                                            ),
                                          ],
                                        ),
                                      ),
                                      const Icon(Icons.mic_none_rounded),
                                    ],
                                  ),
                          ),
                        ],
                      ),
                    ),
                    const SizedBox(height: 28),
                    Text(
                      strings.recentDrafts,
                      style: Theme.of(context).textTheme.titleLarge,
                    ),
                    const SizedBox(height: 16),
                    if (_loadingDrafts)
                      const Center(
                        child: Padding(
                          padding: EdgeInsets.all(24),
                          child: CircularProgressIndicator(
                            color: AppColors.accent,
                          ),
                        ),
                      )
                    else if (_draftLoadFailed) ...[
                      const Icon(
                        Icons.cloud_off_outlined,
                        size: 42,
                        color: AppColors.mutedText,
                      ),
                      const SizedBox(height: 12),
                      Text(
                        strings.draftLoadFailed,
                        textAlign: TextAlign.center,
                        style: const TextStyle(
                          color: AppColors.text,
                          fontWeight: FontWeight.w600,
                        ),
                      ),
                      const SizedBox(height: 10),
                      Center(
                        child: OutlinedButton.icon(
                          onPressed: _loadDrafts,
                          icon: const Icon(Icons.refresh),
                          label: Text(strings.tryAgain),
                        ),
                      ),
                    ] else if (_drafts.isEmpty) ...[
                      const SizedBox(height: 10),
                      const Icon(
                        Icons.inventory_2_outlined,
                        size: 42,
                        color: AppColors.border,
                      ),
                      const SizedBox(height: 12),
                      Text(
                        strings.noDrafts,
                        textAlign: TextAlign.center,
                        style: const TextStyle(
                          color: AppColors.text,
                          fontSize: 15,
                          fontWeight: FontWeight.w600,
                        ),
                      ),
                      const SizedBox(height: 4),
                      Text(
                        strings.firstCatalogue,
                        textAlign: TextAlign.center,
                        style: Theme.of(context).textTheme.bodyMedium,
                      ),
                    ] else
                      for (final draft in _drafts)
                        _DraftRow(
                          title: _language == AppLanguage.hindi
                              ? (draft.titleHi ??
                                    draft.titleEn ??
                                    strings.newCatalogue)
                              : (draft.titleEn ??
                                    draft.titleHi ??
                                    strings.newCatalogue),
                          statusLabel: strings.draftStatus(draft.status),
                          thumbnailUrl: draft.thumbnailUrl,
                          language: _language,
                          isOpening: _openingDraftId == draft.id,
                          isDeleting: _deletingDraftId == draft.id,
                          onTap: draft.status == 'approved'
                              ? () => _openPublishedCatalogue(draft)
                              : null,
                          onDelete: () => _confirmDeleteDraft(draft),
                        ),
                  ],
                ),
              ),
            )
          : SafeArea(
              child: ExploreScreen(
                apiClient: widget.apiClient,
                language: _language,
                newCatalogueFlow: _controller.newCatalogueFlow,
              ),
            ),
      bottomNavigationBar: NavigationBar(
        selectedIndex: _selectedTab,
        onDestinationSelected: (index) => setState(() => _selectedTab = index),
        destinations: [
          NavigationDestination(
            icon: const Icon(Icons.home_outlined),
            selectedIcon: const Icon(Icons.home),
            label: _language == AppLanguage.hindi ? 'होम' : 'Home',
          ),
          NavigationDestination(
            key: const Key('exploreTab'),
            icon: const Icon(Icons.storefront_outlined),
            selectedIcon: const Icon(Icons.storefront),
            label: _language == AppLanguage.hindi ? 'खोजें' : 'Explore',
          ),
        ],
      ),
    );
  }
}

class _DraftRow extends StatelessWidget {
  const _DraftRow({
    required this.title,
    required this.statusLabel,
    required this.thumbnailUrl,
    required this.language,
    required this.isOpening,
    required this.isDeleting,
    required this.onTap,
    required this.onDelete,
  });

  final String title;
  final String statusLabel;
  final String? thumbnailUrl;
  final AppLanguage language;
  final bool isOpening;
  final bool isDeleting;
  final VoidCallback? onTap;
  final VoidCallback onDelete;

  @override
  Widget build(BuildContext context) {
    final strings = AppStrings(language);
    return InkWell(
      onTap: onTap,
      child: Container(
        padding: const EdgeInsets.symmetric(vertical: 14),
        decoration: const BoxDecoration(
          border: Border(bottom: BorderSide(color: AppColors.divider)),
        ),
        child: Row(
          children: [
            SizedBox(
              width: 56,
              height: 56,
              child: DecoratedBox(
                decoration: BoxDecoration(
                  color: AppColors.surface,
                  border: Border.all(color: AppColors.border),
                  borderRadius: BorderRadius.circular(8),
                ),
                child: ProductImage(
                  networkUrl: thumbnailUrl,
                  borderRadius: 7,
                  cacheWidth: 112,
                  cacheHeight: 112,
                ),
              ),
            ),
            const SizedBox(width: 14),
            Expanded(
              child: Column(
                crossAxisAlignment: CrossAxisAlignment.start,
                children: [
                  Text(
                    title,
                    style: const TextStyle(fontWeight: FontWeight.w600),
                  ),
                  const SizedBox(height: 3),
                  Text(
                    statusLabel,
                    style: Theme.of(context).textTheme.bodyMedium,
                  ),
                ],
              ),
            ),
            if (isDeleting)
              const SizedBox.square(
                dimension: 20,
                child: CircularProgressIndicator(
                  strokeWidth: 2,
                  color: AppColors.accent,
                ),
              )
            else if (onTap != null)
              isOpening
                  ? const SizedBox.square(
                      dimension: 20,
                      child: CircularProgressIndicator(
                        strokeWidth: 2,
                        color: AppColors.accent,
                      ),
                    )
                  : Row(
                      mainAxisSize: MainAxisSize.min,
                      children: [
                        const Icon(
                          Icons.chevron_right,
                          color: AppColors.mutedText,
                        ),
                        PopupMenuButton<String>(
                          tooltip: strings.deleteCatalogue,
                          onSelected: (_) => onDelete(),
                          itemBuilder: (context) => [
                            PopupMenuItem<String>(
                              value: 'delete',
                              child: Row(
                                children: [
                                  const Icon(Icons.delete_outline),
                                  const SizedBox(width: 10),
                                  Text(strings.deleteCatalogue),
                                ],
                              ),
                            ),
                          ],
                        ),
                      ],
                    )
            else
              PopupMenuButton<String>(
                tooltip: strings.deleteCatalogue,
                onSelected: (_) => onDelete(),
                itemBuilder: (context) => [
                  PopupMenuItem<String>(
                    value: 'delete',
                    child: Row(
                      children: [
                        const Icon(Icons.delete_outline),
                        const SizedBox(width: 10),
                        Text(strings.deleteCatalogue),
                      ],
                    ),
                  ),
                ],
              ),
          ],
        ),
      ),
    );
  }
}

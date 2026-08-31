import 'package:flutter/material.dart';

import '../../../core/api/api_client.dart';
import '../../../core/localization/app_language.dart';
import '../../../core/localization/app_strings.dart';
import '../../../core/theme/app_theme.dart';
import '../models/profile_models.dart';

class ProfileConsentScreen extends StatefulWidget {
  const ProfileConsentScreen({
    super.key,
    required this.apiClient,
    required this.profile,
    required this.onComplete,
    required this.language,
    this.allowBack = false,
    this.onLogout,
  });

  final ApiClient apiClient;
  final ArtisanProfile profile;
  final ValueChanged<ArtisanProfile> onComplete;
  final AppLanguage language;
  final bool allowBack;
  final VoidCallback? onLogout;

  @override
  State<ProfileConsentScreen> createState() => _ProfileConsentScreenState();
}

class _ProfileConsentScreenState extends State<ProfileConsentScreen> {
  late final TextEditingController _name;
  late final TextEditingController _cluster;
  late final TextEditingController _craft;
  late bool _consent;
  bool _saving = false;
  String? _error;

  @override
  void initState() {
    super.initState();
    _name = TextEditingController(text: widget.profile.name);
    _cluster = TextEditingController(text: widget.profile.cluster ?? '');
    _craft = TextEditingController(
      text: widget.profile.craftCategories.join(', '),
    );
    _consent = widget.profile.consent.accepted;
  }

  @override
  void dispose() {
    _name.dispose();
    _cluster.dispose();
    _craft.dispose();
    super.dispose();
  }

  Future<void> _save() async {
    final categories = _craft.text
        .split(',')
        .map((value) => value.trim())
        .where((value) => value.isNotEmpty)
        .toList();
    if (_name.text.trim().isEmpty ||
        _cluster.text.trim().isEmpty ||
        categories.isEmpty ||
        !_consent) {
      setState(() => _error = AppStrings(widget.language).completeProfileError);
      return;
    }
    setState(() {
      _saving = true;
      _error = null;
    });
    try {
      var profile = await widget.apiClient.updateMe(
        UpdateProfileInput(
          name: _name.text.trim(),
          preferredLanguage: widget.language.code,
          cluster: _cluster.text.trim(),
          craftCategories: categories,
        ),
      );
      final consent = await widget.apiClient.setMediaProcessingConsent(
        SetMediaConsentInput(
          accepted: true,
          policyVersion: widget.profile.consent.policyVersion,
        ),
      );
      profile = profile.copyWith(consent: consent);
      if (mounted) widget.onComplete(profile);
    } on ApiException catch (error) {
      if (mounted) setState(() => _error = error.message);
    } finally {
      if (mounted) setState(() => _saving = false);
    }
  }

  Future<void> _confirmLogout() async {
    final strings = AppStrings(widget.language);
    final confirmed = await showDialog<bool>(
      context: context,
      builder: (context) => AlertDialog(
        title: Text(strings.logout),
        content: Text(strings.logoutQuestion),
        actions: [
          TextButton(
            onPressed: () => Navigator.of(context).pop(false),
            child: Text(strings.cancel),
          ),
          FilledButton(
            onPressed: () => Navigator.of(context).pop(true),
            child: Text(strings.logout),
          ),
        ],
      ),
    );
    if (confirmed == true && mounted) widget.onLogout?.call();
  }

  @override
  Widget build(BuildContext context) {
    final strings = AppStrings(widget.language);
    return PopScope(
      canPop: widget.allowBack,
      child: Scaffold(
        appBar: AppBar(
          backgroundColor: AppColors.background,
          surfaceTintColor: Colors.transparent,
          automaticallyImplyLeading: widget.allowBack,
          title: Text(strings.profileAndConsent),
        ),
        body: SafeArea(
          child: ListView(
            padding: const EdgeInsets.fromLTRB(24, 16, 24, 32),
            children: [
              Text(
                strings.profileIntro,
                style: Theme.of(context).textTheme.headlineSmall,
              ),
              const SizedBox(height: 8),
              Text(
                strings.profileIntroBody,
                style: Theme.of(context).textTheme.bodyMedium,
              ),
              const SizedBox(height: 24),
              TextField(
                controller: _name,
                decoration: InputDecoration(labelText: strings.nameLabel),
              ),
              const SizedBox(height: 12),
              TextField(
                controller: _cluster,
                decoration: InputDecoration(labelText: strings.clusterLabel),
              ),
              const SizedBox(height: 12),
              TextField(
                controller: _craft,
                decoration: InputDecoration(
                  labelText: strings.craftCategoryLabel,
                  hintText: strings.craftCategoryHint,
                ),
              ),
              const SizedBox(height: 20),
              CheckboxListTile(
                value: _consent,
                onChanged: (value) => setState(() => _consent = value ?? false),
                contentPadding: EdgeInsets.zero,
                controlAffinity: ListTileControlAffinity.leading,
                activeColor: AppColors.accent,
                title: Text(strings.aiConsentLabel),
                subtitle: Text(strings.aiConsentDetails),
              ),
              if (_error != null) ...[
                const SizedBox(height: 8),
                Text(_error!, style: const TextStyle(color: AppColors.error)),
              ],
              const SizedBox(height: 20),
              FilledButton(
                onPressed: _saving ? null : _save,
                child: _saving
                    ? const SizedBox.square(
                        dimension: 22,
                        child: CircularProgressIndicator(
                          strokeWidth: 2,
                          color: Colors.white,
                        ),
                      )
                    : Text(strings.saveAndContinue),
              ),
              if (widget.allowBack && widget.onLogout != null) ...[
                const Divider(height: 36, color: AppColors.divider),
                TextButton.icon(
                  key: const Key('logoutButton'),
                  onPressed: _saving ? null : _confirmLogout,
                  icon: const Icon(Icons.logout),
                  label: Text(strings.logout),
                  style: TextButton.styleFrom(foregroundColor: AppColors.error),
                ),
              ],
            ],
          ),
        ),
      ),
    );
  }
}

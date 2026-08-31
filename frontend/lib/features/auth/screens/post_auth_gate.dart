import 'package:flutter/material.dart';

import '../../../core/api/api_client.dart';
import '../../../core/localization/app_language.dart';
import '../../../core/localization/app_strings.dart';
import '../../../core/theme/app_theme.dart';
import '../../dashboard/screens/dashboard_screen.dart';
import '../../profile/models/profile_models.dart';
import '../../profile/screens/profile_consent_screen.dart';
import '../models/auth_models.dart';

class PostAuthGate extends StatefulWidget {
  const PostAuthGate({
    super.key,
    required this.apiClient,
    required this.session,
    required this.language,
    required this.onLanguageChanged,
  });

  final ApiClient apiClient;
  final AuthSession session;
  final AppLanguage language;
  final ValueChanged<AppLanguage> onLanguageChanged;

  @override
  State<PostAuthGate> createState() => _PostAuthGateState();
}

class _PostAuthGateState extends State<PostAuthGate> {
  ArtisanProfile? _profile;
  Object? _error;

  @override
  void initState() {
    super.initState();
    _load();
  }

  Future<void> _load() async {
    setState(() => _error = null);
    try {
      final profile = await widget.apiClient.getMe();
      if (mounted) setState(() => _profile = profile);
    } catch (error) {
      if (mounted) setState(() => _error = error);
    }
  }

  @override
  Widget build(BuildContext context) {
    if (_error != null) {
      final strings = AppStrings(widget.language);
      return Scaffold(
        body: Center(
          child: Padding(
            padding: const EdgeInsets.all(24),
            child: Column(
              mainAxisSize: MainAxisSize.min,
              children: [
                Text(strings.profileLoadFailed),
                const SizedBox(height: 16),
                FilledButton(onPressed: _load, child: Text(strings.tryAgain)),
              ],
            ),
          ),
        ),
      );
    }
    final profile = _profile;
    if (profile == null) {
      return const Scaffold(
        body: Center(child: CircularProgressIndicator(color: AppColors.accent)),
      );
    }
    if (profile.needsOnboarding) {
      return ProfileConsentScreen(
        apiClient: widget.apiClient,
        profile: profile,
        language: widget.language,
        onComplete: (updated) => setState(() => _profile = updated),
      );
    }
    return DashboardScreen(
      apiClient: widget.apiClient,
      session: widget.session,
      profile: profile,
      language: widget.language,
      onLanguageChanged: widget.onLanguageChanged,
    );
  }
}

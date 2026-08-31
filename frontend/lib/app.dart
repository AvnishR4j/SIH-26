import 'package:flutter/material.dart';

import 'core/api/api_client.dart';
import 'core/api/mock_api_client.dart';
import 'core/api/real_api_client.dart';
import 'core/localization/app_language.dart';
import 'core/session/session_store.dart';
import 'core/theme/app_theme.dart';
import 'features/auth/models/auth_models.dart';
import 'features/auth/screens/login_screen.dart';
import 'features/auth/screens/post_auth_gate.dart';

class KalaSetuApp extends StatefulWidget {
  const KalaSetuApp({super.key, this.apiClient});

  final ApiClient? apiClient;

  @override
  State<KalaSetuApp> createState() => _KalaSetuAppState();
}

class _KalaSetuAppState extends State<KalaSetuApp> {
  AppLanguage _language = AppLanguage.hindi;
  late final ApiClient _apiClient = widget.apiClient ?? _configuredApiClient();
  final SessionStore _sessionStore = SessionStore();
  AuthSession? _session;
  var _restoringSession = true;

  @override
  void initState() {
    super.initState();
    _restoreSession();
  }

  Future<void> _restoreSession() async {
    final session = await _sessionStore.read();
    if (session != null) {
      _apiClient.restoreSession(session);
      try {
        await _apiClient.getMe();
        _session = session;
      } catch (_) {
        _apiClient.clearSession();
        await _sessionStore.clear();
      }
    }
    if (mounted) setState(() => _restoringSession = false);
  }

  Future<void> _saveSession(AuthSession session) async {
    await _sessionStore.save(session);
    if (mounted) setState(() => _session = session);
  }

  void _logout() {
    _apiClient.clearSession();
    _sessionStore.clear();
    setState(() => _session = null);
  }

  ApiClient _configuredApiClient() {
    const baseUrl = String.fromEnvironment('API_BASE_URL');
    return baseUrl.isEmpty
        ? MockApiClient()
        : RealApiClient(baseUrl: Uri.parse(baseUrl));
  }

  @override
  Widget build(BuildContext context) {
    final home = _restoringSession
        ? const Scaffold(
            body: Center(
              child: CircularProgressIndicator(color: AppColors.accent),
            ),
          )
        : _session == null
        ? LoginScreen(
            apiClient: _apiClient,
            language: _language,
            onLanguageChanged: (language) {
              setState(() => _language = language);
            },
            onAuthenticated: _saveSession,
          )
        : PostAuthGate(
            apiClient: _apiClient,
            session: _session!,
            language: _language,
            onLanguageChanged: (language) {
              setState(() => _language = language);
            },
            onLogout: _logout,
          );
    return MaterialApp(
      debugShowCheckedModeBanner: false,
      title: 'KalaSetu AI',
      theme: AppTheme.light,
      home: home,
    );
  }
}

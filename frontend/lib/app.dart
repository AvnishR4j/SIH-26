import 'package:flutter/material.dart';

import 'core/api/api_client.dart';
import 'core/api/mock_api_client.dart';
import 'core/api/real_api_client.dart';
import 'core/localization/app_language.dart';
import 'core/theme/app_theme.dart';
import 'features/auth/screens/login_screen.dart';

class KalaSetuApp extends StatefulWidget {
  const KalaSetuApp({super.key, this.apiClient});

  final ApiClient? apiClient;

  @override
  State<KalaSetuApp> createState() => _KalaSetuAppState();
}

class _KalaSetuAppState extends State<KalaSetuApp> {
  AppLanguage _language = AppLanguage.hindi;
  late final ApiClient _apiClient = widget.apiClient ?? _configuredApiClient();

  ApiClient _configuredApiClient() {
    const baseUrl = String.fromEnvironment('API_BASE_URL');
    return baseUrl.isEmpty
        ? MockApiClient()
        : RealApiClient(baseUrl: Uri.parse(baseUrl));
  }

  @override
  Widget build(BuildContext context) {
    return MaterialApp(
      debugShowCheckedModeBanner: false,
      title: 'KalaSetu AI',
      theme: AppTheme.light,
      home: LoginScreen(
        apiClient: _apiClient,
        language: _language,
        onLanguageChanged: (language) {
          setState(() => _language = language);
        },
      ),
    );
  }
}

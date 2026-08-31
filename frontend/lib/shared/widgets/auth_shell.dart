import 'package:flutter/material.dart';

import '../../core/localization/app_language.dart';
import '../../core/theme/app_theme.dart';
import 'brand_mark.dart';
import 'language_switch.dart';

class AuthShell extends StatelessWidget {
  const AuthShell({
    super.key,
    required this.language,
    required this.onLanguageChanged,
    required this.child,
  });

  final AppLanguage language;
  final ValueChanged<AppLanguage> onLanguageChanged;
  final Widget child;

  @override
  Widget build(BuildContext context) {
    return Scaffold(
      backgroundColor: AppColors.authBackground,
      body: SafeArea(
        child: Center(
          child: SingleChildScrollView(
            padding: const EdgeInsets.symmetric(horizontal: 14, vertical: 28),
            child: ConstrainedBox(
              constraints: const BoxConstraints(maxWidth: 420),
              child: Container(
                padding: const EdgeInsets.fromLTRB(20, 16, 20, 24),
                decoration: BoxDecoration(
                  color: AppColors.surface,
                  borderRadius: BorderRadius.circular(24),
                  border: Border.all(
                    color: const Color(0xFFB8AA91),
                    width: 1.5,
                  ),
                  boxShadow: const [
                    BoxShadow(
                      color: Color(0x22000000),
                      blurRadius: 2,
                      offset: Offset(0, 2),
                    ),
                  ],
                ),
                child: Column(
                  crossAxisAlignment: CrossAxisAlignment.stretch,
                  children: [
                    Align(
                      alignment: Alignment.centerRight,
                      child: LanguageSwitch(
                        language: language,
                        onChanged: onLanguageChanged,
                      ),
                    ),
                    const SizedBox(height: 6),
                    const Align(
                      alignment: Alignment.center,
                      child: BrandMark(),
                    ),
                    const SizedBox(height: 8),
                    const Text(
                      'KalaSetu',
                      textAlign: TextAlign.center,
                      style: TextStyle(
                        color: AppColors.text,
                        fontSize: 25,
                        fontWeight: FontWeight.w700,
                      ),
                    ),
                    const SizedBox(height: 34),
                    child,
                  ],
                ),
              ),
            ),
          ),
        ),
      ),
    );
  }
}

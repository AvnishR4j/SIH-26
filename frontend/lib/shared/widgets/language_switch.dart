import 'package:flutter/material.dart';

import '../../core/localization/app_language.dart';
import '../../core/theme/app_theme.dart';

class LanguageSwitch extends StatelessWidget {
  const LanguageSwitch({
    super.key,
    required this.language,
    required this.onChanged,
  });

  final AppLanguage language;
  final ValueChanged<AppLanguage> onChanged;

  @override
  Widget build(BuildContext context) {
    return Semantics(
      label: 'Language',
      child: Row(
        mainAxisSize: MainAxisSize.min,
        children: [
          _LanguageButton(
            label: 'हिंदी',
            selected: language == AppLanguage.hindi,
            onTap: () => onChanged(AppLanguage.hindi),
          ),
          const Padding(
            padding: EdgeInsets.symmetric(horizontal: 6),
            child: Text('|', style: TextStyle(color: AppColors.border)),
          ),
          _LanguageButton(
            label: 'English',
            selected: language == AppLanguage.english,
            onTap: () => onChanged(AppLanguage.english),
          ),
        ],
      ),
    );
  }
}

class _LanguageButton extends StatelessWidget {
  const _LanguageButton({
    required this.label,
    required this.selected,
    required this.onTap,
  });

  final String label;
  final bool selected;
  final VoidCallback onTap;

  @override
  Widget build(BuildContext context) {
    return InkWell(
      borderRadius: BorderRadius.circular(4),
      onTap: onTap,
      child: Padding(
        padding: const EdgeInsets.symmetric(vertical: 4),
        child: Text(
          label,
          style: TextStyle(
            color: selected ? AppColors.accent : AppColors.mutedText,
            fontSize: 13,
            fontWeight: selected ? FontWeight.w700 : FontWeight.w500,
          ),
        ),
      ),
    );
  }
}

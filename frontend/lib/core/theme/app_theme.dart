import 'package:flutter/material.dart';

class AppColors {
  static const background = Color(0xFFFBF8F3);
  static const authBackground = Color(0xFFE9D3AA);
  static const surface = Color(0xFFFFFCF8);
  static const text = Color(0xFF2B2420);
  static const mutedText = Color(0xFF8A7F73);
  static const accent = Color(0xFFB5651D);
  static const darkAccent = Color(0xFF8F4E16);
  static const border = Color(0xFFDDD5C9);
  static const divider = Color(0xFFEAE4DA);
  static const error = Color(0xFFB3402D);
}

class AppTheme {
  static ThemeData get light {
    final colorScheme = ColorScheme.fromSeed(
      seedColor: AppColors.accent,
      brightness: Brightness.light,
      surface: AppColors.surface,
      error: AppColors.error,
    );

    return ThemeData(
      useMaterial3: true,
      colorScheme: colorScheme,
      scaffoldBackgroundColor: AppColors.background,
      fontFamily: 'sans-serif',
      textTheme: const TextTheme(
        headlineSmall: TextStyle(
          color: AppColors.text,
          fontSize: 24,
          fontWeight: FontWeight.w700,
          height: 1.25,
        ),
        titleLarge: TextStyle(
          color: AppColors.text,
          fontSize: 20,
          fontWeight: FontWeight.w700,
        ),
        bodyLarge: TextStyle(color: AppColors.text, fontSize: 16, height: 1.45),
        bodyMedium: TextStyle(
          color: AppColors.mutedText,
          fontSize: 14,
          height: 1.45,
        ),
      ),
      inputDecorationTheme: InputDecorationTheme(
        filled: true,
        fillColor: Colors.white,
        contentPadding: const EdgeInsets.symmetric(
          horizontal: 16,
          vertical: 16,
        ),
        border: OutlineInputBorder(
          borderRadius: BorderRadius.circular(10),
          borderSide: const BorderSide(color: AppColors.border),
        ),
        enabledBorder: OutlineInputBorder(
          borderRadius: BorderRadius.circular(10),
          borderSide: const BorderSide(color: AppColors.border),
        ),
        focusedBorder: OutlineInputBorder(
          borderRadius: BorderRadius.circular(10),
          borderSide: const BorderSide(color: AppColors.accent, width: 1.5),
        ),
        errorBorder: OutlineInputBorder(
          borderRadius: BorderRadius.circular(10),
          borderSide: const BorderSide(color: AppColors.error),
        ),
      ),
      filledButtonTheme: FilledButtonThemeData(
        style: FilledButton.styleFrom(
          backgroundColor: AppColors.accent,
          foregroundColor: Colors.white,
          minimumSize: const Size.fromHeight(52),
          shape: RoundedRectangleBorder(
            borderRadius: BorderRadius.circular(10),
          ),
          textStyle: const TextStyle(fontSize: 16, fontWeight: FontWeight.w700),
        ),
      ),
    );
  }
}

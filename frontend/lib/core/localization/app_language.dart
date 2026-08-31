enum AppLanguage { hindi, english }

extension AppLanguageCode on AppLanguage {
  String get code => this == AppLanguage.hindi ? 'hi' : 'en';
}

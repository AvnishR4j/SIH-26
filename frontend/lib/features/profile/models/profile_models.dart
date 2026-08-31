class MediaProcessingConsent {
  const MediaProcessingConsent({
    required this.accepted,
    required this.acceptedAt,
    required this.policyVersion,
  });

  final bool accepted;
  final DateTime? acceptedAt;
  final String policyVersion;
}

class ArtisanProfile {
  const ArtisanProfile({
    required this.id,
    required this.name,
    required this.phone,
    required this.role,
    required this.preferredLanguage,
    required this.cluster,
    required this.craftCategories,
    required this.consent,
  });

  final String id;
  final String name;
  final String phone;
  final String role;
  final String preferredLanguage;
  final String? cluster;
  final List<String> craftCategories;
  final MediaProcessingConsent consent;

  bool get hasRequiredProfile =>
      name.trim().isNotEmpty &&
      preferredLanguage.trim().isNotEmpty &&
      cluster?.trim().isNotEmpty == true &&
      craftCategories.isNotEmpty;

  bool get needsOnboarding => !hasRequiredProfile || !consent.accepted;

  ArtisanProfile copyWith({
    String? name,
    String? preferredLanguage,
    String? cluster,
    List<String>? craftCategories,
    MediaProcessingConsent? consent,
  }) {
    return ArtisanProfile(
      id: id,
      name: name ?? this.name,
      phone: phone,
      role: role,
      preferredLanguage: preferredLanguage ?? this.preferredLanguage,
      cluster: cluster ?? this.cluster,
      craftCategories: craftCategories ?? this.craftCategories,
      consent: consent ?? this.consent,
    );
  }
}

class UpdateProfileInput {
  const UpdateProfileInput({
    required this.name,
    required this.preferredLanguage,
    required this.cluster,
    required this.craftCategories,
  });

  final String name;
  final String preferredLanguage;
  final String cluster;
  final List<String> craftCategories;
}

class SetMediaConsentInput {
  const SetMediaConsentInput({
    required this.accepted,
    required this.policyVersion,
  });

  final bool accepted;
  final String policyVersion;
}

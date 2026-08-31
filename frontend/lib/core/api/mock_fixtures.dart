import '../../features/catalogue/models/catalogue_models.dart';
import '../../features/profile/models/profile_models.dart';

class MockFixtures {
  static ArtisanProfile completeProfile() {
    return ArtisanProfile(
      id: 'usr_001',
      name: 'Sita Devi',
      phone: '+919876543210',
      role: 'artisan',
      preferredLanguage: 'hi',
      cluster: 'Lucknow Chikankari SHG',
      craftCategories: const ['textile', 'embroidery'],
      consent: MediaProcessingConsent(
        accepted: true,
        acceptedAt: DateTime.parse('2026-08-29T10:20:00Z'),
        policyVersion: '2026-08-29',
      ),
    );
  }

  static CatalogueDraft newDraft({
    required String id,
    required String craftCategory,
    required DateTime now,
  }) {
    return CatalogueDraft(
      id: id,
      version: 1,
      status: 'draft',
      craftCategory: craftCategory,
      sourceLanguage: 'hi',
      initialNotes: null,
      fields: const DraftFields(),
      listing: null,
      images: const [],
      voiceNotes: const [],
      missingFields: const [],
      pricing: null,
      createdAt: now,
      updatedAt: now,
    );
  }

  static DraftListing generatedListing() {
    return const DraftListing(
      titleHi: 'हाथ की कढ़ाई वाला कॉटन दुपट्टा',
      titleEn: 'Hand Embroidered Cotton Dupatta',
      descriptionHi: 'सफेद कॉटन पर हाथ से की गई कढ़ाई वाला दुपट्टा।',
      descriptionEn: 'A white cotton dupatta with detailed hand embroidery.',
      tags: ['cotton dupatta', 'hand embroidery', 'chikankari'],
    );
  }

  static DraftFields generatedFields() {
    return const DraftFields(
      productType: 'dupatta',
      material: 'cotton',
      technique: 'chikankari embroidery',
      color: 'white',
      dimensions: null,
      quantityAvailable: 3,
      productionTimeDays: 5,
      care: 'Gentle hand wash',
      origin: 'Lucknow, Uttar Pradesh',
    );
  }
}

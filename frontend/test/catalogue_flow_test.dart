import 'package:flutter_test/flutter_test.dart';
import 'package:kalasetu/core/api/mock_api_client.dart';
import 'package:kalasetu/features/catalogue/models/catalogue_models.dart';

void main() {
  test(
    'contract mock completes draft media and generation lifecycle',
    () async {
      final api = MockApiClient();
      final profile = await api.getMe();
      expect(profile.consent.accepted, isTrue);

      final draft = await api.createDraft(
        const CreateDraftInput(craftCategory: 'textile'),
        idempotencyKey: 'create-key',
      );
      final replayedDraft = await api.createDraft(
        const CreateDraftInput(craftCategory: 'textile'),
        idempotencyKey: 'create-key',
      );
      expect(replayedDraft.id, draft.id);
      expect(draft.sourceLanguage, 'hi');

      final image = await api.uploadDraftImage(
        draft.id,
        const LocalMediaFile(path: 'mock-product.jpg', mimeType: 'image/jpeg'),
        idempotencyKey: 'image-key',
      );
      final enhancement = await api.enhanceDraftImage(
        draft.id,
        image.id,
        const EnhanceImageInput(),
        idempotencyKey: 'enhance-key',
      );
      expect(enhancement.type, 'enhance_image');

      final voice = await api.uploadVoiceNote(
        draft.id,
        const LocalMediaFile(path: 'mock-voice.m4a', mimeType: 'audio/mp4'),
        language: 'hi',
        idempotencyKey: 'voice-key',
      );
      final generation = await api.generateListing(
        draft.id,
        GenerateListingInput(voiceNoteId: voice.id, imageId: image.id),
        idempotencyKey: 'generation-key',
      );

      expect((await api.getOperation(generation.id)).status, 'running');
      expect((await api.getOperation(generation.id)).status, 'succeeded');

      final generatedDraft = await api.getDraft(draft.id);
      expect(generatedDraft.status, 'needs_confirmation');
      expect(generatedDraft.listing?.titleHi, isNotEmpty);
      expect(generatedDraft.missingFields, contains('dimensions'));

      expect((await api.getOperation(enhancement.id)).status, 'running');
      expect((await api.getOperation(enhancement.id)).status, 'succeeded');
      final enhancedDraft = await api.getDraft(draft.id);
      expect(enhancedDraft.images.first.enhancementStatus, 'succeeded');

      final reviewedDraft = await api.updateDraft(
        draft.id,
        UpdateDraftInput(
          version: enhancedDraft.version,
          fields: enhancedDraft.fields.copyWith(dimensions: '2.4 m x 1 m'),
          listing: enhancedDraft.listing!,
        ),
      );
      final imageSelectedDraft = await api.selectDraftImageVariant(
        draft.id,
        image.id,
        SelectImageVariantInput(
          version: reviewedDraft.version,
          selectedVariant: 'enhanced',
        ),
      );
      expect(imageSelectedDraft.images.first.selectedVariant, 'enhanced');

      final price = await api.suggestPrice(
        draft.id,
        PriceSuggestionInput(
          version: imageSelectedDraft.version,
          materialCostPaise: 30000,
          labourHours: 8,
          hourlyRatePaise: 5000,
          packagingCostPaise: 5000,
          logisticsBufferPaise: 0,
          benchmarkCategory: 'cotton_dupatta',
        ),
        idempotencyKey: 'price-key',
      );
      expect(price.isDemoData, isTrue);
      expect(price.recommendedPaise, greaterThan(0));

      final approved = await api.approveDraft(
        draft.id,
        ApproveDraftInput(
          version: price.draftVersion,
          approvedPricePaise: price.recommendedPaise,
          priceOverrideReason: null,
        ),
        idempotencyKey: 'approve-key',
      );
      expect(approved.status, 'approved');

      final share = await api.getShareCard(approved.publicShareId);
      expect(share.catalogId, approved.id);
      expect(share.enquiryEnabled, isTrue);

      const enquiryInput = BuyerEnquiryInput(
        buyerName: 'Aarav Retail',
        buyerPhone: '+918888888888',
        quantityRequested: 20,
        message: 'Interested in 20 pieces',
        consentToContact: true,
      );
      final enquiry = await api.submitEnquiry(
        approved.publicShareId,
        enquiryInput,
        idempotencyKey: 'enquiry-key',
      );
      final replayedEnquiry = await api.submitEnquiry(
        approved.publicShareId,
        enquiryInput,
        idempotencyKey: 'enquiry-key',
      );
      expect(enquiry.status, 'received');
      expect(replayedEnquiry.enquiryId, enquiry.enquiryId);
    },
  );
}

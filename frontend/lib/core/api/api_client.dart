import '../../features/auth/models/auth_models.dart';
import '../../features/catalogue/models/catalogue_models.dart';
import '../../features/profile/models/profile_models.dart';

abstract interface class ApiClient {
  Future<OtpRequestResponse> requestOtp(
    OtpRequest request, {
    required String idempotencyKey,
  });

  Future<AuthSession> verifyOtp(OtpVerification request);

  Future<ArtisanProfile> getMe();

  Future<ArtisanProfile> updateMe(UpdateProfileInput input);

  Future<MediaProcessingConsent> setMediaProcessingConsent(
    SetMediaConsentInput input,
  );

  Future<DraftPage> listDrafts({
    int limit = 20,
    String? cursor,
    String? status,
  });

  Future<CatalogueDraft> createDraft(
    CreateDraftInput input, {
    required String idempotencyKey,
  });

  Future<CatalogueDraft> getDraft(String draftId);

  Future<CatalogueDraft> updateDraft(String draftId, UpdateDraftInput input);

  Future<DraftImage> uploadDraftImage(
    String draftId,
    LocalMediaFile file, {
    required String idempotencyKey,
  });

  Future<ApiOperation> enhanceDraftImage(
    String draftId,
    String imageId,
    EnhanceImageInput input, {
    required String idempotencyKey,
  });

  Future<CatalogueDraft> selectDraftImageVariant(
    String draftId,
    String imageId,
    SelectImageVariantInput input,
  );

  Future<VoiceNote> uploadVoiceNote(
    String draftId,
    LocalMediaFile file, {
    required String language,
    required String idempotencyKey,
  });

  Future<ApiOperation> generateListing(
    String draftId,
    GenerateListingInput input, {
    required String idempotencyKey,
  });

  Future<ApiOperation> getOperation(String operationId);

  Future<PricingSuggestion> suggestPrice(
    String draftId,
    PriceSuggestionInput input, {
    required String idempotencyKey,
  });

  Future<ApprovedCatalogue> approveDraft(
    String draftId,
    ApproveDraftInput input, {
    required String idempotencyKey,
  });

  Future<ShareCard> getShareCard(String publicShareId);

  Future<BuyerEnquiry> submitEnquiry(
    String publicShareId,
    BuyerEnquiryInput input, {
    required String idempotencyKey,
  });
}

class ApiException implements Exception {
  const ApiException({
    required this.code,
    required this.message,
    this.details = const {},
  });

  final String code;
  final String message;
  final Map<String, Object?> details;
}

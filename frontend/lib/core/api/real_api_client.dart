import '../../features/auth/models/auth_models.dart';
import '../../features/catalogue/models/catalogue_models.dart';
import '../../features/profile/models/profile_models.dart';
import 'api_client.dart';

class RealApiClient implements ApiClient {
  RealApiClient({required this.baseUrl, required this.accessToken});

  final Uri baseUrl;
  final String? Function() accessToken;

  Never _planned() => throw const ApiException(
    code: 'NOT_CONFIGURED',
    message: 'The real API transport is not configured for this demo build.',
  );

  @override
  Future<CatalogueDraft> createDraft(
    CreateDraftInput input, {
    required String idempotencyKey,
  }) => _planned();
  @override
  Future<ApiOperation> enhanceDraftImage(
    String draftId,
    String imageId,
    EnhanceImageInput input, {
    required String idempotencyKey,
  }) => _planned();
  @override
  Future<ApiOperation> generateListing(
    String draftId,
    GenerateListingInput input, {
    required String idempotencyKey,
  }) => _planned();
  @override
  Future<CatalogueDraft> getDraft(String draftId) => _planned();
  @override
  Future<CatalogueDraft> updateDraft(String draftId, UpdateDraftInput input) =>
      _planned();
  @override
  Future<ArtisanProfile> getMe() => _planned();
  @override
  Future<ApiOperation> getOperation(String operationId) => _planned();
  @override
  Future<CatalogueDraft> selectDraftImageVariant(
    String draftId,
    String imageId,
    SelectImageVariantInput input,
  ) => _planned();
  @override
  Future<PricingSuggestion> suggestPrice(
    String draftId,
    PriceSuggestionInput input, {
    required String idempotencyKey,
  }) => _planned();
  @override
  Future<ApprovedCatalogue> approveDraft(
    String draftId,
    ApproveDraftInput input, {
    required String idempotencyKey,
  }) => _planned();
  @override
  Future<ShareCard> getShareCard(String publicShareId) => _planned();
  @override
  Future<BuyerEnquiry> submitEnquiry(
    String publicShareId,
    BuyerEnquiryInput input, {
    required String idempotencyKey,
  }) => _planned();
  @override
  Future<DraftPage> listDrafts({
    int limit = 20,
    String? cursor,
    String? status,
  }) => _planned();
  @override
  Future<OtpRequestResponse> requestOtp(
    OtpRequest request, {
    required String idempotencyKey,
  }) => _planned();
  @override
  Future<MediaProcessingConsent> setMediaProcessingConsent(
    SetMediaConsentInput input,
  ) => _planned();
  @override
  Future<ArtisanProfile> updateMe(UpdateProfileInput input) => _planned();
  @override
  Future<DraftImage> uploadDraftImage(
    String draftId,
    LocalMediaFile file, {
    required String idempotencyKey,
  }) => _planned();
  @override
  Future<VoiceNote> uploadVoiceNote(
    String draftId,
    LocalMediaFile file, {
    required String language,
    required String idempotencyKey,
  }) => _planned();
  @override
  Future<AuthSession> verifyOtp(OtpVerification request) => _planned();
}

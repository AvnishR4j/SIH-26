import '../../../core/api/api_client.dart';
import '../../../core/media/media_capture_service.dart';
import '../../../core/utils/idempotency_key.dart';
import '../models/catalogue_flow_state.dart';
import '../models/catalogue_models.dart';
import '../../profile/models/profile_models.dart';

class CatalogueFlowController {
  CatalogueFlowController(this._apiClient, {required this.media});

  final ApiClient _apiClient;
  final MediaCaptureService media;
  String? _createDraftKey;
  CatalogueFlowState? _state;

  CatalogueFlowState get state => _state!;

  String? get localImagePath => _state?.localImagePath;

  Future<CatalogueFlowState> createDraft(String craftCategory) async {
    final key = _createDraftKey ??= newIdempotencyKey();
    final draft = await _apiClient.createDraft(
      CreateDraftInput(craftCategory: craftCategory),
      idempotencyKey: key,
    );
    _state = CatalogueFlowState(draft: draft, createDraftKey: key);
    return state;
  }

  Future<LocalMediaFile?> capturePhoto() => media.capturePhoto();

  Future<LocalMediaFile?> pickPhoto() => media.pickPhoto();

  Future<void> uploadPhotoAndStartEnhancement(LocalMediaFile file) async {
    state.localImagePath = file.path;
    final image = await _apiClient.uploadDraftImage(
      state.draft.id,
      file,
      idempotencyKey: state.uploadImageKey,
    );
    state.image = image;
    final operation = await _apiClient.enhanceDraftImage(
      state.draft.id,
      image.id,
      const EnhanceImageInput(),
      idempotencyKey: state.enhanceImageKey,
    );
    state.enhancementOperationId = operation.id;
    state.draft = await _apiClient.getDraft(state.draft.id);
  }

  Future<void> startRecording() => media.startVoiceRecording();

  Future<LocalMediaFile?> stopRecording() => media.stopVoiceRecording();

  Future<void> cancelRecording() => media.cancelVoiceRecording();

  Future<ApiOperation> uploadVoiceAndGenerate(LocalMediaFile file) async {
    state.localAudioPath = file.path;
    final note = await _apiClient.uploadVoiceNote(
      state.draft.id,
      file,
      language: 'hi',
      idempotencyKey: state.uploadVoiceKey,
    );
    state.voiceNote = note;
    final operation = await _apiClient.generateListing(
      state.draft.id,
      GenerateListingInput(voiceNoteId: note.id, imageId: state.image!.id),
      idempotencyKey: state.generateListingKey,
    );
    state.generationOperationId = operation.id;
    return operation;
  }

  Future<ApiOperation> resumeGeneration() async {
    final operationId = state.generationOperationId;
    if (operationId != null) return _apiClient.getOperation(operationId);
    return _apiClient.generateListing(
      state.draft.id,
      GenerateListingInput(
        voiceNoteId: state.voiceNote!.id,
        imageId: state.image!.id,
      ),
      idempotencyKey: state.generateListingKey,
    );
  }

  Future<ApiOperation> retryFailedGeneration() async {
    state.generateListingKey = newIdempotencyKey();
    final operation = await _apiClient.generateListing(
      state.draft.id,
      GenerateListingInput(
        voiceNoteId: state.voiceNote!.id,
        imageId: state.image!.id,
      ),
      idempotencyKey: state.generateListingKey,
    );
    state.generationOperationId = operation.id;
    return operation;
  }

  Future<void> acceptMediaProcessingConsent() async {
    final profile = await _apiClient.getMe();
    await _apiClient.setMediaProcessingConsent(
      SetMediaConsentInput(
        accepted: true,
        policyVersion: profile.consent.policyVersion,
      ),
    );
  }

  Future<ApiOperation> getOperation(String id) => _apiClient.getOperation(id);

  Future<CatalogueDraft> refreshDraft() async {
    state.draft = await _apiClient.getDraft(state.draft.id);
    return state.draft;
  }

  Future<CatalogueDraft> updateDraft(
    DraftFields fields,
    DraftListing listing,
  ) async {
    state.draft = await _apiClient.updateDraft(
      state.draft.id,
      UpdateDraftInput(
        version: state.draft.version,
        fields: fields,
        listing: listing,
      ),
    );
    return state.draft;
  }

  Future<CatalogueDraft> selectImageVariant(String variant) async {
    final image = state.draft.images.firstWhere((item) => item.isPrimary);
    state.draft = await _apiClient.selectDraftImageVariant(
      state.draft.id,
      image.id,
      SelectImageVariantInput(
        version: state.draft.version,
        selectedVariant: variant,
      ),
    );
    state.image = state.draft.images.firstWhere((item) => item.isPrimary);
    return state.draft;
  }

  Future<CatalogueDraft> waitForEnhancement() async {
    final operationId = state.enhancementOperationId;
    if (operationId == null) return refreshDraft();
    final deadline = DateTime.now().add(const Duration(seconds: 60));
    var operation = await _apiClient.getOperation(operationId);
    while (operation.isPending && DateTime.now().isBefore(deadline)) {
      await Future<void>.delayed(
        Duration(seconds: operation.pollAfterSeconds.clamp(1, 10)),
      );
      operation = await _apiClient.getOperation(operationId);
    }
    if (operation.isPending) {
      throw const ApiException(
        code: 'OPERATION_PENDING',
        message:
            'Image enhancement is still running. You can check again shortly.',
      );
    }
    return refreshDraft();
  }

  Future<ApiOperation> retryEnhancement() async {
    state.enhanceImageKey = newIdempotencyKey();
    final image = state.draft.images.firstWhere((item) => item.isPrimary);
    final operation = await _apiClient.enhanceDraftImage(
      state.draft.id,
      image.id,
      const EnhanceImageInput(),
      idempotencyKey: state.enhanceImageKey,
    );
    state.enhancementOperationId = operation.id;
    return operation;
  }

  Future<PricingSuggestion> suggestPrice(PriceSuggestionInput input) async {
    final suggestion = await _apiClient.suggestPrice(
      state.draft.id,
      input,
      idempotencyKey: state.suggestPriceKey,
    );
    state.draft = await _apiClient.getDraft(state.draft.id);
    return suggestion;
  }

  void beginNewPriceSuggestion() {
    state.suggestPriceKey = newIdempotencyKey();
  }

  void chooseFinalPrice(int pricePaise, String? overrideReason) {
    state.approvedPricePaise = pricePaise;
    state.priceOverrideReason = overrideReason;
  }

  Future<ApprovedCatalogue> approveDraft() {
    return _apiClient.approveDraft(
      state.draft.id,
      ApproveDraftInput(
        version: state.draft.version,
        approvedPricePaise: state.approvedPricePaise!,
        priceOverrideReason: state.priceOverrideReason,
        approvalNote:
            'Artisan confirmed the title, image, product facts, and price.',
      ),
      idempotencyKey: state.approveDraftKey,
    );
  }

  Future<void> syncDraftToShopify(String draftId) =>
      _apiClient.syncDraftToShopify(draftId);

  Future<ShareCard> getShareCard(String publicShareId) =>
      _apiClient.getShareCard(publicShareId);

  Future<ArtisanProfile> getCurrentProfile() => _apiClient.getMe();

  Future<BuyerEnquiry> submitEnquiry(
    String publicShareId,
    BuyerEnquiryInput input, {
    required String idempotencyKey,
  }) => _apiClient.submitEnquiry(
    publicShareId,
    input,
    idempotencyKey: idempotencyKey,
  );
}

import '../../features/auth/models/auth_models.dart';
import '../../features/catalogue/models/catalogue_models.dart';
import '../../features/profile/models/profile_models.dart';
import 'api_client.dart';
import 'mock_fixtures.dart';

class MockApiClient implements ApiClient {
  final Map<String, OtpRequestResponse> _otpRequests = {};

  @override
  void restoreSession(AuthSession session) {}

  @override
  void clearSession() {}
  final Map<String, CatalogueDraft> _drafts = {};
  final Map<String, CatalogueDraft> _draftCreations = {};
  final Map<String, DraftImage> _imageUploads = {};
  final Map<String, VoiceNote> _voiceUploads = {};
  final Map<String, ApiOperation> _operationStarts = {};
  final Map<String, ApiOperation> _operations = {};
  final Map<String, int> _operationPolls = {};
  final Map<String, PricingSuggestion> _priceSuggestions = {};
  final Map<String, ApprovedCatalogue> _approvals = {};
  final Map<String, ShareCard> _shareCards = {};
  final Map<String, BuyerEnquiry> _enquiries = {};

  ArtisanProfile _profile = MockFixtures.completeProfile();
  int _draftSequence = 0;
  int _imageSequence = 0;
  int _voiceSequence = 0;
  int _operationSequence = 0;
  int _catalogueSequence = 0;
  int _enquirySequence = 0;

  @override
  Future<OtpRequestResponse> requestOtp(
    OtpRequest request, {
    required String idempotencyKey,
  }) async {
    await _latency();
    return _otpRequests.putIfAbsent(
      idempotencyKey,
      () => const OtpRequestResponse(
        requestId: 'otp_req_mock_123',
        expiresInSeconds: 300,
        retryAfterSeconds: 30,
      ),
    );
  }

  @override
  Future<AuthSession> verifyOtp(OtpVerification request) async {
    await _latency();
    if (request.otp != '123456') {
      throw const ApiException(
        code: 'VALIDATION_ERROR',
        message: 'Invalid OTP',
      );
    }
    return const AuthSession(
      accessToken: 'mock.jwt.token',
      tokenType: 'bearer',
      expiresInSeconds: 86400,
      user: ArtisanUser(
        id: 'usr_001',
        name: 'Sita Devi',
        phone: '+919876543210',
        role: 'artisan',
        preferredLanguage: 'hi',
      ),
    );
  }

  @override
  Future<ArtisanProfile> getMe() async {
    await _latency();
    return _profile;
  }

  @override
  Future<ArtisanProfile> updateMe(UpdateProfileInput input) async {
    await _latency();
    _profile = _profile.copyWith(
      name: input.name,
      preferredLanguage: input.preferredLanguage,
      cluster: input.cluster,
      craftCategories: List.unmodifiable(input.craftCategories),
    );
    return _profile;
  }

  @override
  Future<MediaProcessingConsent> setMediaProcessingConsent(
    SetMediaConsentInput input,
  ) async {
    await _latency();
    final consent = MediaProcessingConsent(
      accepted: input.accepted,
      acceptedAt: input.accepted ? DateTime.now().toUtc() : null,
      policyVersion: input.policyVersion,
    );
    _profile = _profile.copyWith(consent: consent);
    return consent;
  }

  @override
  Future<DraftPage> listDrafts({
    int limit = 20,
    String? cursor,
    String? status,
  }) async {
    await _latency();
    final drafts =
        _drafts.values
            .where((draft) => status == null || draft.status == status)
            .toList()
          ..sort((a, b) => b.updatedAt.compareTo(a.updatedAt));
    return DraftPage(
      items: drafts.take(limit).map(_summaryFor).toList(growable: false),
      nextCursor: null,
    );
  }

  @override
  Future<CatalogueDraft> createDraft(
    CreateDraftInput input, {
    required String idempotencyKey,
  }) async {
    await _latency();
    final existing = _draftCreations[idempotencyKey];
    if (existing != null) return existing;
    final now = DateTime.now().toUtc();
    final draft = MockFixtures.newDraft(
      id: 'draft_${(++_draftSequence).toString().padLeft(3, '0')}',
      craftCategory: input.craftCategory,
      now: now,
    );
    _drafts[draft.id] = draft;
    _draftCreations[idempotencyKey] = draft;
    return draft;
  }

  @override
  Future<CatalogueDraft> getDraft(String draftId) async {
    await _latency();
    return _requireDraft(draftId);
  }

  @override
  Future<void> deleteDraft(String draftId) async {
    await _latency();
    _requireDraft(draftId);
    final shareIds = _approvals.values
        .where((catalogue) => catalogue.draftId == draftId)
        .map((catalogue) => catalogue.publicShareId)
        .toList(growable: false);
    _drafts.remove(draftId);
    _approvals.removeWhere((_, catalogue) => catalogue.draftId == draftId);
    for (final shareId in shareIds) {
      _shareCards.remove(shareId);
    }
  }

  @override
  Future<CatalogueDraft> updateDraft(
    String draftId,
    UpdateDraftInput input,
  ) async {
    await _latency();
    final draft = _requireDraft(draftId);
    _requireVersion(draft, input.version);
    final updated = draft.copyWith(
      version: draft.version + 1,
      status: 'needs_confirmation',
      fields: input.fields,
      listing: input.listing,
      missingFields: const [],
    );
    _drafts[draftId] = updated;
    return updated;
  }

  @override
  Future<DraftImage> uploadDraftImage(
    String draftId,
    LocalMediaFile file, {
    required String idempotencyKey,
  }) async {
    await _latency();
    final draft = _requireDraft(draftId);
    final existing = _imageUploads[idempotencyKey];
    if (existing != null) return existing;
    final image = _imageUploads.putIfAbsent(idempotencyKey, () {
      final number = (++_imageSequence).toString().padLeft(3, '0');
      return DraftImage(
        id: 'img_$number',
        originalUrl: 'http://localhost:8000/media/img_${number}_original.jpg',
        enhancedUrl: null,
        isPrimary: true,
        selectedVariant: null,
        enhancementStatus: 'not_started',
        createdAt: DateTime.now().toUtc(),
      );
    });
    _drafts[draftId] = draft.copyWith(
      version: draft.version + 1,
      images: [image],
    );
    return image;
  }

  @override
  Future<ApiOperation> enhanceDraftImage(
    String draftId,
    String imageId,
    EnhanceImageInput input, {
    required String idempotencyKey,
  }) async {
    await _latency();
    _requireConsent();
    final operation = _operationStarts.putIfAbsent(
      idempotencyKey,
      () => _newOperation('enhance_image', draftId),
    );
    _operations.putIfAbsent(operation.id, () => operation);
    return operation;
  }

  @override
  Future<CatalogueDraft> selectDraftImageVariant(
    String draftId,
    String imageId,
    SelectImageVariantInput input,
  ) async {
    await _latency();
    final draft = _requireDraft(draftId);
    _requireVersion(draft, input.version);
    final image = draft.images.firstWhere((item) => item.id == imageId);
    if (input.selectedVariant == 'enhanced' &&
        image.enhancementStatus != 'succeeded') {
      throw const ApiException(
        code: 'INVALID_STATE',
        message: 'The enhanced image is not ready yet.',
      );
    }
    final updated = draft.copyWith(
      version: draft.version + 1,
      images: [
        for (final item in draft.images)
          item.id == imageId
              ? item.copyWith(selectedVariant: input.selectedVariant)
              : item,
      ],
    );
    _drafts[draftId] = updated;
    return updated;
  }

  @override
  Future<VoiceNote> uploadVoiceNote(
    String draftId,
    LocalMediaFile file, {
    required String language,
    required String idempotencyKey,
  }) async {
    await _latency();
    _requireConsent();
    final existing = _voiceUploads[idempotencyKey];
    if (existing != null) return existing;
    final note = _voiceUploads.putIfAbsent(idempotencyKey, () {
      final number = (++_voiceSequence).toString().padLeft(3, '0');
      return VoiceNote(
        id: 'voice_$number',
        language: language,
        status: 'uploaded',
        durationSeconds: 12,
        createdAt: DateTime.now().toUtc(),
      );
    });
    final draft = _requireDraft(draftId);
    _drafts[draftId] = draft.copyWith(
      version: draft.version + 1,
      status: 'media_ready',
      voiceNotes: [note],
    );
    return note;
  }

  @override
  Future<ApiOperation> generateListing(
    String draftId,
    GenerateListingInput input, {
    required String idempotencyKey,
  }) async {
    await _latency();
    _requireConsent();
    final operation = _operationStarts.putIfAbsent(
      idempotencyKey,
      () => _newOperation('generate_listing', draftId),
    );
    _operations.putIfAbsent(operation.id, () => operation);
    final draft = _requireDraft(draftId);
    _drafts[draftId] = draft.copyWith(status: 'processing');
    return operation;
  }

  @override
  Future<ApiOperation> getOperation(String operationId) async {
    await _latency(short: true);
    final operation = _operations[operationId];
    if (operation == null) {
      throw const ApiException(
        code: 'NOT_FOUND',
        message: 'Operation not found',
      );
    }
    final polls = (_operationPolls[operationId] ?? 0) + 1;
    _operationPolls[operationId] = polls;
    final updated = operation.copyWith(
      status: polls == 1 ? 'running' : 'succeeded',
    );
    _operations[operationId] = updated;
    if (updated.status == 'succeeded') _applyOperationResult(updated);
    return updated;
  }

  @override
  Future<PricingSuggestion> suggestPrice(
    String draftId,
    PriceSuggestionInput input, {
    required String idempotencyKey,
  }) async {
    await _latency();
    final existing = _priceSuggestions[idempotencyKey];
    if (existing != null) return existing;
    final draft = _requireDraft(draftId);
    _requireVersion(draft, input.version);
    final labourCost = (input.labourHours * input.hourlyRatePaise).round();
    final minimum =
        input.materialCostPaise +
        labourCost +
        input.packagingCostPaise +
        input.logisticsBufferPaise;
    final recommended = (minimum * 1.25).round();
    final nextVersion = draft.version + 1;
    final suggestion = PricingSuggestion(
      draftId: draftId,
      draftVersion: nextVersion,
      suggestedMinPaise: (recommended * 0.9).round(),
      suggestedMaxPaise: (recommended * 1.25).round(),
      recommendedPaise: recommended,
      confidence: 'medium',
      breakdown: PriceBreakdown(
        materialCostPaise: input.materialCostPaise,
        labourCostPaise: labourCost,
        packagingCostPaise: input.packagingCostPaise,
        logisticsBufferPaise: input.logisticsBufferPaise,
        minimumSustainablePricePaise: minimum,
        marketReferenceLowPaise: 80000,
        marketReferenceHighPaise: 140000,
      ),
      reasons: const [
        'The minimum includes material, labour, packaging, and logistics costs.',
        'The category benchmark uses a dated demo reference dataset.',
      ],
      benchmarkCategory: input.benchmarkCategory,
      benchmarkSourceLabel: 'Demo benchmark dataset',
      benchmarkSourceDate: DateTime.parse('2026-08-29'),
      isDemoData: true,
    );
    _priceSuggestions[idempotencyKey] = suggestion;
    _drafts[draftId] = draft.copyWith(
      version: nextVersion,
      status: 'ready_for_approval',
      pricing: suggestion,
    );
    return suggestion;
  }

  @override
  Future<ApprovedCatalogue> approveDraft(
    String draftId,
    ApproveDraftInput input, {
    required String idempotencyKey,
  }) async {
    await _latency();
    final existing = _approvals[idempotencyKey];
    if (existing != null) return existing;
    final draft = _requireDraft(draftId);
    _requireVersion(draft, input.version);
    final pricing = draft.pricing;
    final image = draft.images.firstWhere((item) => item.isPrimary);
    if (pricing == null ||
        pricing.draftVersion != draft.version ||
        image.selectedVariant == null ||
        draft.listing == null) {
      throw const ApiException(
        code: 'INVALID_STATE',
        message: 'Some catalogue details still need attention.',
      );
    }
    final outsideRange =
        input.approvedPricePaise < pricing.suggestedMinPaise ||
        input.approvedPricePaise > pricing.suggestedMaxPaise;
    if (outsideRange && (input.priceOverrideReason?.trim().isEmpty ?? true)) {
      throw const ApiException(
        code: 'VALIDATION_ERROR',
        message: 'Add a reason for the custom price.',
      );
    }
    final number = (++_catalogueSequence).toString().padLeft(3, '0');
    final approved = ApprovedCatalogue(
      id: 'cat_$number',
      draftId: draftId,
      status: 'approved',
      approvedPricePaise: input.approvedPricePaise,
      currency: 'INR',
      publicShareId: 'share_$number',
      publicShareUrl: 'http://localhost:3000/share/share_$number',
      createdAt: DateTime.now().toUtc(),
    );
    _approvals[idempotencyKey] = approved;
    _drafts[draftId] = draft.copyWith(
      version: draft.version + 1,
      status: 'approved',
    );
    _shareCards[approved.publicShareId] = ShareCard(
      catalogId: approved.id,
      title: draft.listing!.titleEn,
      description: draft.listing!.descriptionEn,
      imageUrl: image.selectedVariant == 'enhanced'
          ? image.enhancedUrl!
          : image.originalUrl,
      pricePaise: input.approvedPricePaise,
      currency: 'INR',
      quantityAvailable: draft.fields.quantityAvailable ?? 1,
      artisan: ShareArtisan(
        displayName: _profile.name,
        cluster: _profile.cluster,
      ),
      enquiryEnabled: true,
      publishedAt: approved.createdAt,
    );
    return approved;
  }

  @override
  Future<ApprovedCatalogue> getPublishedCatalogue(String draftId) async {
    await _latency();
    for (final catalogue in _approvals.values) {
      if (catalogue.draftId == draftId) return catalogue;
    }
    throw const ApiException(
      code: 'NOT_FOUND',
      message: 'Published catalogue not found.',
    );
  }

  @override
  Future<MarketplacePage> listMarketplaceCatalogues({
    int limit = 20,
    String? cursor,
  }) async {
    await _latency();
    final entries = _shareCards.entries
        .toList(growable: false)
        .reversed
        .toList();
    final start = cursor == null ? 0 : int.tryParse(cursor) ?? 0;
    final page = entries.skip(start).take(limit).toList(growable: false);
    final next = start + page.length;
    return MarketplacePage(
      items: page
          .map(
            (entry) => MarketplaceCatalogue(
              publicShareId: entry.key,
              title: entry.value.title,
              description: entry.value.description,
              imageUrl: entry.value.imageUrl,
              pricePaise: entry.value.pricePaise,
              currency: entry.value.currency,
              quantityAvailable: entry.value.quantityAvailable,
              artisan: entry.value.artisan,
              publishedAt: entry.value.publishedAt,
            ),
          )
          .toList(growable: false),
      nextCursor: next < entries.length ? '$next' : null,
    );
  }

  @override
  Future<void> deleteMarketplaceCatalogue(String publicShareId) async {
    await _latency();
    final approved = _approvals.values
        .where((catalogue) => catalogue.publicShareId == publicShareId)
        .firstOrNull;
    if (approved == null) {
      throw const ApiException(
        code: 'NOT_FOUND',
        message: 'Published catalogue not found.',
      );
    }
    _shareCards.remove(publicShareId);
    _drafts.remove(approved.draftId);
    _approvals.removeWhere(
      (_, catalogue) => catalogue.publicShareId == publicShareId,
    );
  }

  @override
  Future<ShareCard> getShareCard(String publicShareId) async {
    await _latency();
    final card = _shareCards[publicShareId];
    if (card == null) {
      throw const ApiException(
        code: 'NOT_FOUND',
        message: 'This catalogue is unavailable.',
      );
    }
    return card;
  }

  @override
  Future<BuyerEnquiry> submitEnquiry(
    String publicShareId,
    BuyerEnquiryInput input, {
    required String idempotencyKey,
  }) async {
    await _latency();
    if (!_shareCards.containsKey(publicShareId)) {
      throw const ApiException(
        code: 'NOT_FOUND',
        message: 'Catalogue not found',
      );
    }
    if (!input.consentToContact) {
      throw const ApiException(
        code: 'CONSENT_REQUIRED',
        message: 'Contact consent is required.',
      );
    }
    return _enquiries.putIfAbsent(
      idempotencyKey,
      () => BuyerEnquiry(
        enquiryId: 'enq_${(++_enquirySequence).toString().padLeft(3, '0')}',
        status: 'received',
        receivedAt: DateTime.now().toUtc(),
      ),
    );
  }

  ApiOperation _newOperation(String type, String draftId) {
    final now = DateTime.now().toUtc();
    return ApiOperation(
      id: 'op_${(++_operationSequence).toString().padLeft(3, '0')}',
      type: type,
      status: 'queued',
      resourceType: 'draft',
      resourceId: draftId,
      pollAfterSeconds: 1,
      error: null,
      createdAt: now,
      updatedAt: now,
    );
  }

  void _applyOperationResult(ApiOperation operation) {
    final draft = _requireDraft(operation.resourceId);
    if (operation.type == 'generate_listing') {
      _drafts[draft.id] = draft.copyWith(
        version: draft.version + 1,
        status: 'needs_confirmation',
        listing: MockFixtures.generatedListing(),
        fields: MockFixtures.generatedFields(),
        missingFields: const ['dimensions'],
      );
      return;
    }
    if (operation.type == 'enhance_image' && draft.images.isNotEmpty) {
      final image = draft.images.first;
      _drafts[draft.id] = draft.copyWith(
        images: [
          image.copyWith(
            enhancedUrl: 'http://localhost:8000/media/${image.id}_enhanced.jpg',
            enhancementStatus: 'succeeded',
          ),
        ],
      );
    }
  }

  DraftSummary _summaryFor(CatalogueDraft draft) => DraftSummary(
    id: draft.id,
    version: draft.version,
    status: draft.status,
    titleHi: draft.listing?.titleHi,
    titleEn: draft.listing?.titleEn,
    thumbnailUrl: draft.images.isEmpty ? null : draft.images.first.originalUrl,
    recommendedPricePaise: null,
    updatedAt: draft.updatedAt,
  );

  CatalogueDraft _requireDraft(String id) {
    final draft = _drafts[id];
    if (draft == null) {
      throw const ApiException(code: 'NOT_FOUND', message: 'Draft not found');
    }
    return draft;
  }

  void _requireVersion(CatalogueDraft draft, int version) {
    if (draft.version != version) {
      throw ApiException(
        code: 'VERSION_CONFLICT',
        message: 'This draft changed. Refresh and try again.',
        details: {'current_version': draft.version},
      );
    }
  }

  void _requireConsent() {
    if (!_profile.consent.accepted) {
      throw const ApiException(
        code: 'CONSENT_REQUIRED',
        message: 'Media processing consent is required.',
      );
    }
  }

  Future<void> _latency({bool short = false}) =>
      Future<void>.delayed(Duration(milliseconds: short ? 120 : 260));
}

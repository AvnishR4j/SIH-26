import 'dart:convert';
import 'dart:io';

import '../../features/auth/models/auth_models.dart';
import '../../features/catalogue/models/catalogue_models.dart';
import '../../features/profile/models/profile_models.dart';
import 'api_client.dart';

class RealApiClient implements ApiClient {
  RealApiClient({required this.baseUrl, HttpClient? client})
    : _client = client ?? HttpClient();
  final Uri baseUrl;
  final HttpClient _client;
  String? _token;

  @override
  void restoreSession(AuthSession session) => _token = session.accessToken;

  @override
  void clearSession() => _token = null;

  Uri _url(String path, [Map<String, String>? query]) {
    final root = baseUrl.path.endsWith('/')
        ? baseUrl.path.substring(0, baseUrl.path.length - 1)
        : baseUrl.path;
    return baseUrl.replace(path: '$root/$path', queryParameters: query);
  }

  Future<Map<String, dynamic>> _request(
    String method,
    String path, {
    Object? body,
    String? key,
    bool auth = true,
    Map<String, String>? query,
  }) async {
    try {
      final request = await _client.openUrl(method, _url(path, query));
      _headers(request, auth, key);
      request.headers.contentType = ContentType.json;
      if (body != null) request.write(jsonEncode(body));
      return await _response(request);
    } on SocketException {
      throw const ApiException(
        code: 'NETWORK_ERROR',
        message: 'Could not reach KalaSetu. Check the network and try again.',
      );
    } on HttpException {
      throw const ApiException(
        code: 'NETWORK_ERROR',
        message: 'Could not reach KalaSetu. Check the network and try again.',
      );
    }
  }

  Future<Map<String, dynamic>> _upload(
    String path,
    LocalMediaFile file,
    String field,
    String key,
    Map<String, String> fields,
  ) async {
    try {
      final request = await _client.postUrl(_url(path));
      _headers(request, true, key);
      final boundary = 'kalasetu-${DateTime.now().microsecondsSinceEpoch}';
      request.headers.contentType = ContentType(
        'multipart',
        'form-data',
        parameters: {'boundary': boundary},
      );
      for (final item in fields.entries) {
        request.write(
          '--$boundary\r\nContent-Disposition: form-data; name="${item.key}"\r\n\r\n${item.value}\r\n',
        );
      }
      final name = file.path.split(Platform.pathSeparator).last;
      request.write(
        '--$boundary\r\nContent-Disposition: form-data; name="$field"; filename="$name"\r\nContent-Type: ${file.mimeType}\r\n\r\n',
      );
      request.add(await File(file.path).readAsBytes());
      request.write('\r\n--$boundary--\r\n');
      return await _response(request);
    } on FileSystemException {
      throw const ApiException(
        code: 'MEDIA_UNAVAILABLE',
        message: 'The selected media file is no longer available.',
      );
    }
  }

  void _headers(HttpClientRequest request, bool auth, String? key) {
    request.headers.set(HttpHeaders.acceptHeader, 'application/json');
    if (auth) {
      if (_token == null) {
        throw const ApiException(
          code: 'UNAUTHENTICATED',
          message: 'Please sign in again.',
        );
      }
      request.headers.set(HttpHeaders.authorizationHeader, 'Bearer $_token');
    }
    if (key != null) request.headers.set('Idempotency-Key', key);
  }

  Future<Map<String, dynamic>> _response(HttpClientRequest request) async {
    final response = await request.close();
    final text = await utf8.decodeStream(response);
    final data = text.isEmpty
        ? <String, dynamic>{}
        : (jsonDecode(text) as Map).cast<String, dynamic>();
    if (response.statusCode < 200 || response.statusCode >= 300) {
      final error = data['error'] is Map
          ? (data['error'] as Map).cast<String, dynamic>()
          : <String, dynamic>{};
      throw ApiException(
        code: error['code'] as String? ?? 'HTTP_${response.statusCode}',
        message:
            error['message'] as String? ??
            'KalaSetu could not complete that request.',
        details: error['details'] is Map
            ? (error['details'] as Map).cast<String, Object?>()
            : const {},
      );
    }
    return data;
  }

  int _i(dynamic value) => (value as num).toInt();
  DateTime _d(dynamic value) => DateTime.parse(value as String).toUtc();
  List<String> _s(dynamic value) => (value as List? ?? const []).cast<String>();
  DraftFields _fields(Map<String, dynamic> v) => DraftFields(
    productType: v['product_type'] as String?,
    material: v['material'] as String?,
    technique: v['technique'] as String?,
    color: v['color'] as String?,
    dimensions: v['dimensions'] as String?,
    quantityAvailable: v['quantity_available'] == null
        ? null
        : _i(v['quantity_available']),
    productionTimeDays: v['production_time_days'] == null
        ? null
        : _i(v['production_time_days']),
    care: v['care'] as String?,
    origin: v['origin'] as String?,
  );
  DraftListing _listing(Map<String, dynamic> v) => DraftListing(
    titleHi: v['title_hi'] as String? ?? '',
    titleEn: v['title_en'] as String? ?? '',
    descriptionHi: v['description_hi'] as String? ?? '',
    descriptionEn: v['description_en'] as String? ?? '',
    tags: _s(v['tags']),
  );
  DraftImage _image(Map<String, dynamic> v) => DraftImage(
    id: v['id'] as String,
    originalUrl: v['original_url'] as String,
    enhancedUrl: v['enhanced_url'] as String?,
    isPrimary: v['is_primary'] as bool,
    selectedVariant: v['selected_variant'] as String?,
    enhancementStatus: v['enhancement_status'] as String,
    createdAt: _d(v['created_at']),
  );
  VoiceNote _voice(Map<String, dynamic> v) => VoiceNote(
    id: v['id'] as String,
    language: v['language'] as String,
    status: v['status'] as String,
    durationSeconds: _i(v['duration_seconds']),
    createdAt: _d(v['created_at']),
  );
  PricingSuggestion _price(Map<String, dynamic> v) {
    final b = (v['breakdown'] as Map).cast<String, dynamic>();
    return PricingSuggestion(
      draftId: v['draft_id'] as String,
      draftVersion: _i(v['draft_version']),
      suggestedMinPaise: _i(v['suggested_min_paise']),
      suggestedMaxPaise: _i(v['suggested_max_paise']),
      recommendedPaise: _i(v['recommended_paise']),
      confidence: v['confidence'] as String,
      breakdown: PriceBreakdown(
        materialCostPaise: _i(b['material_cost_paise']),
        labourCostPaise: _i(b['labour_cost_paise']),
        packagingCostPaise: _i(b['packaging_cost_paise']),
        logisticsBufferPaise: _i(b['logistics_buffer_paise']),
        minimumSustainablePricePaise: _i(b['minimum_sustainable_price_paise']),
        marketReferenceLowPaise: _i(b['market_reference_low_paise']),
        marketReferenceHighPaise: _i(b['market_reference_high_paise']),
      ),
      reasons: _s(v['reasons']),
      benchmarkCategory: v['benchmark_category'] as String,
      benchmarkSourceLabel: v['benchmark_source_label'] as String,
      benchmarkSourceDate: _d(v['benchmark_source_date']),
      isDemoData: v['is_demo_data'] as bool,
    );
  }

  CatalogueDraft _draft(Map<String, dynamic> v) => CatalogueDraft(
    id: v['id'] as String,
    version: _i(v['version']),
    status: v['status'] as String,
    craftCategory: v['craft_category'] as String,
    sourceLanguage: v['source_language'] as String,
    initialNotes: v['initial_notes'] as String?,
    fields: _fields((v['fields'] as Map).cast<String, dynamic>()),
    listing: v['listing'] == null
        ? null
        : _listing((v['listing'] as Map).cast<String, dynamic>()),
    images: (v['images'] as List)
        .map((x) => _image((x as Map).cast<String, dynamic>()))
        .toList(),
    voiceNotes: (v['voice_notes'] as List)
        .map((x) => _voice((x as Map).cast<String, dynamic>()))
        .toList(),
    missingFields: _s(v['missing_fields']),
    pricing: v['pricing'] == null
        ? null
        : _price((v['pricing'] as Map).cast<String, dynamic>()),
    createdAt: _d(v['created_at']),
    updatedAt: _d(v['updated_at']),
  );
  ApiOperation _operation(Map<String, dynamic> v) {
    final raw = v['error'];
    final error = raw is Map
        ? OperationError(
            code: raw['code'] as String,
            message: raw['message'] as String,
            details: raw['details'] is Map
                ? (raw['details'] as Map).cast<String, Object?>()
                : const {},
          )
        : null;
    return ApiOperation(
      id: v['id'] as String,
      type: v['type'] as String,
      status: v['status'] as String,
      resourceType: v['resource_type'] as String,
      resourceId: v['resource_id'] as String,
      pollAfterSeconds: _i(v['poll_after_seconds']),
      error: error,
      createdAt: _d(v['created_at']),
      updatedAt: _d(v['updated_at']),
    );
  }

  @override
  Future<OtpRequestResponse> requestOtp(
    OtpRequest x, {
    required String idempotencyKey,
  }) async {
    final v = await _request(
      'POST',
      'auth/request-otp',
      body: x.toJson(),
      key: idempotencyKey,
      auth: false,
    );
    return OtpRequestResponse(
      requestId: v['request_id'] as String,
      expiresInSeconds: _i(v['expires_in_seconds']),
      retryAfterSeconds: _i(v['retry_after_seconds']),
    );
  }

  @override
  Future<AuthSession> verifyOtp(OtpVerification x) async {
    final v = await _request(
      'POST',
      'auth/verify-otp',
      body: x.toJson(),
      auth: false,
    );
    final u = (v['user'] as Map).cast<String, dynamic>();
    final session = AuthSession(
      accessToken: v['access_token'] as String,
      tokenType: v['token_type'] as String,
      expiresInSeconds: _i(v['expires_in_seconds']),
      user: ArtisanUser(
        id: u['id'] as String,
        name: u['name'] as String,
        phone: u['phone'] as String,
        role: u['role'] as String,
        preferredLanguage: u['preferred_language'] as String,
      ),
    );
    restoreSession(session);
    return session;
  }

  @override
  Future<ArtisanProfile> getMe() async => _profile(await _request('GET', 'me'));
  ArtisanProfile _profile(Map<String, dynamic> v) {
    final c = (v['consent'] as Map).cast<String, dynamic>();
    return ArtisanProfile(
      id: v['id'] as String,
      name: v['name'] as String,
      phone: v['phone'] as String,
      role: v['role'] as String,
      preferredLanguage: v['preferred_language'] as String,
      cluster: v['cluster'] as String?,
      craftCategories: _s(v['craft_categories']),
      consent: MediaProcessingConsent(
        accepted: c['media_processing_accepted'] as bool,
        acceptedAt: c['media_processing_accepted_at'] == null
            ? null
            : _d(c['media_processing_accepted_at']),
        policyVersion: c['policy_version'] as String,
      ),
    );
  }

  @override
  Future<ArtisanProfile> updateMe(UpdateProfileInput x) async => _profile(
    await _request(
      'PATCH',
      'me',
      body: {
        'name': x.name,
        'preferred_language': x.preferredLanguage,
        'cluster': x.cluster,
        'craft_categories': x.craftCategories,
      },
    ),
  );
  @override
  Future<MediaProcessingConsent> setMediaProcessingConsent(
    SetMediaConsentInput x,
  ) async {
    final v = await _request(
      'PUT',
      'me/consents/media-processing',
      body: {'accepted': x.accepted, 'policy_version': x.policyVersion},
    );
    return MediaProcessingConsent(
      accepted: v['media_processing_accepted'] as bool,
      acceptedAt: v['media_processing_accepted_at'] == null
          ? null
          : _d(v['media_processing_accepted_at']),
      policyVersion: v['policy_version'] as String,
    );
  }

  @override
  Future<DraftPage> listDrafts({
    int limit = 20,
    String? cursor,
    String? status,
  }) async {
    final q = {
      'limit': '$limit',
      ...?(cursor == null ? null : {'cursor': cursor}),
      ...?(status == null ? null : {'status': status}),
    };
    final v = await _request('GET', 'catalog/drafts', query: q);
    return DraftPage(
      items: (v['items'] as List).map((x) {
        final m = (x as Map).cast<String, dynamic>();
        return DraftSummary(
          id: m['id'] as String,
          version: _i(m['version']),
          status: m['status'] as String,
          titleHi: m['title_hi'] as String?,
          titleEn: m['title_en'] as String?,
          thumbnailUrl: m['thumbnail_url'] as String?,
          recommendedPricePaise: m['recommended_price_paise'] == null
              ? null
              : _i(m['recommended_price_paise']),
          updatedAt: _d(m['updated_at']),
        );
      }).toList(),
      nextCursor: v['next_cursor'] as String?,
    );
  }

  @override
  Future<CatalogueDraft> createDraft(
    CreateDraftInput x, {
    required String idempotencyKey,
  }) async => _draft(
    await _request(
      'POST',
      'catalog/drafts',
      body: {
        'craft_category': x.craftCategory,
        'source_language': x.sourceLanguage,
        'initial_notes': x.initialNotes,
      },
      key: idempotencyKey,
    ),
  );
  @override
  Future<CatalogueDraft> getDraft(String id) async =>
      _draft(await _request('GET', 'catalog/drafts/$id'));
  @override
  Future<void> deleteDraft(String id) async {
    await _request('DELETE', 'catalog/drafts/$id');
  }

  @override
  Future<CatalogueDraft> updateDraft(String id, UpdateDraftInput x) async =>
      _draft(
        await _request(
          'PATCH',
          'catalog/drafts/$id',
          body: {
            'version': x.version,
            'fields': {
              'product_type': x.fields.productType,
              'material': x.fields.material,
              'technique': x.fields.technique,
              'color': x.fields.color,
              'dimensions': x.fields.dimensions,
              'quantity_available': x.fields.quantityAvailable,
              'production_time_days': x.fields.productionTimeDays,
              'care': x.fields.care,
              'origin': x.fields.origin,
            }..removeWhere((k, v) => v == null),
            'listing': {
              'title_hi': x.listing.titleHi,
              'title_en': x.listing.titleEn,
              'description_hi': x.listing.descriptionHi,
              'description_en': x.listing.descriptionEn,
              'tags': x.listing.tags,
            },
          },
        ),
      );
  @override
  Future<DraftImage> uploadDraftImage(
    String id,
    LocalMediaFile x, {
    required String idempotencyKey,
  }) async => _image(
    await _upload('catalog/drafts/$id/images', x, 'image', idempotencyKey, {
      'is_primary': 'true',
    }),
  );
  @override
  Future<ApiOperation> enhanceDraftImage(
    String id,
    String image,
    EnhanceImageInput x, {
    required String idempotencyKey,
  }) async => _operation(
    await _request(
      'POST',
      'catalog/drafts/$id/images/$image/enhance',
      body: {
        'background': x.background,
        'crop_style': x.cropStyle,
        'preserve_original': x.preserveOriginal,
      },
      key: idempotencyKey,
    ),
  );
  @override
  Future<CatalogueDraft> selectDraftImageVariant(
    String id,
    String image,
    SelectImageVariantInput x,
  ) async => _draft(
    await _request(
      'PATCH',
      'catalog/drafts/$id/images/$image',
      body: {'version': x.version, 'selected_variant': x.selectedVariant},
    ),
  );
  @override
  Future<VoiceNote> uploadVoiceNote(
    String id,
    LocalMediaFile x, {
    required String language,
    required String idempotencyKey,
  }) async => _voice(
    await _upload(
      'catalog/drafts/$id/voice-notes',
      x,
      'audio',
      idempotencyKey,
      {'language': language},
    ),
  );
  @override
  Future<ApiOperation> generateListing(
    String id,
    GenerateListingInput x, {
    required String idempotencyKey,
  }) async => _operation(
    await _request(
      'POST',
      'catalog/drafts/$id/generate-listing',
      body: {
        'voice_note_id': x.voiceNoteId,
        'image_id': x.imageId,
        'target_languages': x.targetLanguages,
      },
      key: idempotencyKey,
    ),
  );
  @override
  Future<ApiOperation> getOperation(String id) async =>
      _operation(await _request('GET', 'operations/$id'));
  @override
  Future<PricingSuggestion> suggestPrice(
    String id,
    PriceSuggestionInput x, {
    required String idempotencyKey,
  }) async => _price(
    await _request(
      'POST',
      'catalog/drafts/$id/pricing/suggest',
      body: {
        'version': x.version,
        'material_cost_paise': x.materialCostPaise,
        'labour_hours': x.labourHours,
        'hourly_rate_paise': x.hourlyRatePaise,
        'packaging_cost_paise': x.packagingCostPaise,
        'logistics_buffer_paise': x.logisticsBufferPaise,
        'benchmark_category': x.benchmarkCategory,
      },
      key: idempotencyKey,
    ),
  );
  @override
  Future<ApprovedCatalogue> approveDraft(
    String id,
    ApproveDraftInput x, {
    required String idempotencyKey,
  }) async {
    final v = await _request(
      'POST',
      'catalog/drafts/$id/approve',
      body: {
        'version': x.version,
        'approved_price_paise': x.approvedPricePaise,
        'price_override_reason': x.priceOverrideReason,
        'approval_note': x.approvalNote,
      },
      key: idempotencyKey,
    );
    return ApprovedCatalogue(
      id: v['id'] as String,
      draftId: v['draft_id'] as String,
      status: v['status'] as String,
      approvedPricePaise: _i(v['approved_price_paise']),
      currency: v['currency'] as String,
      publicShareId: v['public_share_id'] as String,
      publicShareUrl: v['public_share_url'] as String,
      createdAt: _d(v['created_at']),
    );
  }

  @override
  Future<ApprovedCatalogue> getPublishedCatalogue(String id) async {
    final v = await _request('GET', 'catalog/drafts/$id/published');
    return ApprovedCatalogue(
      id: v['id'] as String,
      draftId: v['draft_id'] as String,
      status: v['status'] as String,
      approvedPricePaise: _i(v['approved_price_paise']),
      currency: v['currency'] as String,
      publicShareId: v['public_share_id'] as String,
      publicShareUrl: v['public_share_url'] as String,
      createdAt: _d(v['created_at']),
    );
  }

  @override
  Future<void> syncDraftToShopify(String id) async {
    await _request('POST', 'catalog/drafts/$id/shopify');
  }

  @override
  Future<MarketplacePage> listMarketplaceCatalogues({
    int limit = 20,
    String? cursor,
  }) async {
    final v = await _request(
      'GET',
      'marketplace/catalogues',
      auth: false,
      query: {'limit': '$limit', ?cursor: cursor},
    );
    return MarketplacePage(
      items: (v['items'] as List)
          .cast<Map>()
          .map((item) {
            final artisan = (item['artisan'] as Map).cast<String, dynamic>();
            return MarketplaceCatalogue(
              publicShareId: item['public_share_id'] as String,
              title: item['title'] as String,
              description: item['description'] as String,
              imageUrl: item['image_url'] as String,
              pricePaise: _i(item['price_paise']),
              currency: item['currency'] as String,
              quantityAvailable: _i(item['quantity_available']),
              artisan: ShareArtisan(
                displayName: artisan['display_name'] as String,
                cluster: artisan['cluster'] as String?,
              ),
              publishedAt: _d(item['published_at']),
            );
          })
          .toList(growable: false),
      nextCursor: v['next_cursor'] as String?,
    );
  }

  @override
  Future<void> deleteMarketplaceCatalogue(String publicShareId) async {
    await _request('DELETE', 'marketplace/catalogues/$publicShareId');
  }

  @override
  Future<ShareCard> getShareCard(String id) async {
    final v = await _request('GET', 'share/$id', auth: false);
    final a = (v['artisan'] as Map).cast<String, dynamic>();
    return ShareCard(
      catalogId: v['catalog_id'] as String,
      title: v['title'] as String,
      description: v['description'] as String,
      imageUrl: v['image_url'] as String,
      pricePaise: _i(v['price_paise']),
      currency: v['currency'] as String,
      quantityAvailable: _i(v['quantity_available']),
      artisan: ShareArtisan(
        displayName: a['display_name'] as String,
        cluster: a['cluster'] as String?,
      ),
      enquiryEnabled: v['enquiry_enabled'] as bool,
      publishedAt: _d(v['published_at']),
    );
  }

  @override
  Future<BuyerEnquiry> submitEnquiry(
    String id,
    BuyerEnquiryInput x, {
    required String idempotencyKey,
  }) async {
    final v = await _request(
      'POST',
      'share/$id/enquiries',
      auth: false,
      key: idempotencyKey,
      body: {
        'buyer_name': x.buyerName,
        'buyer_phone': x.buyerPhone,
        'quantity_requested': x.quantityRequested,
        'message': x.message,
        'consent_to_contact': x.consentToContact,
      },
    );
    return BuyerEnquiry(
      enquiryId: v['enquiry_id'] as String,
      status: v['status'] as String,
      receivedAt: _d(v['received_at']),
    );
  }
}

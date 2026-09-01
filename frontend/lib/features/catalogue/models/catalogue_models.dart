class LocalMediaFile {
  const LocalMediaFile({required this.path, required this.mimeType});

  final String path;
  final String mimeType;
}

class DraftFields {
  const DraftFields({
    this.productType,
    this.material,
    this.technique,
    this.color,
    this.dimensions,
    this.quantityAvailable,
    this.productionTimeDays,
    this.care,
    this.origin,
  });

  final String? productType;
  final String? material;
  final String? technique;
  final String? color;
  final String? dimensions;
  final int? quantityAvailable;
  final int? productionTimeDays;
  final String? care;
  final String? origin;

  DraftFields copyWith({
    String? productType,
    String? material,
    String? technique,
    String? color,
    String? dimensions,
    int? quantityAvailable,
    int? productionTimeDays,
    String? care,
    String? origin,
  }) {
    return DraftFields(
      productType: productType ?? this.productType,
      material: material ?? this.material,
      technique: technique ?? this.technique,
      color: color ?? this.color,
      dimensions: dimensions ?? this.dimensions,
      quantityAvailable: quantityAvailable ?? this.quantityAvailable,
      productionTimeDays: productionTimeDays ?? this.productionTimeDays,
      care: care ?? this.care,
      origin: origin ?? this.origin,
    );
  }
}

class DraftListing {
  const DraftListing({
    required this.titleHi,
    required this.titleEn,
    required this.descriptionHi,
    required this.descriptionEn,
    required this.tags,
  });

  final String titleHi;
  final String titleEn;
  final String descriptionHi;
  final String descriptionEn;
  final List<String> tags;

  DraftListing copyWith({
    String? titleHi,
    String? titleEn,
    String? descriptionHi,
    String? descriptionEn,
    List<String>? tags,
  }) {
    return DraftListing(
      titleHi: titleHi ?? this.titleHi,
      titleEn: titleEn ?? this.titleEn,
      descriptionHi: descriptionHi ?? this.descriptionHi,
      descriptionEn: descriptionEn ?? this.descriptionEn,
      tags: tags ?? this.tags,
    );
  }
}

class DraftImage {
  const DraftImage({
    required this.id,
    required this.originalUrl,
    required this.enhancedUrl,
    required this.isPrimary,
    required this.selectedVariant,
    required this.enhancementStatus,
    required this.createdAt,
  });

  final String id;
  final String originalUrl;
  final String? enhancedUrl;
  final bool isPrimary;
  final String? selectedVariant;
  final String enhancementStatus;
  final DateTime createdAt;

  DraftImage copyWith({
    String? enhancedUrl,
    String? selectedVariant,
    String? enhancementStatus,
  }) {
    return DraftImage(
      id: id,
      originalUrl: originalUrl,
      enhancedUrl: enhancedUrl ?? this.enhancedUrl,
      isPrimary: isPrimary,
      selectedVariant: selectedVariant ?? this.selectedVariant,
      enhancementStatus: enhancementStatus ?? this.enhancementStatus,
      createdAt: createdAt,
    );
  }
}

class VoiceNote {
  const VoiceNote({
    required this.id,
    required this.language,
    required this.status,
    required this.durationSeconds,
    required this.createdAt,
  });

  final String id;
  final String language;
  final String status;
  final int durationSeconds;
  final DateTime createdAt;
}

class CatalogueDraft {
  const CatalogueDraft({
    required this.id,
    required this.version,
    required this.status,
    required this.craftCategory,
    required this.sourceLanguage,
    required this.initialNotes,
    required this.fields,
    required this.listing,
    required this.images,
    required this.voiceNotes,
    required this.missingFields,
    required this.pricing,
    required this.createdAt,
    required this.updatedAt,
  });

  final String id;
  final int version;
  final String status;
  final String craftCategory;
  final String sourceLanguage;
  final String? initialNotes;
  final DraftFields fields;
  final DraftListing? listing;
  final List<DraftImage> images;
  final List<VoiceNote> voiceNotes;
  final List<String> missingFields;
  final PricingSuggestion? pricing;
  final DateTime createdAt;
  final DateTime updatedAt;

  CatalogueDraft copyWith({
    int? version,
    String? status,
    DraftFields? fields,
    DraftListing? listing,
    List<DraftImage>? images,
    List<VoiceNote>? voiceNotes,
    List<String>? missingFields,
    PricingSuggestion? pricing,
  }) {
    return CatalogueDraft(
      id: id,
      version: version ?? this.version,
      status: status ?? this.status,
      craftCategory: craftCategory,
      sourceLanguage: sourceLanguage,
      initialNotes: initialNotes,
      fields: fields ?? this.fields,
      listing: listing ?? this.listing,
      images: images ?? this.images,
      voiceNotes: voiceNotes ?? this.voiceNotes,
      missingFields: missingFields ?? this.missingFields,
      pricing: pricing ?? this.pricing,
      createdAt: createdAt,
      updatedAt: DateTime.now().toUtc(),
    );
  }
}

class DraftSummary {
  const DraftSummary({
    required this.id,
    required this.version,
    required this.status,
    required this.titleHi,
    required this.titleEn,
    required this.thumbnailUrl,
    required this.recommendedPricePaise,
    required this.updatedAt,
  });

  final String id;
  final int version;
  final String status;
  final String? titleHi;
  final String? titleEn;
  final String? thumbnailUrl;
  final int? recommendedPricePaise;
  final DateTime updatedAt;
}

class DraftPage {
  const DraftPage({required this.items, required this.nextCursor});

  final List<DraftSummary> items;
  final String? nextCursor;
}

class CreateDraftInput {
  const CreateDraftInput({
    required this.craftCategory,
    this.sourceLanguage = 'hi',
    this.initialNotes,
  });

  final String craftCategory;
  final String sourceLanguage;
  final String? initialNotes;
}

class EnhanceImageInput {
  const EnhanceImageInput({
    this.background = 'neutral',
    this.cropStyle = 'marketplace_square',
    this.preserveOriginal = true,
  });

  final String background;
  final String cropStyle;
  final bool preserveOriginal;
}

class GenerateListingInput {
  const GenerateListingInput({
    required this.voiceNoteId,
    required this.imageId,
    this.targetLanguages = const ['hi', 'en'],
  });

  final String voiceNoteId;
  final String imageId;
  final List<String> targetLanguages;
}

class UpdateDraftInput {
  const UpdateDraftInput({
    required this.version,
    required this.fields,
    required this.listing,
  });

  final int version;
  final DraftFields fields;
  final DraftListing listing;
}

class SelectImageVariantInput {
  const SelectImageVariantInput({
    required this.version,
    required this.selectedVariant,
  });

  final int version;
  final String selectedVariant;
}

class PriceSuggestionInput {
  const PriceSuggestionInput({
    required this.version,
    required this.materialCostPaise,
    required this.labourHours,
    required this.hourlyRatePaise,
    required this.packagingCostPaise,
    required this.logisticsBufferPaise,
    required this.benchmarkCategory,
    this.material,
  });

  final int version;
  final int materialCostPaise;
  final double labourHours;
  final int hourlyRatePaise;
  final int packagingCostPaise;
  final int logisticsBufferPaise;
  final String benchmarkCategory;
  final String? material;
}

class PriceBreakdown {
  const PriceBreakdown({
    required this.materialCostPaise,
    required this.labourCostPaise,
    required this.packagingCostPaise,
    required this.logisticsBufferPaise,
    required this.minimumSustainablePricePaise,
    required this.marketReferenceLowPaise,
    required this.marketReferenceHighPaise,
  });

  final int materialCostPaise;
  final int labourCostPaise;
  final int packagingCostPaise;
  final int logisticsBufferPaise;
  final int minimumSustainablePricePaise;
  final int marketReferenceLowPaise;
  final int marketReferenceHighPaise;
}

class PricingSuggestion {
  const PricingSuggestion({
    required this.draftId,
    required this.draftVersion,
    required this.suggestedMinPaise,
    required this.suggestedMaxPaise,
    required this.recommendedPaise,
    required this.confidence,
    required this.breakdown,
    required this.reasons,
    required this.benchmarkCategory,
    required this.benchmarkSourceLabel,
    required this.benchmarkSourceDate,
    required this.isDemoData,
    this.material,
    this.materialRate,
  });

  final String draftId;
  final int draftVersion;
  final int suggestedMinPaise;
  final int suggestedMaxPaise;
  final int recommendedPaise;
  final String confidence;
  final PriceBreakdown breakdown;
  final List<String> reasons;
  final String benchmarkCategory;
  final String benchmarkSourceLabel;
  final DateTime benchmarkSourceDate;
  final bool isDemoData;
  final String? material;
  final MaterialRate? materialRate;
}

class MaterialRate {
  const MaterialRate({
    required this.material,
    required this.unit,
    required this.ratePaisePerUnit,
    required this.sourceLabel,
    required this.sourceDate,
    required this.isDemoData,
  });

  final String material;
  final String unit;
  final int ratePaisePerUnit;
  final String sourceLabel;
  final DateTime sourceDate;
  final bool isDemoData;
}

class ApproveDraftInput {
  const ApproveDraftInput({
    required this.version,
    required this.approvedPricePaise,
    required this.priceOverrideReason,
    this.approvalNote,
  });

  final int version;
  final int approvedPricePaise;
  final String? priceOverrideReason;
  final String? approvalNote;
}

class ApprovedCatalogue {
  const ApprovedCatalogue({
    required this.id,
    required this.draftId,
    required this.status,
    required this.approvedPricePaise,
    required this.currency,
    required this.publicShareId,
    required this.publicShareUrl,
    required this.createdAt,
  });

  final String id;
  final String draftId;
  final String status;
  final int approvedPricePaise;
  final String currency;
  final String publicShareId;
  final String publicShareUrl;
  final DateTime createdAt;
}

class ShareArtisan {
  const ShareArtisan({required this.displayName, required this.cluster});

  final String displayName;
  final String? cluster;
}

class ShareCard {
  const ShareCard({
    required this.catalogId,
    required this.title,
    required this.description,
    required this.imageUrl,
    required this.pricePaise,
    required this.currency,
    required this.quantityAvailable,
    required this.artisan,
    required this.enquiryEnabled,
    required this.publishedAt,
  });

  final String catalogId;
  final String title;
  final String description;
  final String imageUrl;
  final int pricePaise;
  final String currency;
  final int quantityAvailable;
  final ShareArtisan artisan;
  final bool enquiryEnabled;
  final DateTime publishedAt;
}

class MarketplaceCatalogue {
  const MarketplaceCatalogue({
    required this.publicShareId,
    required this.title,
    required this.description,
    required this.imageUrl,
    required this.pricePaise,
    required this.currency,
    required this.quantityAvailable,
    required this.artisan,
    required this.publishedAt,
  });

  final String publicShareId;
  final String title;
  final String description;
  final String imageUrl;
  final int pricePaise;
  final String currency;
  final int quantityAvailable;
  final ShareArtisan artisan;
  final DateTime publishedAt;
}

class MarketplacePage {
  const MarketplacePage({required this.items, required this.nextCursor});

  final List<MarketplaceCatalogue> items;
  final String? nextCursor;
}

class BuyerEnquiryInput {
  const BuyerEnquiryInput({
    required this.buyerName,
    required this.buyerPhone,
    required this.quantityRequested,
    required this.message,
    required this.consentToContact,
  });

  final String buyerName;
  final String buyerPhone;
  final int quantityRequested;
  final String? message;
  final bool consentToContact;
}

class BuyerEnquiry {
  const BuyerEnquiry({
    required this.enquiryId,
    required this.status,
    required this.receivedAt,
  });

  final String enquiryId;
  final String status;
  final DateTime receivedAt;
}

class OperationError {
  const OperationError({
    required this.code,
    required this.message,
    this.details = const {},
  });

  final String code;
  final String message;
  final Map<String, Object?> details;
}

class ApiOperation {
  const ApiOperation({
    required this.id,
    required this.type,
    required this.status,
    required this.resourceType,
    required this.resourceId,
    required this.pollAfterSeconds,
    required this.error,
    required this.createdAt,
    required this.updatedAt,
  });

  final String id;
  final String type;
  final String status;
  final String resourceType;
  final String resourceId;
  final int pollAfterSeconds;
  final OperationError? error;
  final DateTime createdAt;
  final DateTime updatedAt;

  bool get isPending => status == 'queued' || status == 'running';

  ApiOperation copyWith({String? status, OperationError? error}) {
    return ApiOperation(
      id: id,
      type: type,
      status: status ?? this.status,
      resourceType: resourceType,
      resourceId: resourceId,
      pollAfterSeconds: pollAfterSeconds,
      error: error ?? this.error,
      createdAt: createdAt,
      updatedAt: DateTime.now().toUtc(),
    );
  }
}

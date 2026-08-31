import '../../../core/utils/idempotency_key.dart';
import 'catalogue_models.dart';

class CatalogueFlowState {
  CatalogueFlowState({required this.draft, required this.createDraftKey})
    : uploadImageKey = newIdempotencyKey(),
      enhanceImageKey = newIdempotencyKey(),
      uploadVoiceKey = newIdempotencyKey(),
      generateListingKey = newIdempotencyKey(),
      suggestPriceKey = newIdempotencyKey(),
      approveDraftKey = newIdempotencyKey();

  CatalogueDraft draft;
  DraftImage? image;
  VoiceNote? voiceNote;
  String? localImagePath;
  String? localAudioPath;
  String? enhancementOperationId;
  String? generationOperationId;
  int? approvedPricePaise;
  String? priceOverrideReason;

  final String createDraftKey;
  final String uploadImageKey;
  String enhanceImageKey;
  final String uploadVoiceKey;
  String generateListingKey;
  String suggestPriceKey;
  final String approveDraftKey;
}

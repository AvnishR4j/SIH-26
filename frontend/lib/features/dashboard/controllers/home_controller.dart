import '../../../core/api/api_client.dart';
import '../../../core/media/media_capture_service.dart';
import '../../catalogue/controllers/catalogue_flow_controller.dart';
import '../../catalogue/models/catalogue_models.dart';

class HomeController {
  HomeController(this._apiClient, {required this.media});

  final ApiClient _apiClient;
  final MediaCaptureService media;

  Future<List<DraftSummary>> loadRecentDrafts() async {
    final page = await _apiClient.listDrafts(limit: 3);
    return page.items;
  }

  CatalogueFlowController newCatalogueFlow() =>
      CatalogueFlowController(_apiClient, media: media);
}

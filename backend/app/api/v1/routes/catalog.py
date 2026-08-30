from typing import Annotated, Literal
from uuid import UUID

from fastapi import (
    APIRouter,
    BackgroundTasks,
    File,
    Form,
    Header,
    Query,
    Response,
    UploadFile,
    status,
)

from app.api.dependencies import (
    CatalogServiceDependency,
    CurrentUser,
    MediaServiceDependency,
    PricingServiceDependency,
    SharingServiceDependency,
    VoiceServiceDependency,
)
from app.core.errors import error_responses
from app.schemas.catalog import (
    Draft,
    DraftCreate,
    DraftImage,
    DraftImagePatch,
    DraftList,
    DraftPatch,
    DraftStatus,
    GenerateListingRequest,
    ImageEnhancementRequest,
    PricingSuggestion,
    PricingSuggestionRequest,
    VoiceNote,
)
from app.schemas.operations import OperationResponse
from app.schemas.sharing import ApprovalRequest, ApprovedCatalog

router = APIRouter(tags=["catalogue drafts"])


@router.post(
    "/drafts",
    response_model=Draft,
    status_code=status.HTTP_201_CREATED,
    responses=error_responses(401, 409, 422, 500),
)
def create_draft(
    body: DraftCreate,
    user: CurrentUser,
    service: CatalogServiceDependency,
    idempotency_key: Annotated[UUID, Header(alias="Idempotency-Key")],
) -> Draft:
    return service.create_draft(user, body, str(idempotency_key))


@router.get(
    "/drafts",
    response_model=DraftList,
    responses=error_responses(401, 422, 500),
)
def list_drafts(
    user: CurrentUser,
    service: CatalogServiceDependency,
    limit: Annotated[int, Query(ge=1, le=50)] = 20,
    cursor: str | None = None,
    status_filter: Annotated[DraftStatus | None, Query(alias="status")] = None,
) -> DraftList:
    return service.list_drafts(user, limit, cursor, status_filter)


@router.get(
    "/drafts/{draft_id}",
    response_model=Draft,
    responses=error_responses(401, 404, 422, 500),
)
def get_draft(
    draft_id: str,
    user: CurrentUser,
    service: CatalogServiceDependency,
) -> Draft:
    return service.get_draft(user, draft_id)


@router.patch(
    "/drafts/{draft_id}",
    response_model=Draft,
    responses=error_responses(400, 401, 404, 409, 422, 500),
)
def update_draft(
    draft_id: str,
    body: DraftPatch,
    user: CurrentUser,
    service: CatalogServiceDependency,
) -> Draft:
    return service.update_draft(user, draft_id, body)


@router.post(
    "/drafts/{draft_id}/images",
    response_model=DraftImage,
    status_code=status.HTTP_201_CREATED,
    responses=error_responses(400, 401, 404, 409, 413, 415, 422, 500, 503),
)
async def upload_image(
    draft_id: str,
    user: CurrentUser,
    service: MediaServiceDependency,
    image: Annotated[UploadFile, File()],
    idempotency_key: Annotated[UUID, Header(alias="Idempotency-Key")],
    is_primary: Annotated[bool, Form()] = True,
) -> DraftImage:
    content = await image.read(service.settings.max_image_bytes + 1)
    await image.close()
    return service.upload_image(
        user,
        draft_id,
        content,
        is_primary,
        str(idempotency_key),
    )


@router.post(
    "/drafts/{draft_id}/images/{image_id}/enhance",
    response_model=OperationResponse,
    status_code=status.HTTP_202_ACCEPTED,
    responses=error_responses(400, 401, 403, 404, 409, 422, 500, 503),
)
def enhance_image(
    draft_id: str,
    image_id: str,
    body: ImageEnhancementRequest,
    user: CurrentUser,
    service: MediaServiceDependency,
    background_tasks: BackgroundTasks,
    response: Response,
    idempotency_key: Annotated[UUID, Header(alias="Idempotency-Key")],
) -> OperationResponse:
    operation, should_schedule = service.start_image_enhancement(
        user,
        draft_id,
        image_id,
        body,
        str(idempotency_key),
    )
    response.headers["Location"] = f"/api/v1/operations/{operation.id}"
    if should_schedule:
        background_tasks.add_task(service.complete_image_enhancement, user.id, operation.id)
    return operation


@router.patch(
    "/drafts/{draft_id}/images/{image_id}",
    response_model=Draft,
    responses=error_responses(400, 401, 404, 409, 422, 500),
)
def update_image(
    draft_id: str,
    image_id: str,
    body: DraftImagePatch,
    user: CurrentUser,
    service: MediaServiceDependency,
) -> Draft:
    return service.update_image(user, draft_id, image_id, body)


@router.post(
    "/drafts/{draft_id}/voice-notes",
    response_model=VoiceNote,
    status_code=status.HTTP_201_CREATED,
    responses=error_responses(400, 401, 404, 409, 413, 415, 422, 500, 503),
)
async def upload_voice_note(
    draft_id: str,
    user: CurrentUser,
    service: VoiceServiceDependency,
    audio: Annotated[UploadFile, File()],
    language: Annotated[Literal["hi", "en"], Form()],
    idempotency_key: Annotated[UUID, Header(alias="Idempotency-Key")],
) -> VoiceNote:
    content = await audio.read(service.settings.max_audio_bytes + 1)
    await audio.close()
    return service.upload_voice_note(
        user,
        draft_id,
        content,
        language,
        str(idempotency_key),
    )


@router.post(
    "/drafts/{draft_id}/generate-listing",
    response_model=OperationResponse,
    status_code=status.HTTP_202_ACCEPTED,
    responses=error_responses(400, 401, 403, 404, 409, 422, 500, 503),
)
def generate_listing(
    draft_id: str,
    body: GenerateListingRequest,
    user: CurrentUser,
    service: VoiceServiceDependency,
    background_tasks: BackgroundTasks,
    response: Response,
    idempotency_key: Annotated[UUID, Header(alias="Idempotency-Key")],
) -> OperationResponse:
    operation, should_schedule = service.start_listing_generation(
        user,
        draft_id,
        body,
        str(idempotency_key),
    )
    response.headers["Location"] = f"/api/v1/operations/{operation.id}"
    if should_schedule:
        background_tasks.add_task(
            service.complete_listing_generation,
            user.id,
            operation.id,
        )
    return operation


@router.post(
    "/drafts/{draft_id}/pricing/suggest",
    response_model=PricingSuggestion,
    responses=error_responses(400, 401, 404, 409, 422, 500),
)
def suggest_price(
    draft_id: str,
    body: PricingSuggestionRequest,
    user: CurrentUser,
    service: PricingServiceDependency,
    idempotency_key: Annotated[UUID, Header(alias="Idempotency-Key")],
) -> PricingSuggestion:
    return service.suggest_price(
        user,
        draft_id,
        body,
        str(idempotency_key),
    )


@router.post(
    "/drafts/{draft_id}/approve",
    response_model=ApprovedCatalog,
    status_code=status.HTTP_201_CREATED,
    responses=error_responses(400, 401, 404, 409, 422, 500),
)
def approve_draft(
    draft_id: str,
    body: ApprovalRequest,
    user: CurrentUser,
    service: SharingServiceDependency,
    idempotency_key: Annotated[UUID, Header(alias="Idempotency-Key")],
) -> ApprovedCatalog:
    return service.approve_draft(user, draft_id, body, str(idempotency_key))

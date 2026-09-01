from __future__ import annotations

import mimetypes
from dataclasses import dataclass
from datetime import UTC, datetime, timedelta
from typing import Any

import httpx

from app.core.config import Settings, get_settings
from app.core.errors import ApiError


@dataclass(frozen=True)
class ShopifyDraftProduct:
    title: str
    description_html: str
    vendor: str
    product_type: str
    tags: list[str]
    price_paise: int
    image_filename: str
    image_content: bytes


@dataclass(frozen=True)
class ShopifyCreatedProduct:
    product_id: str
    handle: str | None


class ShopifyService:
    """Server-side Shopify Admin API client for the team's own demo store."""

    def __init__(
        self,
        settings: Settings,
        transport: httpx.BaseTransport | None = None,
    ) -> None:
        self.settings = settings
        self.client = httpx.Client(
            timeout=settings.shopify_timeout_seconds,
            transport=transport,
        )
        self._access_token: str | None = None
        self._access_token_expires_at: datetime | None = None

    def create_draft_product(self, product: ShopifyDraftProduct) -> ShopifyCreatedProduct:
        image_resource_url = self._stage_image(product.image_filename, product.image_content)
        created = self._graphql(
            """
            mutation CreateKalaSetuProduct($product: ProductCreateInput!, $media: [CreateMediaInput!]) {
              productCreate(product: $product, media: $media) {
                product {
                  id
                  handle
                  variants(first: 1) { nodes { id } }
                }
                userErrors { field message }
              }
            }
            """,
            {
                "product": {
                    "title": product.title,
                    "descriptionHtml": product.description_html,
                    "vendor": product.vendor,
                    "productType": product.product_type,
                    "tags": product.tags,
                    "status": "DRAFT",
                },
                "media": [
                    {
                        "alt": product.title,
                        "mediaContentType": "IMAGE",
                        "originalSource": image_resource_url,
                    }
                ],
            },
            "productCreate",
        )
        shopify_product = created.get("product")
        if not isinstance(shopify_product, dict):
            raise self._unavailable_error()
        product_id = shopify_product.get("id")
        variants = shopify_product.get("variants", {}).get("nodes", [])
        if not isinstance(product_id, str) or not variants or not isinstance(variants[0], dict):
            raise self._unavailable_error()
        variant_id = variants[0].get("id")
        if not isinstance(variant_id, str):
            raise self._unavailable_error()

        self._graphql(
            """
            mutation SetKalaSetuPrice($productId: ID!, $variants: [ProductVariantsBulkInput!]!) {
              productVariantsBulkUpdate(productId: $productId, variants: $variants) {
                userErrors { field message }
              }
            }
            """,
            {
                "productId": product_id,
                "variants": [{"id": variant_id, "price": f"{product.price_paise / 100:.2f}"}],
            },
            "productVariantsBulkUpdate",
        )
        handle = shopify_product.get("handle")
        return ShopifyCreatedProduct(product_id=product_id, handle=handle if isinstance(handle, str) else None)

    def verify_connection(self) -> str:
        response = self._graphql(
            "query ShopifyShopName { shop { name } }",
            {},
            "shop",
        )
        name = response.get("name")
        if not isinstance(name, str):
            raise self._unavailable_error()
        return name

    def _stage_image(self, filename: str, content: bytes) -> str:
        mime_type = mimetypes.guess_type(filename)[0] or "image/jpeg"
        payload = self._graphql(
            """
            mutation StageKalaSetuImage($input: [StagedUploadInput!]!) {
              stagedUploadsCreate(input: $input) {
                stagedTargets {
                  url
                  resourceUrl
                  parameters { name value }
                }
                userErrors { field message }
              }
            }
            """,
            {
                "input": [
                    {
                        "filename": filename,
                        "mimeType": mime_type,
                        "resource": "PRODUCT_IMAGE",
                        "httpMethod": "POST",
                    }
                ]
            },
            "stagedUploadsCreate",
        )
        targets = payload.get("stagedTargets")
        if not isinstance(targets, list) or not targets or not isinstance(targets[0], dict):
            raise self._unavailable_error()
        target = targets[0]
        url = target.get("url")
        resource_url = target.get("resourceUrl")
        parameters = target.get("parameters")
        if (
            not isinstance(url, str)
            or not isinstance(resource_url, str)
            or not isinstance(parameters, list)
        ):
            raise self._unavailable_error()
        fields = {
            parameter["name"]: parameter["value"]
            for parameter in parameters
            if isinstance(parameter, dict)
            and isinstance(parameter.get("name"), str)
            and isinstance(parameter.get("value"), str)
        }
        try:
            response = self.client.post(
                url,
                data=fields,
                files={"file": (filename, content, mime_type)},
            )
            response.raise_for_status()
        except httpx.HTTPError as error:
            raise self._unavailable_error() from error
        return resource_url

    def _graphql(self, query: str, variables: dict[str, Any], operation: str) -> dict[str, Any]:
        token = self._get_access_token()
        try:
            response = self.client.post(
                f"https://{self._store_domain}/admin/api/{self.settings.shopify_api_version}/graphql.json",
                headers={
                    "Content-Type": "application/json",
                    "X-Shopify-Access-Token": token,
                },
                json={"query": query, "variables": variables},
            )
            response.raise_for_status()
            body = response.json()
        except (httpx.HTTPError, ValueError) as error:
            raise self._unavailable_error() from error
        payload = body.get("data", {}).get(operation) if isinstance(body, dict) else None
        if not isinstance(payload, dict):
            raise self._unavailable_error()
        errors = payload.get("userErrors")
        if isinstance(errors, list) and errors:
            raise ApiError(
                422,
                "SHOPIFY_REJECTED",
                "Shopify could not create this product. Review the catalogue details and try again.",
            )
        return payload

    def _get_access_token(self) -> str:
        now = datetime.now(UTC)
        if (
            self._access_token is not None
            and self._access_token_expires_at is not None
            and now < self._access_token_expires_at
        ):
            return self._access_token
        try:
            response = self.client.post(
                f"https://{self._store_domain}/admin/oauth/access_token",
                data={
                    "grant_type": "client_credentials",
                    "client_id": self.settings.shopify_client_id,
                    "client_secret": self.settings.shopify_client_secret.get_secret_value()
                    if self.settings.shopify_client_secret is not None
                    else "",
                },
                headers={"Content-Type": "application/x-www-form-urlencoded"},
            )
            response.raise_for_status()
            body = response.json()
        except (httpx.HTTPError, ValueError) as error:
            raise self._unavailable_error() from error
        token = body.get("access_token") if isinstance(body, dict) else None
        if not isinstance(token, str) or not token:
            raise self._unavailable_error()
        expires_in = body.get("expires_in", 86_399)
        seconds = expires_in if isinstance(expires_in, int) else 86_399
        self._access_token = token
        self._access_token_expires_at = now + timedelta(seconds=max(60, seconds - 60))
        return token

    @property
    def _store_domain(self) -> str:
        if not self.settings.shopify_enabled or self.settings.shopify_store_domain is None:
            raise ApiError(
                503,
                "SHOPIFY_UNAVAILABLE",
                "Shopify publishing is not configured yet.",
            )
        return self.settings.shopify_store_domain

    @staticmethod
    def _unavailable_error() -> ApiError:
        return ApiError(
            503,
            "SHOPIFY_UNAVAILABLE",
            "Shopify could not be reached. Please try again shortly.",
        )


def get_shopify_service() -> ShopifyService:
    return ShopifyService(get_settings())

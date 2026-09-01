from __future__ import annotations

import json

import httpx

from app.core.config import Settings
from app.services.shopify import ShopifyDraftProduct, ShopifyService


def shopify_settings() -> Settings:
    return Settings(
        shopify_enabled=True,
        shopify_store_domain="demo-shop.myshopify.com",
        shopify_client_id="client-id",
        shopify_client_secret="client-secret",
    )


def test_creates_a_draft_product_with_image_and_price() -> None:
    requests: list[httpx.Request] = []

    def handler(request: httpx.Request) -> httpx.Response:
        requests.append(request)
        if request.url.path == "/admin/oauth/access_token":
            return httpx.Response(200, json={"access_token": "token", "expires_in": 86_399})
        if request.url.path == "/admin/api/2026-07/graphql.json":
            body = json.loads(request.content)
            query = body["query"]
            if "stagedUploadsCreate" in query:
                return httpx.Response(
                    200,
                    json={
                        "data": {
                            "stagedUploadsCreate": {
                                "stagedTargets": [
                                    {
                                        "url": "https://uploads.example.test/target",
                                        "resourceUrl": "https://cdn.shopify.test/staged/photo.jpg",
                                        "parameters": [
                                            {"name": "key", "value": "product/photo.jpg"}
                                        ],
                                    }
                                ],
                                "userErrors": [],
                            }
                        }
                    },
                )
            if "productCreate" in query:
                product = body["variables"]["product"]
                assert product["status"] == "DRAFT"
                assert product["title"] == "Cotton Dupatta"
                return httpx.Response(
                    200,
                    json={
                        "data": {
                            "productCreate": {
                                "product": {
                                    "id": "gid://shopify/Product/123",
                                    "handle": "cotton-dupatta",
                                    "variants": {"nodes": [{"id": "gid://shopify/ProductVariant/456"}]},
                                },
                                "userErrors": [],
                            }
                        }
                    },
                )
            if "productVariantsBulkUpdate" in query:
                assert body["variables"]["variants"][0]["price"] == "938.00"
                return httpx.Response(
                    200,
                    json={
                        "data": {"productVariantsBulkUpdate": {"userErrors": []}}
                    },
                )
        if request.url == "https://uploads.example.test/target":
            return httpx.Response(201)
        raise AssertionError(f"Unexpected request: {request.method} {request.url}")

    service = ShopifyService(shopify_settings(), transport=httpx.MockTransport(handler))
    created = service.create_draft_product(
        ShopifyDraftProduct(
            title="Cotton Dupatta",
            description_html="<p>Hand embroidery.</p>",
            vendor="Sita Devi",
            product_type="dupatta",
            tags=["cotton", "handmade"],
            price_paise=93_800,
            image_filename="product.jpg",
            image_content=b"jpeg-content",
        )
    )

    assert created.product_id == "gid://shopify/Product/123"
    assert created.handle == "cotton-dupatta"
    assert [request.url.path for request in requests] == [
        "/admin/oauth/access_token",
        "/admin/api/2026-07/graphql.json",
        "/target",
        "/admin/api/2026-07/graphql.json",
        "/admin/api/2026-07/graphql.json",
    ]


def test_connection_uses_client_credentials_token() -> None:
    def handler(request: httpx.Request) -> httpx.Response:
        if request.url.path == "/admin/oauth/access_token":
            return httpx.Response(200, json={"access_token": "token"})
        return httpx.Response(200, json={"data": {"shop": {"name": "My Store 2"}}})

    service = ShopifyService(shopify_settings(), transport=httpx.MockTransport(handler))

    assert service.verify_connection() == "My Store 2"

# ASUSE 2021-22 calibration stage

ASUSE is a government enterprise survey. It can improve KalaSetu's India-specific
cost, labour, and business-context baselines, but it is not a product-price dataset.
It must not be used to claim a precise sale price for an individual craft item.

## Official source

- Study: `DDI-IND-MOSPI-NSSO-ASUSE2122`
- Portal: `https://microdata.gov.in/NADA/index.php/catalog/221/get-microdata`
- Access: a free portal login is required for the raw microdata.

## What to download after login

1. The raw microdata package for ASUSE 2021-22.
2. `NSS_ASUSE_21_22_Layout_mult_post` (layout workbook).
3. The accompanying readme and questionnaire/technical documents.

Place the untouched package under `backend/data/raw/asuse/`. It is ignored by Git.

## Import gate

Before any model is trained, we will inspect the supplied layout and make a reviewed
mapping for the following concepts only where they actually exist in the data:

- enterprise industry/activity code
- state or district context
- worker count and labour-related fields
- operating and raw-material expenses
- receipts, output, or value-added fields
- survey weight and reference period

## How KalaSetu will use it

ASUSE will produce an India-specific *baseline adjustment* for a price range. The
existing cost-plus calculation remains the floor, the artisan approves every price,
and no Shopify price is changed automatically.

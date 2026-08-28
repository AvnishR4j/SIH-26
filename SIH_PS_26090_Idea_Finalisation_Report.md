# SIH 2026 - PS 26090 Idea-Finalisation Report

**Working solution name:** KalaSetu AI - a voice-first catalogue and market-readiness assistant for marginalized artisans  
**Problem statement:** 26090 - *AI-Driven Market Linkage and Smart Cataloging Mobile Application for Marginalized Artisans*  
**Organisation:** Ministry of Social Justice and Empowerment (MoSJE)  
**Category:** Software  
**Report status:** Idea-finalisation research; no field validation is claimed.

---

## 1. Executive recommendation

Proceed with **KalaSetu AI** as an Android-first assistant for an artisan or SHG, rather than proposing another full e-commerce marketplace.

An artisan takes a product photo and speaks naturally in a regional language. The app improves the photo, asks only the missing questions, generates an editable Hindi and English catalogue card, recommends an **explainable price range**, and creates a market-ready export plus an assisted onboarding checklist for B2B buyers and existing marketplaces.

This focus directly addresses the SIH brief's three named requirements: AI image enhancement, regional-language voice catalogue creation, and a dynamic-pricing assistant. It is stronger than a generic marketplace because it solves the point at which many artisans currently fail: creating a trustworthy, complete listing without digital-commerce skills.

### Recommended submission position

- **Pilot:** one accessible artisan cluster or SHG, 10-20 artisans, one craft category, with Hindi as the initial spoken-input language and English/Hindi buyer-facing listings.
- **Do not claim:** nationwide launch, automatic GeM/Indiahandmade publishing, real-time market prices, or artisan trial results until those facts are obtained.
- **Core promise:** "From voice note and raw photo to an artisan-approved, market-ready catalogue in minutes."
- **Why now:** the SIH statement itself identifies the gap between temporary fair-based exposure and continuous digital-market access. MoSJE-linked finance bodies also support traditional-craft entrepreneurship and market exposure through fairs, giving the problem a clear institutional context.[^nbcfdc]

## 2. Confirmed SIH requirements and compliance strategy

The official statement requires an intuitive, AI-driven cross-platform mobile app with a scalable backend and a minimalist, accessible UX for low-literacy users. It specifically asks for professional photo preparation, voice-led multilingual cataloguing into English and Hindi, and price suggestions based on market trends and raw-material costs.[^ps]

| SIH requirement | KalaSetu AI response | Proof to show in idea PDF/demo |
| --- | --- | --- |
| Professional product photographs | Original-preserving background cleanup, crop/lighting checks, and before/after comparison | One raw product photo, the proposed result, and an artisan approval button |
| Regional-language voice catalogue | Record -> transcript -> confirmation chips -> Hindi/English listing | A 30-second spoken description transformed into editable fields |
| SEO-friendly professional descriptions | Craft-specific controlled template plus AI-written draft, always editable | Generated title, description, materials, dimensions, care and tags |
| Dynamic pricing assistant | Hybrid cost-plus baseline, dated benchmark table, and ML-assisted price band | Suggested low/typical/high range, reasons, confidence, and manual override |
| B2B/government-marketplace linkage | Buyer enquiry share card, catalogue export, and document/onboarding checklist | One shareable buyer card and one marketplace-readiness checklist |
| Low digital literacy | Voice-first, icon-led, one-task-per-screen, read-aloud prompts, saved drafts | Five-screen user journey with no free-form form burden |

### SIH submission and selection facts to act on

The SIH 2026 guidelines say that a team may submit ideas for at most two problem statements; a problem statement closes after 500 idea submissions; and the submission requires an idea title, description, and idea-presentation PDF. The published deadline is **20 September 2026**. The same guidelines list novelty, complexity, clarity/detail in the prescribed format, feasibility, practicability, sustainability, scale of impact, UX, and future progression as evaluation criteria.[^sih-guidelines]

**Action:** Check the live PS counter before committing. The counter is a live condition, not a value to copy into the presentation.

### Judging strategy

| Criterion | What the idea must make obvious |
| --- | --- |
| Novelty | The innovation is the end-to-end, voice-first *catalogue readiness* workflow with human approval and transparent price reasoning, not "AI + marketplace" as a slogan. |
| Complexity | Show the coordinated pipeline: image quality, Indic speech/translation, structured catalogue creation, and hybrid pricing. |
| Feasibility | Limit the pilot to one cluster/language/craft; reuse established language APIs and pretrained image models. |
| Sustainability | Partner-led onboarding, reusable catalogue records, and a pricing feedback loop improve over time without charging a vulnerable artisan for basic access. |
| Impact | Measure time-to-listing, completed catalogues, buyer enquiries, listing approval rate, and price-override reasons. |
| UX | Demonstrate voice, confirmation, visual prompts, offline drafts, and human control. |
| Future progression | Add languages/crafts only after validation; integrate marketplaces only through approved partnerships. |

## 3. Product definition

### Primary users

1. **Artisan:** creates and approves a product catalogue with minimal typing.
2. **SHG/NGO/cluster facilitator:** helps onboard artisans, resolves document or quality issues, and reviews drafts where requested.
3. **Buyer:** receives a clean catalogue card and sends an enquiry; they are not required to install the app.

### Out of scope for the SIH prototype

- Building payments, logistics, tax filing, warehousing, or a new public marketplace.
- Training a proprietary foundation model.
- Publishing to Indiahandmade or GeM without their written approval and seller verification.
- Declaring a product authentic, GI-certified, sustainable, or fairly priced without evidence.

### Proposed user flow

```text
Choose craft/template
  -> Capture product photo + voice note
  -> AI proposes image cleanup and catalogue fields
  -> Artisan confirms/corrects with voice or tap choices
  -> Price assistant shows a range and reasons
  -> Save approved catalogue
  -> Share buyer card / export catalogue / open onboarding checklist
```

### High-priority features

1. Voice-led catalogue creation, including retry and manual correction.
2. Original-preserving photo enhancement with an approval gate.
3. Structured fields: craft, material, technique, dimensions, colour, production time, care, inventory, and origin as supplied by the artisan.
4. Bilingual listing draft and buyer-ready catalogue card.
5. Transparent price range with confidence and an override reason.
6. Offline draft queue and later sync.

### Differentiators worth emphasising

- **Human-in-the-loop:** AI drafts; the artisan owns the final wording, photo, price, and sharing decision.
- **Trust layer:** retain original photos, record source/date of price benchmarks, and show why a price range changed.
- **Partner-ready rather than platform-replacement:** guides the artisan through real marketplace requirements instead of pretending they do not exist.
- **Craft templates:** avoid hallucinated generic listings by asking for category-specific facts.

## 4. Recommended technical architecture

### Stack decision

| Layer | Recommendation | Why it fits this submission |
| --- | --- | --- |
| Artisan app | **Flutter/Dart**, Android-first | One codebase can later serve Android, web and desktop; Android-first keeps the pilot focused.[^flutter] |
| API and AI orchestration | **FastAPI/Python** | Python keeps image/ML integration close to the backend and FastAPI provides typed API development and automatic OpenAPI documentation.[^fastapi] |
| Data | **PostgreSQL** for users, catalogues, consent, price observations and audit events | Relational records keep catalogue and consent data dependable; JSON fields can hold craft-specific attributes. |
| Media | Private S3-compatible object storage | Store the original and derived photo separately, with retention/deletion controls. |
| Speech and translation | **Bhashini** pipeline APIs | Its documented APIs expose ASR and translation model pipelines for Indian languages; start with a supported Hindi pipeline and validate quality on the pilot vocabulary.[^bhashini] |
| Image service | Pretrained salient-object/background-removal model plus OpenCV quality checks | It removes a major photo barrier without a custom training programme; U2-Net is a viable candidate to benchmark, not a guaranteed choice.[^u2net] |
| Catalogue drafting | Template-constrained multimodal/LLM service | Generates wording only from confirmed attributes; never lets the model invent product facts. |
| Price service | Hybrid deterministic + statistical/ML service | Gives a defensible recommendation before a large labelled sales dataset exists. |

### Logical architecture

```text
Flutter mobile app
  |-- encrypted local drafts / queued uploads
  v
FastAPI API
  |-- consent + identity/role service
  |-- media service -> private object storage
  |-- AI orchestration -> Bhashini / image model / catalogue generator
  |-- pricing service -> benchmark table + cost model + ML scorer
  v
PostgreSQL <- catalogue versions, approvals, source dates, audit events
  |
  +--> buyer share card / CSV-PDF export / marketplace-readiness checklist
```

### Non-negotiable implementation rules

- Preserve the original image and label every generated derivative.
- Store each generated catalogue as a draft until an artisan or authorised facilitator approves it.
- Keep a version history for generated description, price range, benchmark source/date, and override reason.
- Never send an artisan's photo or voice recording to a third-party AI provider before recorded consent.
- Degrade gracefully: if speech or AI is unavailable, allow photo capture, saved draft, simple form fields, and later processing.

## 5. AI design that is credible

### A. Image enhancer and studio

**Prototype pipeline:** blur/exposure/orientation check -> subject segmentation -> optional neutral background -> crop to category template -> side-by-side approval.

Do not promise that the app can reconstruct damaged craftsmanship, remove watermarks, or guarantee marketplace acceptance. Assess results with a small consented test set and record failure cases such as reflective objects, fine embroidery edges, shadows and multi-product photos.

### B. Voice catalogue and bilingual listing

Bhashini documents support for ASR and translation pipelines, including Hindi and many other Indic languages; model choice must be tested against the selected craft vocabulary and accent rather than assumed.[^bhashini-models]

**Safe flow:**

1. Capture a short voice note in the pilot language.
2. Display the transcript and read it back where useful.
3. Extract only a controlled schema: product type, material, technique, colour, dimensions, quantity, production time, care, and story.
4. Ask explicit confirmation for uncertain fields.
5. Produce Hindi and English drafts from confirmed fields; allow edit and approve.

Evaluate word error rate on key craft terms, field-completion rate, correction count, and the percentage of listings approved without facilitator rewrite.

### C. Pricing assistant

The statement asks for ML-based pricing informed by current market trends and raw-material costs. The proposal should not make an untestable "AI knows the market price" claim.

**Recommended hybrid model:**

```text
minimum sustainable price = materials + labour-hours x artisan-entered hourly rate + packaging + logistics buffer
market reference band = dated, licensed/partner-provided comparable listings
recommendation = price range + confidence + explanations
ML adjustment = only when enough labelled, permitted historical observations exist
```

For the prototype, use a small, manually verified benchmark table and a simple similarity/regression model to demonstrate the ML component. The model returns a **range**, not a fixed price, and always exposes inputs, source date, confidence, and a "set my own price" option. The actual cost/sales data needed for a robust model must be collected with consent.

## 6. Data strategy

There is no dataset linked in the SIH statement. This is not a blocker: language and image services can use pretrained models, while the proposal should define a lawful, representative pilot dataset instead of relying on indiscriminate scraping.

| Data | Needed for | Source | Permission / handling |
| --- | --- | --- | --- |
| 50-100 product photos with raw and accepted versions | Image-quality evaluation and demo | Consented artisan/SHG pilot; licensed/team-created fallback | Written consent; remove personal identifiers; retain original separately |
| Product attributes and voice notes | Catalogue extraction evaluation | Same pilot | Consent for recording/processing; permit correction/deletion |
| Materials, labour time, packaging and local delivery estimate | Minimum sustainable price | Artisan/facilitator-entered data | Validate by interview; do not infer values from photos |
| Dated comparable price observations | Price-band benchmark | Partner-provided records, manual research where terms allow, or public catalogues with recorded source/date | Do not scrape or republish marketplace content without permission |
| Completed sale / enquiry outcomes | Future ML calibration | Opt-in artisan records | Optional; aggregate where possible; do not expose buyer details |
| Language/model performance data | Indic ASR/translation testing | Consent-based sample phrases and anonymised corrections | Never assume general accuracy from a public benchmark |

### Minimum field-validation protocol

If a cluster is confirmed, recruit 3-5 artisans and one facilitator before submission. Conduct a 20-minute task test per artisan: create one listing using the current method and one using the prototype. Record consent, task time, corrections, completion, comprehension, and qualitative feedback. This is sufficient for a credible **early usability signal**, not a claim of impact.

### No-field-access fallback

Use only team-created or explicitly licensed sample products and label all findings as **prototype simulation**. Include a partner-outreach plan and do not put fabricated adoption, income, or accuracy numbers in the SIH PDF.

## 7. Market-linkage reality and integration approach

Indiahhandmade is a Ministry of Textiles initiative with an existing seller journey. Its seller materials require artisan identity documentation, PAN, GST or enrolment information, and bank details; product approval is administered by the platform.[^indiahandmade-sop][^indiahandmade-faq] GeM seller registration also has identity/business and tax-related prerequisites.[^gem]

Therefore the first release should provide:

- an exportable catalogue card/CSV/PDF containing only fields approved by the artisan;
- a B2B buyer-enquiry link or shareable QR code;
- a marketplace-readiness checklist that explains missing documents without storing them unless required and consented;
- facilitator-assisted registration handoff to Indiahandmade or GeM.

**Do not present an automated upload, order, payment, or GeM API connection** unless a written agreement and current technical documentation are obtained. This restraint increases feasibility and trustworthiness.

## 8. Privacy, safety, and adoption risks

The DPDP Act, 2023 sets a legal framework for lawful processing of digital personal data; MeitY also publishes the DPDP Rules, 2025 and enforcement material. Treat this as a design constraint and obtain current legal advice before deployment, rather than claiming compliance by default.[^dpdp]

| Risk | Mitigation for the SIH proposal |
| --- | --- |
| AI invents material, origin, or craft story | Use controlled fields, confidence flags, and user approval; prohibit unverified claims. |
| Poor speech recognition for accents/craft terms | Pilot one language; allow replay/correction and maintain a consented craft glossary. |
| Incorrect price harms artisan income | Show a range and reasons, never force a price; make override easy; label benchmarks with date/source. |
| Photo model damages detail | Preserve original, show before/after, offer undo, and test fine-detail products. |
| Low connectivity | Save encrypted local drafts and queue uploads; keep a lightweight text-only fallback. |
| Privacy or exploitation | Data minimisation, plain-language consent, deletion path, no public contact sharing, no sale of artisan data. |
| Marketplace claim is rejected | Position as assisted onboarding/export until a formal integration is approved. |
| No pilot partner | Keep all demo evidence labelled simulated and make partner validation the next milestone. |

## 9. Pitch and demo plan

### 90-second demo narrative

1. **Pain (10 s):** an artisan has a raw photo and can describe the product, but cannot create a professional online listing.
2. **Capture (15 s):** take one photo and record a Hindi voice note.
3. **Assist (25 s):** show before/after image option, transcript, and confirmation chips for material, dimensions and craft details.
4. **Trust (20 s):** show the bilingual catalogue and transparent price range with cost/benchmark reasons; artisan changes the price.
5. **Linkage (15 s):** share the buyer card and show Indiahandmade/GeM readiness checklist.
6. **Impact (5 s):** "not a new marketplace - a bridge that lets artisans participate confidently in the markets that already exist."

### Metrics to propose, not fabricate

- Median time from product capture to approved catalogue.
- Catalogue completion and approval rate.
- Number of AI suggestions corrected by the artisan.
- Photo-quality acceptance rate.
- Buyer enquiries and conversion, if subsequently piloted.
- Price-override rate and override reason.
- Satisfaction/comprehension rating from consented usability participants.

### Suggested SIH idea-PDF slide order

1. Title, team, PS 26090 and one-line value proposition.
2. Problem and target user.
3. Why current fairs/marketplaces do not remove the listing-creation barrier.
4. KalaSetu AI user journey.
5. SIH requirement-to-feature matrix.
6. Technical architecture and human-in-the-loop guardrails.
7. Pricing logic and data credibility.
8. Marketplace handoff/partner ecosystem.
9. Pilot, metrics, risks and mitigation.
10. Scalability roadmap and call to action.

## 10. Final decision and next gates

### Go decision

This is a strong SIH idea if the presentation stays disciplined: **one validated workflow, one initial language, one craft cluster, and transparent human control.** It meets all named requirements without pretending to replace established marketplaces or own unavailable market data.

### Must resolve before final PDF

1. Select the pilot craft cluster, state/city, and first spoken language.
2. Confirm whether the team can speak to at least three artisans or one SHG/NGO/facilitator.
3. Obtain consent before using any real photo, voice note, price, or testimonial.
4. Check the live SIH counter and submission format/deadline again.
5. Run a small Hindi/craft-vocabulary test of the chosen Bhashini pipeline.
6. Prepare a benchmark table with source/date and clearly state its limitations.

---

## Sources

[^ps]: [Smart India Hackathon - PS 26090](https://www.sih.gov.in/sih2026PS) (official problem statement page; accessed 25 August 2026).
[^sih-guidelines]: [SIH 2026 Guidelines for Institutes/Universities](https://www.sih.gov.in/letters/2026/SIH%202026%20Guidelines.pdf) (official SIH PDF; accessed 25 August 2026).
[^nbcfdc]: [Entrepreneurial Schemes of NBCFDC](https://socialjustice.gov.in/schemes/13?mid=32549) (Department of Social Justice and Empowerment; accessed 25 August 2026).
[^flutter]: [Flutter - Build apps for any screen](https://flutter.dev/) (official documentation; accessed 25 August 2026).
[^fastapi]: [FastAPI documentation](https://fastapi.tiangolo.com/) (official documentation; accessed 25 August 2026).
[^bhashini]: [Bhashini API pipeline overview](https://bhashini.gitbook.io/bhashini-apis) (accessed 25 August 2026).
[^bhashini-models]: [Bhashini available models](https://dibd-bhashini.gitbook.io/bhashini-apis/available-models-for-usage) (accessed 25 August 2026).
[^u2net]: [U2-Net: Going Deeper with Nested U-Structure for Salient Object Detection](https://arxiv.org/abs/2005.09007) (Qin et al., 2020; accessed 25 August 2026).
[^indiahandmade-sop]: [Indiahandmade Seller Registration SOP](https://www.indiahandmade.com/static/version1774002994/frontend/ESHILP/theme/en_US/images/SOP_Seller-Registration-English.pdf) (Ministry of Textiles/Digital India Corporation; accessed 25 August 2026).
[^indiahandmade-faq]: [Indiahandmade Seller FAQ](https://www.indiahandmade.com/faq) (accessed 25 August 2026).
[^gem]: [GeM Seller Registration Prerequisites](https://assets-bg.gem.gov.in/resources/pdf/seller-registration-pre-requisites-v1.2.pdf) (Government e-Marketplace; accessed 25 August 2026).
[^dpdp]: [Digital Personal Data Protection Act, 2023](https://www.meity.gov.in/writereaddata/files/Digital%20Personal%20Data%20Protection%20Act%202023.pdf) and [MeitY DPDP Act and Policies](https://www.meity.gov.in/documents/act-and-policies) (accessed 25 August 2026).

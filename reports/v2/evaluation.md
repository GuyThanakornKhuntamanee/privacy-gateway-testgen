# v2 Evaluation Report

- Dataset version: `2.0.0`
- Profile: `real-world-enterprise`
- Seed: `7`
- Cases: `72`
- Files: `70`
- Overall: **PASS**

## Quality gates

| Gate | Result | Value | Requirement |
|---|---|---|---|
| schema_validity | PASS | 1.0 | >= 1.0 |
| prompt_span_accuracy | PASS | 1.0 | >= 1.0 |
| file_open_rate | PASS | 1.0 | >= 1.0 |
| entity_location_accuracy | PASS | 1.0 | >= 1.0 |
| extraction_accuracy | PASS | 1.0 | >= 1.0 |
| exact_duplicate_rate | PASS | 0.0 | <= 0.0 |
| near_duplicate_rate | PASS | 0.0 | <= 0.05 |
| document_duplicate_rate | PASS | 0.0 | <= 0.05 |
| file_type_coverage | PASS | ['csv', 'docx', 'jpeg', 'jpg', 'json', 'md', 'pdf', 'pptx', 'txt', 'xlsx'] | >= 8 types |
| archetype_coverage | PASS | 29 | >= 8 |
| persona_coverage | PASS | 16 | >= 6 |
| intent_coverage | PASS | 20 | >= 8 |
| language_coverage | PASS | ['en', 'mixed', 'th'] | >= 2 |
| domain_coverage | PASS | ['infrastructure', 'payment', 'pii', 'secrets'] | >= 3 |
| negative_share | PASS | 0.25 | >= 0.08 |
| multi_domain_share | PASS | 0.1806 | >= 0.08 |
| attachment_share | PASS | 0.7222 | >= 0.35 |
| ocr_case_coverage | PASS | 5 | >= 1 |
| opening_repetition | PASS | 0.0278 | <= 0.35 |
| repeated_phrase_rate | PASS | 0.0972 | <= 0.2 |
| archetype_concentration | PASS | 0.1111 | <= 0.3 |
| synthetic_safety | PASS | 0 | 0 safety issues |
| attachment_verification | PASS | 1.0 | == 1.0 |

## Coverage

- File types: `{'csv': 0.0972, 'docx': 0.2361, 'jpeg': 0.0139, 'jpg': 0.0417, 'json': 0.0556, 'md': 0.0278, 'pdf': 0.125, 'pptx': 0.0556, 'txt': 0.1389, 'xlsx': 0.1389}`
- File counts: `{'csv': 7, 'docx': 18, 'jpeg': 1, 'jpg': 3, 'json': 5, 'md': 2, 'pdf': 10, 'pptx': 4, 'txt': 10, 'xlsx': 10}`
- Archetypes: `{'appointment_list': 0.0139, 'bank_statement': 0.0278, 'customer_complaint': 0.0139, 'customer_export': 0.0556, 'cv': 0.0139, 'employee_list': 0.0833, 'employment_contract': 0.0139, 'expense_report': 0.0139, 'internal_memo': 0.0139, 'invoice': 0.0417, 'lab_result': 0.0278, 'leave_request': 0.0278, 'management_deck': 0.0556, 'meeting_minutes': 0.1111, 'order_export': 0.0139, 'payroll': 0.0278, 'prescription': 0.0139, 'purchase_order': 0.0694, 'quotation': 0.0278, 'risk_report': 0.0278, 'scanned_medical_report': 0.0139, 'screenshot_email': 0.0278, 'screenshot_form': 0.0139, 'screenshot_receipt': 0.0139, 'strategy_report': 0.0278, 'supplier_agreement': 0.0278, 'support_ticket': 0.0833, 'transaction_export': 0.0278, 'xml_export': 0.0417}`
- Domains: `{'infrastructure': 0.1528, 'payment': 0.2778, 'pii': 0.3333, 'secrets': 0.1667}`
- Languages: `{'en': 0.2222, 'mixed': 0.3333, 'th': 0.4444}`
- Personas: `{'accountant': 0.0833, 'analyst': 0.0972, 'compliance': 0.0278, 'developer': 0.0694, 'devops': 0.0694, 'executive_assistant': 0.0556, 'finance': 0.0694, 'healthcare_admin': 0.0139, 'hr': 0.0556, 'intern': 0.0139, 'manager': 0.0556, 'operations': 0.0694, 'sales': 0.0833, 'security_engineer': 0.0833, 'support': 0.0972, 'sysadmin': 0.0556}`
- Intents: `{'analyze': 0.0417, 'answer_questions': 0.0278, 'calculate': 0.0556, 'check_code': 0.0139, 'classify': 0.0278, 'compare': 0.0972, 'convert_format': 0.0139, 'create_chart': 0.0278, 'draft_email': 0.0972, 'explain_error': 0.0833, 'extract_fields': 0.125, 'find_anomalies': 0.0139, 'find_missing': 0.0694, 'inspect_config': 0.0139, 'modify_document': 0.0139, 'prepare_report': 0.0556, 'review_document': 0.0694, 'summarize': 0.1111, 'translate': 0.0139, 'troubleshoot': 0.0278}`
- Difficulties: `{'1': 0.1528, '2': 0.1528, '3': 0.2639, '4': 0.2778, '5': 0.1528}`
- Attachment counts: `{'0': 20, '1': 38, '2': 10, '3': 4}`
- Entity density: `{'0': 6, '1-3': 38, '4-6': 12, '7+': 16}`
- Extraction methods: `{'direct_text': 12, 'ocr': 5, 'office_parser': 29, 'pdf_text': 9, 'structured_parser': 11}`
- Negative ratio: `0.25`
- Ambiguous ratio: `0.1389`
- Multi-domain share: `0.1806`
- OCR cases: `5`

## Verification

- File open rate: `1.0`
- Extraction accuracy: `1.0` (failures `0`)
- Entity location accuracy: `1.0`
- Verification status: `{'verified': 67, 'verified_partial': 5}`
- Validation issue cases: `0`

## Realism diagnostics

- Top prompt openings: `[{'opening': 'take a look', 'count': 2}, {'opening': 'this one is', 'count': 2}, {'opening': 'เอาสองอันนี้ ทำ summary.', 'count': 1}, {'opening': 'อันนี้มัน สรุปเป็น bullet.', 'count': 1}, {'opening': 'please use this', 'count': 1}, {'opening': 'สองไฟล์นี้ draft an', 'count': 1}, {'opening': 'งงกับ support_ticket.docx นี้', 'count': 1}, {'opening': 'อันนี้ support_ticket.json ล่าสุด', 'count': 1}, {'opening': 'help me รีวิวให้ทีว่ามีอะไรต้องแก้', 'count': 1}, {'opening': 'อันนี้ของลูกค้า when you', 'count': 1}]`
- Top opening share: `0.0278`
- Repeated 4-grams: `[{'phrase': 'boss wants it by', 'count': 7}, {'phrase': 'the customer tried twice', 'count': 7}, {'phrase': 'the service health dashboard', 'count': 7}, {'phrase': 'review the gateway log.', 'count': 7}, {'phrase': 'an error. the customer', 'count': 7}, {'phrase': 'the checkout page shows', 'count': 7}, {'phrase': 'tried twice and is', 'count': 7}, {'phrase': '``` support ticket #48219', 'count': 7}, {'phrase': 'and review the gateway', 'count': 7}, {'phrase': 'step: confirm the service', 'count': 7}]`
- Repeated phrase share: `0.0972`
- Archetype concentration: `0.1111`
- Prompt length: `{'min': 20, 'max': 1251, 'mean': 237.99, 'stdev': 287.27}`
- Document duplicate rate: `0.0`

## Duplicate analysis

- Exact duplicate rate: `0.0`
- Near duplicate rate: `0.0`
- Cross-split near pairs: `0`

## Synthetic safety

- Passed: `True`
- Issues: `0`

## Known limitations

- The PDF renderer uses built-in WinAnsi fonts; PDF attachment content is Latin/English. Thai PDF content is routed to DOCX/XLSX/TXT instead.
- Image text uses a bitmap font and Latin script only. Thai OCR images are out of scope for v2.0.
- Image and scanned-PDF annotations are verified at render-layout level. No third-party OCR engine is run in the test suite, so OCR accuracy is not claimed.
- PPTX speaker notes and native PowerPoint tables are not emitted; slide body text and later-slide placement are supported.
- YAML/TOML/INI/ENV verification uses the generator's strict subset parser, not PyYAML or tomllib.
- Archives, password-protected containers, audio, video, executables and recursive archive extraction are out of scope.
- Template-family isolation is enforced for file bundles; a very small dataset consequently has fewer families in validation/test.
- The default policy file is an illustrative test configuration, not legal advice or a compliance certification.
- All entities are synthetic. Coincidental similarity to a real person, host or company is possible but not intended.

## Recommended improvements

- Run the generated files through the actual gateway extractors, then compare their extraction output with ground_truth/entities.jsonl.
- Add organisation-specific archetypes and policy files before using the dataset operationally.
- Use a larger seed/count when a profile must show every file family in every split.
- Review any case marked verified_partial before treating OCR-oriented labels as authoritative.

# v2 Evaluation Report

- Dataset version: `2.1.0`
- Profile: `real-world-enterprise`
- Seed: `7`
- Cases: `72`
- Files: `62`
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
| file_type_coverage | PASS | ['csv', 'docx', 'jpg', 'json', 'md', 'pdf', 'png', 'txt', 'xlsx'] | >= 8 types |
| archetype_coverage | PASS | 32 | >= 8 |
| persona_coverage | PASS | 16 | >= 6 |
| intent_coverage | PASS | 19 | >= 8 |
| language_coverage | PASS | ['en', 'mixed', 'th'] | >= 2 |
| attachment_language_coverage | PASS | {'en': 29, 'mixed': 21, 'th': 12} | >= 2 languages |
| language_matrix_coverage | PASS | {'en->en': 4, 'en->mixed': 4, 'en->prompt_only': 9, 'en->th': 6, 'mixed->en': 11, 'mixed->mixed': 1, 'mixed->prompt_only': 4, 'mixed->th': 2, 'th->en': 14, 'th->mixed': 16, 'th->prompt_only': 13, 'th->th': 4} | >= 4 prompt/attachment pairs |
| mixed_language_script | PASS | 1.0 | all mixed attachments contain Thai and English script |
| structure_reference_resolution | PASS | 1.0 | all structure references resolve |
| structure_reference_share | PASS | 0.2222 | >= 0.05 |
| multi_file_share | PASS | 0.1667 | >= 0.05 |
| cross_file_link_coverage | PASS | 6 | >= 1 cases |
| same_archetype_bundle_coverage | PASS | 3 | >= 1 cases |
| cross_file_consistency | PASS | 1.0 | >= 1.0 |
| domain_coverage | PASS | ['infrastructure', 'payment', 'pii', 'secrets'] | >= 3 |
| negative_share | PASS | 0.1528 | >= 0.08 |
| multi_domain_share | PASS | 0.1389 | >= 0.08 |
| attachment_share | PASS | 0.6389 | >= 0.35 |
| ocr_case_coverage | PASS | 8 | >= 1 |
| opening_repetition | PASS | 0.0139 | <= 0.35 |
| repeated_phrase_rate | PASS | 0.1389 | <= 0.2 |
| archetype_concentration | PASS | 0.1111 | <= 0.3 |
| synthetic_safety | PASS | 0 | 0 safety issues |
| attachment_verification | PASS | 1.0 | == 1.0 |

## Coverage

- File types: `{'csv': 0.1111, 'docx': 0.125, 'jpg': 0.0556, 'json': 0.0972, 'md': 0.0278, 'pdf': 0.1111, 'png': 0.0694, 'txt': 0.1111, 'xlsx': 0.0556}`
- File counts: `{'csv': 8, 'docx': 12, 'jpg': 4, 'json': 8, 'md': 2, 'pdf': 10, 'png': 5, 'txt': 9, 'xlsx': 4}`
- Archetypes: `{'appointment_list': 0.0139, 'bank_statement': 0.0139, 'candidate_evaluation': 0.0139, 'customer_complaint': 0.0139, 'customer_contract': 0.0139, 'customer_export': 0.0139, 'cv': 0.0278, 'employee_list': 0.0972, 'employment_contract': 0.0139, 'expense_report': 0.0139, 'internal_memo': 0.0278, 'invoice': 0.0139, 'lab_result': 0.0139, 'management_deck': 0.0139, 'medical_report': 0.0139, 'meeting_minutes': 0.0417, 'nda': 0.0139, 'patient_list': 0.0139, 'payroll': 0.0417, 'quotation': 0.0139, 'risk_report': 0.0139, 'sales_pipeline': 0.0278, 'screenshot_chat': 0.0278, 'screenshot_email': 0.0278, 'screenshot_form': 0.0139, 'screenshot_id': 0.0139, 'screenshot_receipt': 0.0278, 'supplier_agreement': 0.0139, 'support_ticket': 0.1111, 'transaction_export': 0.0556, 'vendor_list': 0.0139, 'xml_export': 0.0278}`
- Domains: `{'infrastructure': 0.1667, 'payment': 0.2639, 'pii': 0.3889, 'secrets': 0.1806}`
- Languages (prompt): `{'en': 0.2639, 'mixed': 0.1944, 'th': 0.5417}`
- Languages (attachment): `{'en': 0.4677, 'mixed': 0.3387, 'th': 0.1935}`
- Prompt/attachment language matrix: `{'en->en': 4, 'en->mixed': 4, 'en->prompt_only': 9, 'en->th': 6, 'mixed->en': 11, 'mixed->mixed': 1, 'mixed->prompt_only': 4, 'mixed->th': 2, 'th->en': 14, 'th->mixed': 16, 'th->prompt_only': 13, 'th->th': 4}`
- Mixed attachments verified: `21/21`
- Routed (Latin-only renderer): `19`
- Personas: `{'accountant': 0.0556, 'analyst': 0.0556, 'compliance': 0.0417, 'developer': 0.0556, 'devops': 0.0417, 'executive_assistant': 0.0417, 'finance': 0.1528, 'healthcare_admin': 0.0417, 'hr': 0.0556, 'intern': 0.0278, 'manager': 0.0972, 'operations': 0.0833, 'sales': 0.0139, 'security_engineer': 0.0417, 'support': 0.125, 'sysadmin': 0.0694}`
- Intents: `{'answer_questions': 0.0556, 'calculate': 0.0694, 'check_code': 0.0139, 'classify': 0.0278, 'compare': 0.0417, 'convert_format': 0.0139, 'draft_email': 0.0556, 'explain_error': 0.0139, 'extract_fields': 0.0556, 'find_anomalies': 0.125, 'find_missing': 0.0278, 'inspect_config': 0.0694, 'modify_document': 0.0139, 'prepare_report': 0.0556, 'review_document': 0.0972, 'rewrite': 0.0417, 'summarize': 0.1667, 'translate': 0.0278, 'troubleshoot': 0.0278}`
- Difficulties: `{'1': 0.0556, '2': 0.2083, '3': 0.2778, '4': 0.2917, '5': 0.1667}`
- Attachment counts: `{'0': 26, '1': 34, '2': 8, '3': 4}`
- Entity density: `{'0': 2, '1-3': 34, '4-6': 9, '7+': 27}`
- Extraction methods: `{'direct_text': 10, 'ocr': 8, 'office_parser': 12, 'pdf_text': 8, 'structured_parser': 15}`
- Negative ratio: `0.1528`
- Ambiguous ratio: `0.125`
- Multi-domain share: `0.1389`
- Multi-file share: `0.1667`
- Same-archetype bundle cases: `3`
- Structure-reference cases: `16` (`17/17` resolved)
- Cross-file link cases: `6` (`20` links)
- Consistency checks: `156/156` passed
- OCR cases: `8`

## Verification

- File open rate: `1.0`
- Extraction accuracy: `1.0` (failures `0`)
- Entity location accuracy: `1.0`
- Verification status: `{'verified': 64, 'verified_partial': 8}`
- Validation issue cases: `0`

## Realism diagnostics

- Top prompt openings: `[{'opening': 'พี่ครับ อันนี้มันยังไม่ได้เลย. ทีมภายนอกขอมาด่วน.', 'count': 1}, {'opening': 'พี่คะ อันนี้ อยู่ในแนบ', 'count': 1}, {'opening': 'อันนี้มันยังไม่ได้เย. ดู บรรทัดที่', 'count': 1}, {'opening': 'หา anomaly ให้หน่อย', 'count': 1}, {'opening': 'ยังไม่ได้เลย ช่วยดูที🙏. คือเมื่อคืน', 'count': 1}, {'opening': 'cv.pdf, bank_statement.pdf ช่วยสรุปให้หน่อย', 'count': 1}, {'opening': 'รบกวนช่วย อันนี้ อันนี้', 'count': 1}, {'opening': 'this one what', 'count': 1}, {'opening': 'เอาสองอันนี้ เช็กค่าพวกนี้ให้ที. ทีมภายนอกขอมาด่วน.', 'count': 1}, {'opening': 'ร่างอีเมลให้หน่อย ให้หน่อย. ไม่แน่ใจว่าใช่ไฟล์เดียวกันไหม', 'count': 1}]`
- Top opening share: `0.0139`
- Repeated 4-grams: `[{'phrase': '- confirm the migration', 'count': 10}, {'phrase': 'location: internal video call', 'count': 10}, {'phrase': '- remove the old', 'count': 10}, {'phrase': 'the old deployment credential.', 'count': 10}, {'phrase': 'confirm the migration window.', 'count': 10}, {'phrase': 'remove the old deployment', 'count': 10}, {'phrase': '| location: internal video', 'count': 10}, {'phrase': 'old deployment credential. ```', 'count': 10}, {'phrase': 'the migration window. -', 'count': 10}, {'phrase': 'boss wants it by', 'count': 9}]`
- Repeated phrase share: `0.1389`
- Archetype concentration: `0.1111`
- Prompt length: `{'min': 29, 'max': 1603, 'mean': 323.57, 'stdev': 369.42}`
- Document duplicate rate: `0.0`

## Duplicate analysis

- Exact duplicate rate: `0.0`
- Near duplicate rate: `0.0`
- Cross-split near pairs: `0`

## Synthetic safety

- Passed: `True`
- Issues: `0`

## Known limitations

- PDF content is English/Latin only because the standard-library PDF writer uses built-in WinAnsi fonts. Thai PDF content is routed to DOCX/XLSX/TXT and the routing is recorded on the attachment.
- Image text uses a bitmap Latin font. Thai image OCR is not supported; Thai image scenarios are routed to English with an explicit language_routing field.
- Image and scanned-PDF annotations are verified at render-layout level. No third-party OCR engine is run in the test suite, so OCR accuracy is not claimed.
- PPTX speaker notes and native PowerPoint tables are not emitted; slide body text and later-slide placement are supported.
- YAML/TOML/INI/ENV verification uses the generator's strict subset parser, not PyYAML or tomllib.
- Archives, password-protected containers, audio, video, executables and recursive archive extraction are out of scope.
- Template-family isolation is enforced for file bundles; a very small dataset consequently has fewer families in validation/test.
- The default policy file is an illustrative test configuration, not legal advice or a compliance certification.
- All entities are synthetic. Coincidental similarity to a real person, host or company is possible but not intended.
- Cross-file consistency is validated on the generated scenario plan and annotations, not by executing a downstream gateway.

## Recommended improvements

- Run the generated files through the actual gateway extractors, then compare their extraction output with ground_truth/entities.jsonl.
- Add organisation-specific archetypes and policy files before using the dataset operationally.
- Use a larger seed/count when a profile must show every file family in every split.
- Review any case marked verified_partial before treating OCR-oriented labels as authoritative.

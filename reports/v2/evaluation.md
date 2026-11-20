# v2 Evaluation Report

- Dataset version: `2.1.1`
- Profile: `benchmark-balanced`
- Seed: `21`
- Cases: `72`
- Files: `82`
- Overall: **PASS**
- Benchmark ready: **YES** (68 safe cases, 4 excluded)

## Benchmark readiness

- Reasons: `[]`
- Checks: `{'no_failed_ground_truth_verification': True, 'no_known_high_correctness_issue': True, 'linked_financial_data_consistent': True, 'timeline_valid': True, 'entity_fragments_valid': True, 'language_metadata_valid': True, 'required_safety_checks': True, 'no_unresolved_schema_errors': True, 'deterministic_dataset_output': True, 'deterministic_report_output': True}`

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
| file_type_coverage | PASS | ['conf', 'csv', 'docx', 'env', 'go', 'ini', 'jpeg', 'jpg', 'js', 'json', 'log', 'md', 'pdf', 'png', 'pptx', 'tf', 'toml', 'txt', 'xlsx', 'xml', 'yaml'] | >= 8 types |
| archetype_coverage | PASS | 39 | >= 8 |
| persona_coverage | PASS | 15 | >= 6 |
| intent_coverage | PASS | 17 | >= 8 |
| language_coverage | PASS | ['en', 'mixed', 'th'] | >= 2 |
| attachment_language_coverage | PASS | {'en': 48, 'mixed': 4, 'th': 30} | >= 2 languages |
| language_matrix_coverage | PASS | {'en->en': 12, 'en->mixed': 1, 'en->prompt_only': 6, 'en->th': 9, 'mixed->en': 20, 'mixed->prompt_only': 6, 'mixed->th': 4, 'th->en': 16, 'th->mixed': 3, 'th->prompt_only': 3, 'th->th': 17} | >= 4 prompt/attachment pairs |
| mixed_language_script | PASS | 1.0 | all mixed attachments contain Thai and English script |
| structure_reference_resolution | PASS | 1.0 | all structure references resolve |
| structure_reference_share | PASS | 0.3889 | >= 0.05 |
| multi_file_share | PASS | 0.2361 | >= 0.05 |
| cross_file_link_coverage | PASS | 17 | >= 1 cases |
| same_archetype_bundle_coverage | PASS | 8 | >= 1 cases |
| cross_file_consistency | PASS | 1.0 | >= 1.0 |
| consistency_evaluated | PASS | {'not_applicable': 264, 'passed': 78} | 0 failed, 0 not_evaluated (not_applicable allowed) |
| language_share_check | PASS | 0 | 0 attachments below their declared script-share thresholds |
| localization_residual_labels | PASS | 0 | 0 untranslated static labels in Thai documents |
| prompt_form_concentration | PASS | 0.2667 | <= 0.45 |
| domain_coverage | PASS | ['infrastructure', 'payment', 'pii', 'secrets'] | >= 3 |
| negative_share | PASS | 0.1944 | >= 0.08 |
| multi_domain_share | PASS | 0.2222 | >= 0.08 |
| attachment_share | PASS | 0.7917 | >= 0.35 |
| ocr_case_coverage | PASS | 4 | >= 1 |
| opening_repetition | PASS | 0.0278 | <= 0.35 |
| repeated_phrase_rate | PASS | 0.0833 | <= 0.2 |
| archetype_concentration | PASS | 0.0833 | <= 0.3 |
| synthetic_safety | PASS | 0 | 0 safety issues |
| attachment_verification | PASS | 1.0 | == 1.0 |

## Coverage

- File types: `{'conf': 0.0139, 'csv': 0.0972, 'docx': 0.0833, 'env': 0.0278, 'go': 0.0278, 'ini': 0.0139, 'jpeg': 0.0278, 'jpg': 0.0139, 'js': 0.0139, 'json': 0.0833, 'log': 0.0833, 'md': 0.0694, 'pdf': 0.125, 'png': 0.0278, 'pptx': 0.0417, 'tf': 0.0139, 'toml': 0.0139, 'txt': 0.1389, 'xlsx': 0.0417, 'xml': 0.0417, 'yaml': 0.0139}`
- File counts: `{'conf': 1, 'csv': 8, 'docx': 7, 'env': 2, 'go': 2, 'ini': 1, 'jpeg': 2, 'jpg': 1, 'js': 1, 'json': 6, 'log': 6, 'md': 5, 'pdf': 11, 'png': 2, 'pptx': 3, 'tf': 1, 'toml': 1, 'txt': 14, 'xlsx': 4, 'xml': 3, 'yaml': 1}`
- Archetypes: `{'access_records': 0.0417, 'api_gateway_log': 0.0139, 'api_payload': 0.0278, 'app_log': 0.0417, 'application_config': 0.0278, 'application_environment_config': 0.0278, 'auth_log': 0.0417, 'bank_statement': 0.0139, 'customer_export': 0.0139, 'cv': 0.0139, 'database_config': 0.0417, 'docker_compose': 0.0278, 'employee_list': 0.0833, 'employment_contract': 0.0417, 'incident_report': 0.0417, 'incident_review_deck': 0.0278, 'internal_memo': 0.0139, 'invoice': 0.0278, 'kubernetes_manifest': 0.0139, 'management_deck': 0.0139, 'meeting_minutes': 0.0833, 'nda': 0.0278, 'order_export': 0.0139, 'patient_list': 0.0139, 'payroll': 0.0139, 'purchase_order': 0.0139, 'sales_report_deck': 0.0139, 'screenshot_chat': 0.0278, 'screenshot_dashboard': 0.0139, 'screenshot_receipt': 0.0139, 'server_inventory': 0.0139, 'source_code': 0.0139, 'source_code_go': 0.0139, 'source_code_js': 0.0139, 'support_ticket': 0.0278, 'terraform_config': 0.0139, 'transaction_export': 0.0556, 'vendor_list': 0.0139, 'xml_export': 0.0278}`
- Domains: `{'infrastructure': 0.25, 'payment': 0.1944, 'pii': 0.2917, 'secrets': 0.2917}`
- Languages (prompt): `{'en': 0.2917, 'mixed': 0.3333, 'th': 0.375}`
- Languages (attachment): `{'en': 0.5854, 'mixed': 0.0488, 'th': 0.3659}`
- Prompt/attachment language matrix: `{'en->en': 12, 'en->mixed': 1, 'en->prompt_only': 6, 'en->th': 9, 'mixed->en': 20, 'mixed->prompt_only': 6, 'mixed->th': 4, 'th->en': 16, 'th->mixed': 3, 'th->prompt_only': 3, 'th->th': 17}`
- Mixed attachments verified: `4/4`
- Routed (Latin-only renderer): `42`
- Personas: `{'accountant': 0.0417, 'analyst': 0.0833, 'compliance': 0.0278, 'developer': 0.0556, 'devops': 0.0417, 'executive_assistant': 0.0972, 'finance': 0.0417, 'healthcare_admin': 0.0694, 'hr': 0.1944, 'intern': 0.0139, 'manager': 0.0972, 'sales': 0.0972, 'security_engineer': 0.0417, 'support': 0.0833, 'sysadmin': 0.0139}`
- Intents: `{'answer_questions': 0.0417, 'calculate': 0.0833, 'classify': 0.0278, 'compare': 0.0972, 'draft_email': 0.0139, 'explain_error': 0.0139, 'extract_fields': 0.0833, 'find_anomalies': 0.0417, 'find_missing': 0.125, 'inspect_config': 0.0694, 'modify_document': 0.0556, 'prepare_report': 0.0694, 'review_document': 0.0694, 'rewrite': 0.0139, 'summarize': 0.1111, 'translate': 0.0139, 'troubleshoot': 0.0694}`
- Difficulties: `{'1': 0.0139, '2': 0.1528, '3': 0.3333, '4': 0.2917, '5': 0.2083}`
- Attachment counts: `{'0': 15, '1': 40, '2': 9, '3': 8}`
- Entity density: `{'1-3': 16, '4-6': 10, '7+': 46}`
- Extraction methods: `{'direct_text': 29, 'ocr': 4, 'office_parser': 11, 'pdf_text': 9, 'structured_parser': 16}`
- Negative ratio: `0.1944`
- Ambiguous ratio: `0.0694`
- Multi-domain share: `0.2222`
- Multi-file share: `0.2361`
- Same-archetype bundle cases: `8`
- Structure-reference cases: `28` (`30/30` resolved)
- Cross-file link cases: `17` (`77` links)
- Consistency checks: `78/342` passed; status `{'not_applicable': 264, 'passed': 78}`
- Prompt forms: `{'copied_chat': 1, 'copied_ticket': 1, 'log_fragment': 1, 'pasted_email': 2, 'pasted_file': 1, 'pasted_table': 2, 'raw_notes': 1, 'report_excerpt': 2, 'short_no_paste': 4, 'with_attachment': 57}` (top share `0.2667`)
- Mean Thai script share by prompt language: `{'th': 0.8075, 'en': 0.0049, 'mixed': 0.54}`
- Language mismatches: `0`
- Language coverage by file type: `{'conf': {'files': 1, 'declared': {'en': 1}, 'mismatches': 0}, 'csv': {'files': 8, 'declared': {'en': 4, 'th': 4}, 'mismatches': 0}, 'docx': {'files': 7, 'declared': {'en': 3, 'th': 4}, 'mismatches': 0}, 'env': {'files': 2, 'declared': {'en': 2}, 'mismatches': 0}, 'go': {'files': 2, 'declared': {'en': 1, 'th': 1}, 'mismatches': 0}, 'ini': {'files': 1, 'declared': {'th': 1}, 'mismatches': 0}, 'jpeg': {'files': 2, 'declared': {'en': 2}, 'mismatches': 0}, 'jpg': {'files': 1, 'declared': {'en': 1}, 'mismatches': 0}, 'js': {'files': 1, 'declared': {'en': 1}, 'mismatches': 0}, 'json': {'files': 6, 'declared': {'en': 4, 'mixed': 1, 'th': 1}, 'mismatches': 0}, 'log': {'files': 6, 'declared': {'en': 6}, 'mismatches': 0}, 'md': {'files': 5, 'declared': {'mixed': 2, 'th': 3}, 'mismatches': 0}, 'pdf': {'files': 11, 'declared': {'en': 11}, 'mismatches': 0}, 'png': {'files': 2, 'declared': {'en': 2}, 'mismatches': 0}, 'pptx': {'files': 3, 'declared': {'en': 2, 'mixed': 1}, 'mismatches': 0}, 'tf': {'files': 1, 'declared': {'en': 1}, 'mismatches': 0}, 'toml': {'files': 1, 'declared': {'th': 1}, 'mismatches': 0}, 'txt': {'files': 14, 'declared': {'en': 2, 'th': 12}, 'mismatches': 0}, 'xlsx': {'files': 4, 'declared': {'en': 3, 'th': 1}, 'mismatches': 0}, 'xml': {'files': 3, 'declared': {'en': 1, 'th': 2}, 'mismatches': 0}, 'yaml': {'files': 1, 'declared': {'en': 1}, 'mismatches': 0}}`
- Residual English labels in Thai documents: `0`
- OCR cases: `4`

## Verification

- File open rate: `1.0`
- Extraction accuracy: `1.0` (failures `0`)
- Entity location accuracy: `1.0`
- Verification status: `{'verified': 68, 'verified_partial': 4}`
- Validation issue cases: `0`

## Realism diagnostics

- Top prompt openings: `[{'opening': 'customer says attached', 'count': 2}, {'opening': 'ส่งไปที่ contact@example.com -', 'count': 2}, {'opening': 'api_payload.xml attached. compare', 'count': 1}, {'opening': 'attached access_records.log, ceck', 'count': 1}, {'opening': 'could you help', 'count': 1}, {'opening': 'could you take', 'count': 1}, {'opening': 'employee_list.docx attached. reconcile', 'count': 1}, {'opening': 'employment_contract_v1.pdf, employment_contract_v2.pdf attached,', 'count': 1}, {'opening': 'heelp ดู ไฟล์นี้', 'count': 1}, {'opening': 'hello, attached support_ticket.json,', 'count': 1}]`
- Top opening share: `0.0278`
- Repeated 4-grams: `[{'phrase': 'boss wants it by', 'count': 6}, {'phrase': 'wants it by 5.', 'count': 4}, {'phrase': '| อีเมล | เบอร์โทร', 'count': 4}, {'phrase': 'อีเมล | เบอร์โทร |', 'count': 4}, {'phrase': '- confirm the migration', 'count': 3}, {'phrase': '- remove the old', 'count': 3}, {'phrase': 'confirm the migration window.', 'count': 3}, {'phrase': 'figure out why it', 'count': 3}, {'phrase': 'location: internal video call', 'count': 3}, {'phrase': "not sure it's the", 'count': 3}]`
- Repeated phrase share: `0.0833`
- Archetype concentration: `0.0833`
- Prompt length: `{'min': 34, 'max': 1033, 'mean': 184.35, 'stdev': 233.42}`
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

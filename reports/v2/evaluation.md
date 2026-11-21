# v2 Evaluation Report

- Dataset version: `2.2.0`
- Profile: `benchmark-balanced`
- Seed: `21`
- Cases: `72`
- Files: `76`
- Overall: **PASS**
- Benchmark ready: **YES** (72 safe cases: 63 text, 9 OCR-required; 0 excluded)

## Benchmark readiness

- Reasons: `[]`
- Checks: `{'no_failed_ground_truth_verification': True, 'no_known_high_correctness_issue': True, 'linked_financial_data_consistent': True, 'timeline_valid': True, 'entity_fragments_valid': True, 'no_replacement_glyphs': True, 'thai_file_rendering_verified': True, 'language_metadata_valid': True, 'required_safety_checks': True, 'no_unresolved_schema_errors': True, 'deterministic_dataset_output': True, 'deterministic_report_output': True}`

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
| file_type_coverage | PASS | ['csv', 'docx', 'env', 'ini', 'jpg', 'json', 'log', 'md', 'pdf', 'png', 'pptx', 'toml', 'txt', 'xlsx', 'xml', 'yaml', 'yml'] | >= 8 types |
| archetype_coverage | PASS | 36 | >= 8 |
| persona_coverage | PASS | 15 | >= 6 |
| intent_coverage | PASS | 21 | >= 8 |
| language_coverage | PASS | ['en', 'mixed', 'th'] | >= 2 |
| attachment_language_coverage | PASS | {'en': 34, 'mixed': 7, 'th': 35} | >= 2 languages |
| language_matrix_coverage | PASS | {'en->en': 14, 'en->mixed': 6, 'en->prompt_only': 5, 'en->th': 20, 'mixed->en': 8, 'mixed->prompt_only': 3, 'mixed->th': 6, 'th->en': 12, 'th->mixed': 1, 'th->prompt_only': 6, 'th->th': 9} | >= 4 prompt/attachment pairs |
| mixed_language_script | PASS | 1.0 | all mixed attachments contain Thai and English script |
| structure_reference_resolution | PASS | 1.0 | all structure references resolve |
| structure_reference_share | PASS | 0.3611 | >= 0.05 |
| multi_file_share | PASS | 0.2083 | >= 0.05 |
| cross_file_link_coverage | PASS | 14 | >= 1 cases |
| same_archetype_bundle_coverage | PASS | 9 | >= 1 cases |
| cross_file_consistency | PASS | 1.0 | >= 1.0 |
| consistency_evaluated | PASS | {'not_applicable': 278, 'passed': 73} | 0 failed, 0 not_evaluated (not_applicable allowed) |
| language_share_check | PASS | 0 | 0 attachments below their declared script-share thresholds |
| localization_residual_labels | PASS | 0 | 0 untranslated static labels in Thai documents |
| prompt_form_concentration | PASS | 0.2857 | <= 0.45 |
| thai_file_render_rate | PASS | 9/9 | every Thai or mixed PDF/image attachment is render-verified |
| raster_text_shaping | PASS | 11/11 | every raster attachment records HarfBuzz shaping |
| native_pdf_text_extraction | PASS | 8/8 | every native PDF extracts its canonical text back |
| no_replacement_glyphs | PASS | 0 | 0 replacement characters in canonical render text |
| domain_coverage | PASS | ['infrastructure', 'payment', 'pii', 'secrets'] | >= 3 |
| negative_share | PASS | 0.2222 | >= 0.08 |
| multi_domain_share | PASS | 0.1806 | >= 0.08 |
| attachment_share | PASS | 0.8056 | >= 0.35 |
| ocr_case_coverage | PASS | 9 | >= 1 |
| opening_repetition | PASS | 0.0417 | <= 0.35 |
| repeated_phrase_rate | PASS | 0.0694 | <= 0.2 |
| archetype_concentration | PASS | 0.0833 | <= 0.3 |
| synthetic_safety | PASS | 0 | 0 safety issues |
| attachment_verification | PASS | 1.0 | == 1.0 |

## Coverage

- File types: `{'csv': 0.0417, 'docx': 0.1667, 'env': 0.0139, 'ini': 0.0139, 'jpg': 0.0139, 'json': 0.0694, 'log': 0.1111, 'md': 0.0417, 'pdf': 0.1389, 'png': 0.0833, 'pptx': 0.0417, 'toml': 0.0139, 'txt': 0.1111, 'xlsx': 0.0556, 'xml': 0.0139, 'yaml': 0.0139, 'yml': 0.0278}`
- File counts: `{'csv': 3, 'docx': 12, 'env': 1, 'ini': 1, 'jpg': 1, 'json': 5, 'log': 8, 'md': 3, 'pdf': 11, 'png': 7, 'pptx': 3, 'toml': 1, 'txt': 11, 'xlsx': 5, 'xml': 1, 'yaml': 1, 'yml': 2}`
- Archetypes: `{'access_records': 0.0278, 'api_gateway_log': 0.0417, 'app_log': 0.0278, 'application_config': 0.0278, 'architecture_deck': 0.0139, 'auth_log': 0.0417, 'bank_statement': 0.0139, 'cv': 0.0417, 'database_config': 0.0278, 'deployment_log': 0.0278, 'docker_compose': 0.0278, 'employee_list': 0.0694, 'employment_contract': 0.0278, 'incident_report': 0.0139, 'incident_review_deck': 0.0139, 'internal_memo': 0.0139, 'invoice': 0.0417, 'meeting_minutes': 0.0833, 'patient_list': 0.0139, 'payroll': 0.0139, 'purchase_order': 0.0139, 'risk_report': 0.0139, 'sales_pipeline': 0.0139, 'sales_report_deck': 0.0139, 'scanned_invoice': 0.0139, 'scanned_medical_report': 0.0139, 'screenshot_config': 0.0139, 'screenshot_dashboard': 0.0139, 'screenshot_receipt': 0.0139, 'source_code': 0.0139, 'sql_export': 0.0139, 'strategy_report': 0.0556, 'supplier_agreement': 0.0139, 'support_ticket': 0.0417, 'transaction_export': 0.0139, 'xml_export': 0.0417}`
- Domains: `{'infrastructure': 0.1806, 'payment': 0.2222, 'pii': 0.2639, 'secrets': 0.2917}`
- Languages (prompt): `{'en': 0.4722, 'mixed': 0.2083, 'th': 0.3194}`
- Languages (attachment): `{'en': 0.4474, 'mixed': 0.0921, 'th': 0.4605}`
- Prompt/attachment language matrix: `{'en->en': 14, 'en->mixed': 6, 'en->prompt_only': 5, 'en->th': 20, 'mixed->en': 8, 'mixed->prompt_only': 3, 'mixed->th': 6, 'th->en': 12, 'th->mixed': 1, 'th->prompt_only': 6, 'th->th': 9}`
- Mixed attachments verified: `7/7`
- Routed attachments (English-only renderer): `30`
- Evaluation requirement: `{'direct_text_extraction': 66, 'ocr_required': 10}`
- Native PDF text extraction verified: `8/8`
- Raster attachments verified (layout): `11/11`
- Raster text shaping (HarfBuzz): `11/11`
- Hybrid PDF attachments: `1`
- Thai / mixed PDF and image attachments verified: `9/9`
- Replacement glyphs in canonical render text: `0`
- Personas: `{'accountant': 0.0278, 'analyst': 0.125, 'compliance': 0.0694, 'developer': 0.0417, 'devops': 0.0278, 'executive_assistant': 0.1111, 'finance': 0.1111, 'healthcare_admin': 0.0833, 'hr': 0.0972, 'intern': 0.0694, 'manager': 0.0694, 'operations': 0.0278, 'sales': 0.0694, 'support': 0.0417, 'sysadmin': 0.0278}`
- Intents: `{'analyze': 0.0278, 'answer_questions': 0.0833, 'calculate': 0.0417, 'check_code': 0.0139, 'classify': 0.0139, 'compare': 0.1111, 'create_chart': 0.0417, 'draft_email': 0.0556, 'explain_error': 0.0278, 'extract_fields': 0.0556, 'find_anomalies': 0.0278, 'find_missing': 0.0417, 'generate_docs': 0.0278, 'inspect_config': 0.0278, 'modify_document': 0.0417, 'prepare_report': 0.1389, 'review_document': 0.0417, 'rewrite': 0.0278, 'summarize': 0.0556, 'translate': 0.0556, 'troubleshoot': 0.0417}`
- Difficulties: `{'1': 0.0972, '2': 0.1111, '3': 0.2778, '4': 0.25, '5': 0.2639}`
- Attachment counts: `{'0': 14, '1': 43, '2': 12, '3': 3}`
- Entity density: `{'0': 2, '1-3': 28, '4-6': 9, '7+': 33}`
- Extraction methods: `{'direct_text': 21, 'ocr': 9, 'office_parser': 18, 'pdf_text': 8, 'structured_parser': 11}`
- Negative ratio: `0.2222`
- Ambiguous ratio: `0.0278`
- Multi-domain share: `0.1806`
- Multi-file share: `0.2083`
- Same-archetype bundle cases: `9`
- Structure-reference cases: `26` (`27/27` resolved)
- Cross-file link cases: `14` (`62` links)
- Consistency checks: `73/351` passed; status `{'not_applicable': 278, 'passed': 73}`
- Prompt forms: `{'copied_chat': 1, 'copied_ticket': 3, 'log_fragment': 4, 'report_excerpt': 2, 'short_no_paste': 4, 'with_attachment': 58}` (top share `0.2857`)
- Mean Thai script share by prompt language: `{'th': 0.7538, 'en': 0.0139, 'mixed': 0.5527}`
- Language mismatches: `0`
- Language coverage by file type: `{'csv': {'files': 3, 'declared': {'en': 1, 'th': 2}, 'mismatches': 0}, 'docx': {'files': 12, 'declared': {'en': 4, 'mixed': 3, 'th': 5}, 'mismatches': 0}, 'env': {'files': 1, 'declared': {'en': 1}, 'mismatches': 0}, 'ini': {'files': 1, 'declared': {'th': 1}, 'mismatches': 0}, 'jpg': {'files': 1, 'declared': {'th': 1}, 'mismatches': 0}, 'json': {'files': 5, 'declared': {'en': 2, 'mixed': 1, 'th': 2}, 'mismatches': 0}, 'log': {'files': 8, 'declared': {'en': 8}, 'mismatches': 0}, 'md': {'files': 3, 'declared': {'en': 1, 'mixed': 1, 'th': 1}, 'mismatches': 0}, 'pdf': {'files': 11, 'declared': {'en': 5, 'mixed': 2, 'th': 4}, 'mismatches': 0}, 'png': {'files': 7, 'declared': {'en': 5, 'th': 2}, 'mismatches': 0}, 'pptx': {'files': 3, 'declared': {'en': 2, 'th': 1}, 'mismatches': 0}, 'toml': {'files': 1, 'declared': {'th': 1}, 'mismatches': 0}, 'txt': {'files': 11, 'declared': {'en': 4, 'th': 7}, 'mismatches': 0}, 'xlsx': {'files': 5, 'declared': {'th': 5}, 'mismatches': 0}, 'xml': {'files': 1, 'declared': {'th': 1}, 'mismatches': 0}, 'yaml': {'files': 1, 'declared': {'th': 1}, 'mismatches': 0}, 'yml': {'files': 2, 'declared': {'en': 1, 'th': 1}, 'mismatches': 0}}`
- Residual English labels in Thai documents: `0`
- OCR cases: `9`

## Verification

- File open rate: `1.0`
- Extraction accuracy: `1.0` (failures `0`)
- Entity location accuracy: `1.0`
- Verification status: `{'verified': 62, 'verified_partial': 10}`
- Validation issue cases: `0`

## Realism diagnostics

- Top prompt openings: `[{'opening': 'send it to', 'count': 3}, {'opening': 'can you check', 'count': 2}, {'opening': 'could you attached', 'count': 2}, {'opening': "not sure what's", 'count': 2}, {'opening': 'these two attached,', 'count': 2}, {'opening': 'use this one', 'count': 2}, {'opening': 'อันนี้มัน error ตรงไหนอะ', 'count': 2}, {'opening': 'access_records.log สรุป ให้ที.', 'count': 1}, {'opening': 'attahced the attached', 'count': 1}, {'opening': 'can you prepare', 'count': 1}]`
- Top opening share: `0.0417`
- Repeated 4-grams: `[{'phrase': '- confirm the migration', 'count': 5}, {'phrase': '- remove the old', 'count': 5}, {'phrase': 'confirm the migration window.', 'count': 5}, {'phrase': 'location: internal video call', 'count': 5}, {'phrase': 'remove the old deployment', 'count': 5}, {'phrase': 'the migration window. -', 'count': 5}, {'phrase': 'the old deployment credential.', 'count': 5}, {'phrase': '| location: internal video', 'count': 5}, {'phrase': 'boss wants it by', 'count': 4}, {'phrase': 'need it before the', 'count': 4}]`
- Repeated phrase share: `0.0694`
- Archetype concentration: `0.0833`
- Prompt length: `{'min': 24, 'max': 1564, 'mean': 185.75, 'stdev': 251.09}`
- Document duplicate rate: `0.0`

## Duplicate analysis

- Exact duplicate rate: `0.0`
- Near duplicate rate: `0.0`
- Cross-split near pairs: `0`

## Synthetic safety

- Passed: `True`
- Issues: `0`

## Known limitations

- Native PDF text is embedded TrueType (Sarabun regular/bold) with a ToUnicode map, so Thai and mixed Thai-English text extracts back exactly. Byte identity is guaranteed only for the pinned ReportLab/Pillow versions on one platform; across versions only extracted text, spans and boxes are claimed identical.
- Raster assets (PNG/JPEG and scanned or hybrid PDF regions) are verified at render-layout level. No OCR engine is run, so OCR accuracy is not claimed, and the canonical pre-render text stays the ground truth.
- Raster cases are not excluded from the benchmark for needing OCR. They are listed in `benchmark_safe_ocr_cases.jsonl`, separate from `benchmark_safe_text_cases.jsonl`, because the gateway under test performs the OCR.
- Raster degradation (noise, blur, small rotation, brightness gradient) changes pixels, so the reported bounding boxes are transformed to the final image and may cover slightly more area than the ink.
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

# v2 Evaluation Report

- Dataset version: `2.2.0`
- Profile: `benchmark-balanced`
- Seed: `21`
- Cases: `72`
- Files: `75`
- Overall: **PASS**
- Benchmark ready: **YES** (72 safe cases: 66 text, 6 OCR-required; 0 excluded)

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
| file_type_coverage | PASS | ['csv', 'docx', 'env', 'java', 'jpeg', 'json', 'log', 'md', 'pdf', 'png', 'pptx', 'sql', 'tf', 'toml', 'ts', 'txt', 'xlsx', 'yaml', 'yml'] | >= 8 types |
| archetype_coverage | PASS | 37 | >= 8 |
| persona_coverage | PASS | 16 | >= 6 |
| intent_coverage | PASS | 19 | >= 8 |
| language_coverage | PASS | ['en', 'mixed', 'th'] | >= 2 |
| attachment_language_coverage | PASS | {'en': 40, 'mixed': 7, 'th': 28} | >= 2 languages |
| language_matrix_coverage | PASS | {'en->en': 9, 'en->mixed': 1, 'en->prompt_only': 5, 'en->th': 9, 'mixed->en': 15, 'mixed->mixed': 2, 'mixed->prompt_only': 6, 'mixed->th': 7, 'th->en': 16, 'th->mixed': 4, 'th->prompt_only': 3, 'th->th': 12} | >= 4 prompt/attachment pairs |
| mixed_language_script | PASS | 1.0 | all mixed attachments contain Thai and English script |
| structure_reference_resolution | PASS | 1.0 | all structure references resolve |
| structure_reference_share | PASS | 0.3194 | >= 0.05 |
| multi_file_share | PASS | 0.1806 | >= 0.05 |
| cross_file_link_coverage | PASS | 13 | >= 1 cases |
| same_archetype_bundle_coverage | PASS | 5 | >= 1 cases |
| cross_file_consistency | PASS | 1.0 | >= 1.0 |
| consistency_evaluated | PASS | {'not_applicable': 282, 'passed': 66} | 0 failed, 0 not_evaluated (not_applicable allowed) |
| language_share_check | PASS | 0 | 0 attachments below their declared script-share thresholds |
| localization_residual_labels | PASS | 0 | 0 untranslated static labels in Thai documents |
| prompt_form_concentration | PASS | 0.2857 | <= 0.45 |
| thai_file_render_rate | PASS | 6/6 | every Thai or mixed PDF/image attachment is render-verified |
| raster_text_shaping | PASS | 9/9 | every raster attachment records HarfBuzz shaping |
| native_pdf_text_extraction | PASS | 6/6 | every native PDF extracts its canonical text back |
| no_replacement_glyphs | PASS | 0 | 0 replacement characters in canonical render text |
| domain_coverage | PASS | ['infrastructure', 'payment', 'pii', 'secrets'] | >= 3 |
| negative_share | PASS | 0.2917 | >= 0.08 |
| multi_domain_share | PASS | 0.1944 | >= 0.08 |
| attachment_share | PASS | 0.8056 | >= 0.35 |
| ocr_case_coverage | PASS | 6 | >= 1 |
| opening_repetition | PASS | 0.0278 | <= 0.35 |
| repeated_phrase_rate | PASS | 0.0694 | <= 0.2 |
| archetype_concentration | PASS | 0.0972 | <= 0.3 |
| synthetic_safety | PASS | 0 | 0 safety issues |
| attachment_verification | PASS | 1.0 | == 1.0 |

## Coverage

- File types: `{'csv': 0.0694, 'docx': 0.0972, 'env': 0.0139, 'java': 0.0139, 'jpeg': 0.0139, 'json': 0.0417, 'log': 0.1389, 'md': 0.0278, 'pdf': 0.0833, 'png': 0.0694, 'pptx': 0.0694, 'sql': 0.0139, 'tf': 0.0139, 'toml': 0.0278, 'ts': 0.0139, 'txt': 0.125, 'xlsx': 0.0833, 'yaml': 0.0417, 'yml': 0.0139}`
- File counts: `{'csv': 5, 'docx': 7, 'env': 1, 'java': 1, 'jpeg': 1, 'json': 3, 'log': 10, 'md': 2, 'pdf': 8, 'png': 6, 'pptx': 5, 'sql': 1, 'tf': 1, 'toml': 2, 'ts': 1, 'txt': 11, 'xlsx': 6, 'yaml': 3, 'yml': 1}`
- Archetypes: `{'access_records': 0.0417, 'api_gateway_log': 0.0417, 'api_payload': 0.0139, 'app_log': 0.0972, 'application_config': 0.0417, 'application_environment_config': 0.0139, 'architecture_deck': 0.0139, 'architecture_notes': 0.0278, 'auth_log': 0.0417, 'customer_complaint': 0.0139, 'customer_contract': 0.0139, 'database_config': 0.0139, 'deployment_log': 0.0417, 'docker_compose': 0.0417, 'employee_list': 0.0278, 'employment_contract': 0.0417, 'expense_report': 0.0139, 'incident_report': 0.0139, 'incident_review_deck': 0.0278, 'internal_memo': 0.0139, 'invoice': 0.0139, 'management_deck': 0.0278, 'meeting_minutes': 0.0556, 'patient_list': 0.0139, 'payroll': 0.0417, 'purchase_order': 0.0139, 'sales_pipeline': 0.0139, 'screenshot_config': 0.0139, 'screenshot_email': 0.0139, 'service_account_config': 0.0139, 'source_code': 0.0139, 'source_code_java': 0.0139, 'source_code_js': 0.0278, 'sql_export': 0.0139, 'support_ticket': 0.0556, 'terraform_config': 0.0139, 'xml_export': 0.0139}`
- Domains: `{'infrastructure': 0.25, 'payment': 0.1111, 'pii': 0.2639, 'secrets': 0.2778}`
- Languages (prompt): `{'en': 0.2361, 'mixed': 0.3472, 'th': 0.4167}`
- Languages (attachment): `{'en': 0.5333, 'mixed': 0.0933, 'th': 0.3733}`
- Prompt/attachment language matrix: `{'en->en': 9, 'en->mixed': 1, 'en->prompt_only': 5, 'en->th': 9, 'mixed->en': 15, 'mixed->mixed': 2, 'mixed->prompt_only': 6, 'mixed->th': 7, 'th->en': 16, 'th->mixed': 4, 'th->prompt_only': 3, 'th->th': 12}`
- Mixed attachments verified: `7/7`
- Routed attachments (English-only renderer): `40`
- Evaluation requirement: `{'direct_text_extraction': 68, 'ocr_required': 7}`
- Native PDF text extraction verified: `6/6`
- Raster attachments verified (layout): `9/9`
- Raster text shaping (HarfBuzz): `9/9`
- Hybrid PDF attachments: `2`
- Thai / mixed PDF and image attachments verified: `6/6`
- Replacement glyphs in canonical render text: `0`
- Personas: `{'accountant': 0.0139, 'analyst': 0.0556, 'compliance': 0.0417, 'developer': 0.0833, 'devops': 0.0278, 'executive_assistant': 0.0556, 'finance': 0.0833, 'healthcare_admin': 0.0278, 'hr': 0.0833, 'intern': 0.0694, 'manager': 0.0694, 'operations': 0.125, 'sales': 0.0833, 'security_engineer': 0.0278, 'support': 0.0694, 'sysadmin': 0.0833}`
- Intents: `{'analyze': 0.0417, 'answer_questions': 0.0139, 'calculate': 0.0556, 'check_code': 0.0556, 'classify': 0.0278, 'compare': 0.0833, 'create_chart': 0.0139, 'explain_error': 0.0417, 'extract_fields': 0.0694, 'find_anomalies': 0.125, 'find_missing': 0.0139, 'inspect_config': 0.0833, 'modify_document': 0.0278, 'prepare_report': 0.0694, 'review_document': 0.0139, 'rewrite': 0.0139, 'summarize': 0.125, 'translate': 0.0417, 'troubleshoot': 0.0833}`
- Difficulties: `{'1': 0.1667, '2': 0.1528, '3': 0.3056, '4': 0.2361, '5': 0.1389}`
- Attachment counts: `{'0': 14, '1': 45, '2': 9, '3': 4}`
- Entity density: `{'0': 2, '1-3': 28, '4-6': 13, '7+': 29}`
- Extraction methods: `{'direct_text': 26, 'ocr': 6, 'office_parser': 16, 'pdf_text': 6, 'structured_parser': 12}`
- Negative ratio: `0.2917`
- Ambiguous ratio: `0.0278`
- Multi-domain share: `0.1944`
- Multi-file share: `0.1806`
- Same-archetype bundle cases: `5`
- Structure-reference cases: `23` (`24/24` resolved)
- Cross-file link cases: `13` (`61` links)
- Consistency checks: `66/348` passed; status `{'not_applicable': 282, 'passed': 66}`
- Prompt forms: `{'copied_chat': 3, 'copied_ticket': 1, 'log_fragment': 1, 'pasted_email': 4, 'pasted_file': 1, 'pasted_table': 1, 'short_no_paste': 3, 'with_attachment': 58}` (top share `0.2857`)
- Mean Thai script share by prompt language: `{'th': 0.7892, 'en': 0.0392, 'mixed': 0.4688}`
- Language mismatches: `0`
- Language coverage by file type: `{'csv': {'files': 5, 'declared': {'en': 1, 'th': 4}, 'mismatches': 0}, 'docx': {'files': 7, 'declared': {'en': 3, 'th': 4}, 'mismatches': 0}, 'env': {'files': 1, 'declared': {'th': 1}, 'mismatches': 0}, 'java': {'files': 1, 'declared': {'en': 1}, 'mismatches': 0}, 'jpeg': {'files': 1, 'declared': {'en': 1}, 'mismatches': 0}, 'json': {'files': 3, 'declared': {'en': 1, 'th': 2}, 'mismatches': 0}, 'log': {'files': 10, 'declared': {'en': 10}, 'mismatches': 0}, 'md': {'files': 2, 'declared': {'en': 1, 'th': 1}, 'mismatches': 0}, 'pdf': {'files': 8, 'declared': {'en': 3, 'mixed': 2, 'th': 3}, 'mismatches': 0}, 'png': {'files': 6, 'declared': {'en': 5, 'th': 1}, 'mismatches': 0}, 'pptx': {'files': 5, 'declared': {'en': 2, 'mixed': 3}, 'mismatches': 0}, 'sql': {'files': 1, 'declared': {'en': 1}, 'mismatches': 0}, 'tf': {'files': 1, 'declared': {'en': 1}, 'mismatches': 0}, 'toml': {'files': 2, 'declared': {'th': 2}, 'mismatches': 0}, 'ts': {'files': 1, 'declared': {'mixed': 1}, 'mismatches': 0}, 'txt': {'files': 11, 'declared': {'en': 5, 'mixed': 1, 'th': 5}, 'mismatches': 0}, 'xlsx': {'files': 6, 'declared': {'en': 4, 'th': 2}, 'mismatches': 0}, 'yaml': {'files': 3, 'declared': {'en': 1, 'th': 2}, 'mismatches': 0}, 'yml': {'files': 1, 'declared': {'th': 1}, 'mismatches': 0}}`
- Residual English labels in Thai documents: `0`
- OCR cases: `6`

## Verification

- File open rate: `1.0`
- Extraction accuracy: `1.0` (failures `0`)
- Entity location accuracy: `1.0`
- Verification status: `{'verified': 64, 'verified_partial': 8}`
- Validation issue cases: `0`

## Realism diagnostics

- Top prompt openings: `[{'opening': 'could you help', 'count': 2}, {'opening': 'could you take', 'count': 2}, {'opening': 'ส่งไปที่ contact@example.com -', 'count': 2}, {'opening': 'app_log.log ช่วยสรุปหน่อย. หัวหน้าขอภายในวันนี้;', 'count': 1}, {'opening': 'application_config.env เตรียมสรุปสำหรับหัวหน้า please', 'count': 1}, {'opening': 'compare these two', 'count': 1}, {'opening': 'comprae sales_pipeline_v1.csv, sales_pipeline.xlsx', 'count': 1}, {'opening': 'could you check', 'count': 1}, {'opening': 'employment_contract_v1.pdf, employment_contract_v2.pdf attached,', 'count': 1}, {'opening': 'help me out,', 'count': 1}]`
- Top opening share: `0.0278`
- Repeated 4-grams: `[{'phrase': 'after the latest release', 'count': 5}, {'phrase': 'an error. the customer', 'count': 5}, {'phrase': 'and is waiting for', 'count': 5}, {'phrase': 'and review the gateway', 'count': 5}, {'phrase': 'checkout page shows an', 'count': 5}, {'phrase': 'confirm the service health', 'count': 5}, {'phrase': 'customer tried twice and', 'count': 5}, {'phrase': 'dashboard and review the', 'count': 5}, {'phrase': 'error. the customer tried', 'count': 5}, {'phrase': 'health dashboard and review', 'count': 5}]`
- Repeated phrase share: `0.0694`
- Archetype concentration: `0.0972`
- Prompt length: `{'min': 24, 'max': 851, 'mean': 154.62, 'stdev': 181.03}`
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

# v2 Evaluation Report

- Dataset version: `2.2.0`
- Profile: `thai-rendering`
- Seed: `21`
- Cases: `16`
- Files: `21`
- Overall: **PASS**
- Benchmark ready: **YES** (16 safe cases: 3 text, 13 OCR-required; 0 excluded)

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
| file_type_coverage | PASS | ['docx', 'jpg', 'md', 'pdf', 'png'] | >= 4 types |
| archetype_coverage | PASS | 9 | >= 4 |
| persona_coverage | PASS | 11 | >= 3 |
| intent_coverage | PASS | 10 | >= 4 |
| language_coverage | PASS | ['en', 'mixed', 'th'] | >= 2 |
| attachment_language_coverage | PASS | {'en': 1, 'mixed': 1, 'th': 19} | >= 2 languages |
| language_matrix_coverage | PASS | {'en->en': 1, 'en->th': 1, 'mixed->th': 5, 'th->mixed': 1, 'th->th': 13} | >= 4 prompt/attachment pairs |
| mixed_language_script | PASS | 1.0 | all mixed attachments contain Thai and English script |
| structure_reference_resolution | PASS | 1.0 | all structure references resolve |
| structure_reference_share | PASS | 0.3125 | >= 0.05 |
| multi_file_share | PASS | 0.3125 | >= 0.05 |
| cross_file_link_coverage | PASS | 5 | >= 1 cases |
| same_archetype_bundle_coverage | PASS | 3 | >= 1 cases |
| cross_file_consistency | PASS | 1.0 | >= 1.0 |
| consistency_evaluated | PASS | {'not_applicable': 70, 'passed': 16} | 0 failed, 0 not_evaluated (not_applicable allowed) |
| language_share_check | PASS | 0 | 0 attachments below their declared script-share thresholds |
| localization_residual_labels | PASS | 0 | 0 untranslated static labels in Thai documents |
| prompt_form_concentration | PASS | 0.0 | <= 0.45 |
| thai_file_render_rate | PASS | 18/18 | every Thai or mixed PDF/image attachment is render-verified |
| raster_text_shaping | PASS | 15/15 | every raster attachment records HarfBuzz shaping |
| native_pdf_text_extraction | PASS | 4/4 | every native PDF extracts its canonical text back |
| no_replacement_glyphs | PASS | 0 | 0 replacement characters in canonical render text |
| domain_coverage | PASS | ['infrastructure', 'payment', 'pii', 'secrets'] | >= 2 |
| negative_share | PASS | 0.125 | >= 0.08 |
| multi_domain_share | PASS | 0.1875 | >= 0.08 |
| attachment_share | PASS | 1.0 | >= 0.35 |
| ocr_case_coverage | PASS | 13 | >= 1 |
| opening_repetition | PASS | 0.0625 | <= 0.35 |
| repeated_phrase_rate | PASS | 0.125 | <= 0.2 |
| archetype_concentration | PASS | 0.25 | <= 0.3 |
| synthetic_safety | PASS | 0 | 0 safety issues |
| attachment_verification | PASS | 1.0 | == 1.0 |

## Coverage

- File types: `{'docx': 0.0625, 'jpg': 0.4375, 'md': 0.0625, 'pdf': 0.375, 'png': 0.3125}`
- File counts: `{'docx': 1, 'jpg': 7, 'md': 1, 'pdf': 7, 'png': 5}`
- Archetypes: `{'architecture_notes': 0.125, 'meeting_minutes': 0.125, 'scanned_invoice': 0.125, 'screenshot_chat': 0.25, 'screenshot_code': 0.0625, 'screenshot_config': 0.125, 'screenshot_dashboard': 0.1875, 'screenshot_receipt': 0.0625, 'support_ticket': 0.0625}`
- Domains: `{'infrastructure': 0.125, 'payment': 0.25, 'pii': 0.375, 'secrets': 0.3125}`
- Languages (prompt): `{'en': 0.125, 'mixed': 0.25, 'th': 0.625}`
- Languages (attachment): `{'en': 0.0476, 'mixed': 0.0476, 'th': 0.9048}`
- Prompt/attachment language matrix: `{'en->en': 1, 'en->th': 1, 'mixed->th': 5, 'th->mixed': 1, 'th->th': 13}`
- Mixed attachments verified: `1/1`
- Routed attachments (English-only renderer): `8`
- Evaluation requirement: `{'direct_text_extraction': 7, 'ocr_required': 14}`
- Native PDF text extraction verified: `4/4`
- Raster attachments verified (layout): `15/15`
- Raster text shaping (HarfBuzz): `15/15`
- Hybrid PDF attachments: `1`
- Thai / mixed PDF and image attachments verified: `18/18`
- Replacement glyphs in canonical render text: `0`
- Personas: `{'analyst': 0.125, 'devops': 0.0625, 'executive_assistant': 0.0625, 'finance': 0.0625, 'healthcare_admin': 0.125, 'hr': 0.0625, 'intern': 0.0625, 'manager': 0.125, 'operations': 0.0625, 'sales': 0.125, 'support': 0.125}`
- Intents: `{'analyze': 0.125, 'calculate': 0.0625, 'classify': 0.0625, 'draft_email': 0.0625, 'extract_fields': 0.0625, 'find_anomalies': 0.125, 'prepare_report': 0.125, 'review_document': 0.0625, 'summarize': 0.25, 'troubleshoot': 0.0625}`
- Difficulties: `{'1': 0.0625, '2': 0.125, '3': 0.4375, '4': 0.25, '5': 0.125}`
- Attachment counts: `{'1': 11, '2': 5}`
- Entity density: `{'1-3': 4, '4-6': 3, '7+': 9}`
- Extraction methods: `{'direct_text': 1, 'ocr': 13, 'office_parser': 1, 'pdf_text': 4}`
- Negative ratio: `0.125`
- Ambiguous ratio: `0.125`
- Multi-domain share: `0.1875`
- Multi-file share: `0.3125`
- Same-archetype bundle cases: `3`
- Structure-reference cases: `5` (`5/5` resolved)
- Cross-file link cases: `5` (`26` links)
- Consistency checks: `16/86` passed; status `{'not_applicable': 70, 'passed': 16}`
- Prompt forms: `{'with_attachment': 16}` (top share `0.0`)
- Mean Thai script share by prompt language: `{'th': 0.7832, 'en': 0.0, 'mixed': 0.5112}`
- Language mismatches: `0`
- Language coverage by file type: `{'docx': {'files': 1, 'declared': {'mixed': 1}, 'mismatches': 0}, 'jpg': {'files': 7, 'declared': {'en': 1, 'th': 6}, 'mismatches': 0}, 'md': {'files': 1, 'declared': {'th': 1}, 'mismatches': 0}, 'pdf': {'files': 7, 'declared': {'th': 7}, 'mismatches': 0}, 'png': {'files': 5, 'declared': {'th': 5}, 'mismatches': 0}}`
- Residual English labels in Thai documents: `0`
- OCR cases: `13`

## Verification

- File open rate: `1.0`
- Extraction accuracy: `1.0` (failures `0`)
- Entity location accuracy: `1.0`
- Verification status: `{'verified': 2, 'verified_partial': 14}`
- Validation issue cases: `0`

## Realism diagnostics

- Top prompt openings: `[{'opening': 'architecture_notes.pdf วิเคราะห์ให้ที. ไม่แน่ใจว่าใช่ไฟล์เดียวกันไหม.', 'count': 1}, {'opening': 'could you attached', 'count': 1}, {'opening': 'screenshot_chat.jpg เขียนตอบลูกค้า please', 'count': 1}, {'opening': 'this is broken,', 'count': 1}, {'opening': 'ขอให้ช่วย ดูให้ทีนะ เมื่อคืนแก้แล้ว.', 'count': 1}, {'opening': 'ขอให้ช่วย ยังไม่ได้เลย ช่วยดูที.', 'count': 1}, {'opening': 'ช่วยดู screenshot_config.png สรุปให้ที', 'count': 1}, {'opening': 'ฝากคำนวณยอดรวม อันนี้ หน่อย.', 'count': 1}, {'opening': 'พี่ครับ scanned_invoice.pdf fnd', 'count': 1}, {'opening': 'พี่ครับ ไฟล์นี้ วิเคราะห์ให้ที.', 'count': 1}]`
- Top opening share: `0.0625`
- Repeated 4-grams: `[{'phrase': 'ดู หน้า 1 หน่อย', 'count': 2}]`
- Repeated phrase share: `0.125`
- Archetype concentration: `0.25`
- Prompt length: `{'min': 29, 'max': 366, 'mean': 90.44, 'stdev': 75.83}`
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

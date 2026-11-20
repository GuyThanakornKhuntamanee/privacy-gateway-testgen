# Handoff — v2.1.1 Correctness & Benchmark Readiness

- วันที่: 2026-11-20
- Branch: `fix/v2.1.1-benchmark-readiness`
- Code commit: `b3b7856` — *fix: harden v2.1 ground truth, language and benchmark gates*
- `main` ไม่ถูกแก้ไข; งานต่อจาก `feat/v2.1-language-consistency` (`052652f`)
- Package `0.3.1`; dataset version v2 = `2.1.1`

## 1. สรุปผู้บริหาร

รอบนี้ไม่ได้เพิ่ม format ใหม่ แต่ปิดช่องโหว่ที่ทำให้ dataset “ดูผ่าน” ทั้งที่
ground truth ผิด: log ที่ตรวจแล้วบอกว่าเรียงเวลาแต่จริง ๆ ไม่เรียง, ใบแจ้งหนี้กับ
transaction export ที่อ้างธุรกรรมเดียวกันแต่ยอดต่างกัน, image annotation ที่ติดป้าย
ทั้งชื่อให้กับ fragment, language label ที่ดูแค่ว่ามีอักษรไทยหรือไม่, prompt ที่
ต่อวลีซ้ำ, report ที่เปลี่ยนตาม `PYTHONHASHSEED`, และ consistency check ที่นับ
`all([])` เป็นผ่าน

ผลลัพธ์: 166 tests ผ่าน, v1/v2 gates ผ่านทั้งหมด, `benchmark_ready: true`
พร้อม safe subset 68/72 cases (4 cases เป็น layout-only OCR ที่ถูกกันออกอย่าง
เปิดเผย) และ report byte-identical ข้าม hash seed

## 2. Pre-fix verification table

ตรวจจาก branch เดิม + generated sample ก่อนแก้:

| # | Issue | Status | หลักฐานก่อนแก้ |
|---|---|---|---|
| 1 | Log timestamp ไม่เรียง แต่รายงานว่าผ่าน | CONFIRMED | `_log_lines` ต่อท้าย `2026-03-18T09:20:01Z` หลังบรรทัด 09:33; check บันทึก `passed=True` แบบ hardcode; bracket format สูญเสียเวลา (`2026/03/18:06 +0000`) |
| 2 | Invoice/quotation กับ transaction export ยอดไม่ตรง | CONFIRMED | scenario ใช้ `txn_0` ร่วม แต่ยอด invoice คำนวณแยกและ transaction สุ่มแยก |
| 3 | Image ground truth ติดป้าย fragment | CONFIRMED | 8 annotations ใน sample เดิม; `exact_entity_value="Naree Boonmee"` แต่บรรทัดมี `Bill to: Naree` / `Boonmee \|` |
| 4 | Language label ดูแค่มี script | CONFIRMED | `script_counts` คืนแค่ `contains_*`; `language_check` ไม่มี share |
| 5 | `Contact N` ในเอกสารจริง | CONFIRMED | 19 cases ใน sample เดิม |
| 6 | Report ไม่ deterministic | CONFIRMED | `evaluation.json`/`.md` ต่างกันเมื่อ `PYTHONHASHSEED=1` vs `99` (4-gram จาก set ไม่เรียง) |
| 7 | Static label ใน compound line ไม่ถูกแปล | CONFIRMED | `Subtotal: … VAT 7%: … Total: …` แปลได้แค่ label แรก (direct construction; sample เดิมไม่มี Thai invoice) |
| 8 | PDF หนึ่งไฟล์บังคับทั้ง case เป็น Latin | CONFIRMED | 10 cases ใน sample เดิมที่ prompt เป็น th/mixed แต่ attachment เป็น en ทั้งหมด |
| 9 | Thai address Components ไม่สัมพันธ์กัน | CONFIRMED | tambon/amphoe/province/postcode สุ่มแยกกัน |
| 10 | Thai typo เกิดจากการ mutate code point | CONFIRMED | `_typo_word` insert/delete/swap บนอักษรไทยรวม combining mark |
| 11 | Prompt ต่อวลีซ้ำ/ไม่เข้ากัน | CONFIRMED | template `ช่วย{task}หน่อย` + task `…ให้หน่อย`; context `prod only` ใช้ได้กับ HR |
| 12 | Prompt-only paste รูปแบบเดียว | CONFIRMED | 26/26 cases เป็น fenced block พร้อม lead เดียว |
| 13 | Structure reference ชี้ row/column บน image | CONFIRMED | 2 refs (`column quantity`, `row 3`) บน jpeg |
| 14 | Multi-file bundle ไม่มีหลักฐานความสัมพันธ์ | CONFIRMED | ไม่มีฟิลด์ `relationship`; partner เลือกตาม domain |
| 15 | Old/new revision ไม่มีความหมาย | CONFIRMED | `field` + เติม `" (revised)"`, หรือเติม note อย่างเดียว |
| 16 | Vacuous consistency check นับเป็นผ่าน | CONFIRMED | 56 structure checks ที่ `references=0` ถูกนับ passed |
| 17 | เอกสารไม่ตรง implementation | CONFIRMED | อ้าง XLSX formulas (ไม่มี formula), generated_at ใน report, test ID ตัวอย่างไม่ตรง sample, CI ไม่มี v2 |
| 18 | ไม่มี schema 2.0 fixture | CONFIRMED | ไม่มี artifact 2.0 ที่ทดสอบซ้ำได้ |
| 19 | Collision risk ของ synthetic PII ไม่ได้ documented | CONFIRMED | ไม่มีหัวข้อใน `SECURITY.md` |

## 3. การแก้ไข (before → after → fix → tests)

### 3.1 Log timeline จริง
- Before: ERROR line ใช้เวลาคงที่ 09:20:01 หลัง 09:33; check hardcode True;
  bracket format ตัดชั่วโมง/นาทีทิ้ง
- After: ทุก log line มาจาก `ScenarioPlan` timeline เดียวกัน, ERROR เป็น event
  สุดท้าย, หนึ่ง format ต่อ log (ISO / `2026/03/18 09:12:00 +0000` / JSON)
- Fix: `ScenarioPlan.timestamp_value/format_timestamp`, `parse_log_timestamp`,
  `validate_log_order`; `_log_lines` และ `_access_records` parse ไฟล์ที่ render
  แล้วจริง; 1 บรรทัด = `not_evaluated`
- Tests: `LogTimelineTests` 6 tests (ordered, broken, 3 formats, single line,
  generated logs + error line, determinism)

### 3.2 Financial consistency
- Before: ยอด invoice/transaction สุ่มแยกกัน
- After: `ScenarioPlan.finance()` ถือ line items, subtotal, VAT, total, currency,
  transaction_id, invoice/due/payment date, `payment_schedule="single_payment"`
- Fix: invoice/summary table + transaction export + purchase order อ่านค่าเดียวกัน;
  observation บันทึกค่าที่ render; `linked_amount_matches`,
  `linked_currency_matches`, `linked_transaction_reference_matches`
- หลักฐานใน sample: `pgt2-trn-00039` — invoice.xlsx, transaction_export.xlsx,
  purchase_order.docx → 193,519 / THB / `TXN-2026-44116486` ตรงกันทั้งสามไฟล์
- Tests: 4 tests รวม mismatch rejection, one-sided = not_applicable,
  XLSX มี total จริง (อ่าน sheet XML)

### 3.3 Image ground truth
- Before: entity ถูกตัดข้ามบรรทัดและติดป้าย fragment
- After: Option A — entity atomic ต่อบรรทัด, หน้าขยายแทนการตัดค่า,
  `entity_strategy="atomic_line"`, `fragment_count=1`
- Fix: `_wrap_atomic` ไม่ตัดกลาง protected span; canvas คำนวณความกว้างใหม่;
  verifier ตรวจว่าค่าทั้งหมดอยู่ในบรรทัดเดียวและ bbox อยู่ในภาพ
- หลักฐาน: `pgt2-trn-00008/screenshot_chat.jpg` — `Kamonchanok Suksawat`
  อยู่ในบรรทัด `- Kamonchanok Suksawat - somchai.anan84@example.org`
  bbox `[100,128,240,18]`, fragment_count 1
- Tests: 2 image tests (valid + fragment rejected)

### 3.4 Language label integrity
- Before: `contains_thai/latin`
- After: `thai_chars`, `latin_chars`, `neutral_chars`, shares over authored text
  (entity values measured แยก), thresholds ใน config
- ค่า threshold (วัดจาก corpus): `th ≥ 0.30`, `en ≥ 0.80`, `mixed ≥ 0.10 ทั้งคู่`
  — เลือกจาก Thai docs ที่วัดได้ 0.20–0.82 และ English docs ที่ ~1.0
- Fix: `script_stats`, `language_matches`, `classify_language`,
  `document_static_text`; เอกสารที่ไม่ตรง label ถูก relabel
  (`language_routing: relabelled_from_*`) หรือ reject
- Tests: neutral chars, Thai name ใน English template, declared threshold,
  per-file-type report
- วัดได้: Thai prompt mean Thai share 0.8075, mixed 0.54, English 0.0049;
  attachment mismatch 0; residual labels 0

### 3.5 ไม่มี placeholder people
- Before: `Contact 1`, `contact1@example.com`, `+1-555-01xx`
- After: identity จริงจาก org generator แต่ทำเครื่องหมาย
  `domain="lookalike"`, `detection_expected=false` (document identity ≠ target)
- Tests: ไม่มี `Contact N`/`contact1@` ใน realistic corpus

### 3.6 Deterministic reports
- Before: 4-gram จาก set ไม่เรียง; `generated_at` อยู่ใน report
- After: sort n-gram + tie-break `(-count, phrase)`; report ไม่มี timestamp/path
- หลักฐาน: SHA-256 ของ `evaluation.json`, `evaluation.md`, `verification.json`
  เท่ากันที่ `PYTHONHASHSEED=5` และ `888` (และ test subprocess 1 vs 424242)

### 3.7 Localization
- Before: `VAT 7%:` / `Total:` ใน compound line ยังอังกฤษ
- After: inline label localization เฉพาะ static segment (ไม่แตะ entity),
  `residual_english_labels` รายงานและ gate เป็น 0
- Tests: compound line, Thai entity intact, residual = 0

### 3.8 Per-attachment Latin routing + canonical identity
- Before: PDF หนึ่งไฟล์ → org/scenario เป็น Latin ทั้ง case
- After: `ctx.latin_only` ต่อ attachment; `ลลิตา พูลสวัสดิ์` →
  `Lalita Poolsawat` โดยเก็บ `canonical_value` เดียวกัน; log routing
  `log_english_only`
- Tests: Thai DOCX คงชื่อไทย, PDF romanize, `_canonical_id` เท่ากัน,
  bundle ที่มีทั้ง docx/pdf

### 3.9 Thai address
- Before: สุ่ม component แยกกัน (เช่น ปทุมธานี + เมืองเชียงใหม่)
- After: ตาราง `THAI_ADDRESS_AREAS` (tambon/amphoe/province/postcode)
  public names + บ้าน/หมู่/ซอย synthetic
- Tests: 50 ตัวอย่างตรง tuple และ postcode

### 3.10 Thai typo realism
- Before: insert/delete/swap บน Thai code point
- After: Option A — Thai ไม่ mutate อักษร; ใช้ particle/space/punctuation
- Tests: 30 seeds ข้อความไทยยังอ่านได้ ไม่มี `หน่อยหน่อย`

### 3.11 Prompt composition
- Before: ต่อ template + task + context แบบอิสระ
- After: particle-free `INTENT_CORES`, context compatibility ตาม persona
  category, destination เฉพาะ persona ที่เกี่ยวข้อง, opener overlap guard,
  `prompt_quality_issues` (duplicate word/phrase) และ generation retry
- Tests: duplicated particle, 120 composed prompts, incompatible context,
  HR ไม่ได้ destination clause

### 3.12 Prompt-only diversity
- Before: fenced paste เดียว 26/26
- After: 9 forms (email, chat, ticket, notes, log fragment, table, report,
  code/config, short no-paste) + concentration gate
- วัดได้: top form share 0.2667, prompt-only 15 cases

### 3.13 Structure references
- After: per-extension whitelist (XLSX sheet/row/column, CSV row/column,
  PDF page/section, PPTX slide, text/log line/section, config key);
  image ไม่มี ref เลย; `user_visible: true`
- Tests: image ref = [], validation kind check

### 3.14 Multi-file relationship
- After: `bundle.relationship` = related (มี evidence: shared canonical,
  controlled revision, same archetype) หรือ intentionally_unrelated
  (ต้องเป็น negative/ambiguous); ไม่มี evidence → generation reject
- Tests: evidence required

### 3.15 Meaningful revisions
- After: status/date/amount/phone/time เปลี่ยนจริง พร้อม before/after,
  `change_type`, `source_v1`, `source_v2`; ไม่มี "(revised)"/note-only
- หลักฐาน: `pgt2-trn-00015` Servers table `production → staging`;
  `pgt2-trn-00058` timeline `09:12 → 09:17`
- Tests: field completeness

### 3.16 Consistency status
- After: `status` + `evaluated_items` + `details`; `passed == (status=="passed")`;
  N/A ต้องมี 0 items; report แยก 4 สถานะ
- วัดได้: 342 checks = 78 passed / 264 not_applicable / 0 failed / 0 not_evaluated
- Tests: vacuous N/A, report split, validation contradiction

### 3.17 Documentation
- แก้ XLSX formula claim (ไม่มี formula), generated_at/report determinism,
  ตัวอย่าง test ID (mark illustrative), CI, seed/profile, sample stats,
  image atomic semantics, schema 2.0 fixture, collision risk

### 3.18 Schema 2.0 fixture
- `datasets/compat/v2.0-sample/` 1 case + 1 attachment, hash ตรึงใน test
- Tests: validate + hash + ไม่มี field 2.1

### 3.19 Security / collision risk
- เพิ่มหัวข้อใน `SECURITY.md`: Thai phone/national-ID/bank/address
  เป็น shape/checksum-valid จึงอาจบังเอิญตรงกับของจริง; ไม่มี reserved Thai
  mobile range; ทางเลือก fake ทั้งหมดถูก reject เพราะทำให้ benchmark ง่ายเกิน
- ไม่ลดความสามารถ detector; เอกสารข้อจำกัดชัดเจน

### 3.20 Coverage / CI / safe subset / readiness
- sample ครอบคลุม text, structured text, Office, spreadsheet, PDF, image,
  config/developer, log (21 file types)
- CI: 3.9/3.12/3.13 + v1 gate + generate/validate/verify/report v2 +
  `--check-reproducible` + hash-seed compare + 2.0 fixture
- `benchmark_ready` คำนวณจากหลักฐาน dataset ไม่ใช่ unit tests;
  `benchmark_safe_cases.jsonl` + `benchmark_excluded_cases.jsonl` พร้อมเหตุผล

## 4. Tests added

`tests/test_v2_correctness.py` — 36 tests ครอบคลุม 18 หัวข้อที่กำหนด
(เรียงตาม registry ข้อ 24): log order, amount mismatch, image fragment,
language mismatch, Contact N, hashseed, compound labels, Latin scoping,
Thai address, Thai typo, duplicated phrase, incompatible context,
image structure ref, bundle evidence, revision meaning, vacuous N/A,
2.0 fixture, CI gates และ benchmark-safe/readiness

รวมทั้ง suite: **166 tests ผ่านใน ~50–57 วินาที**

## 5. Measured results (sample ปัจจุบัน)

- v2 dataset: 72 cases, 82 attachment files, 21 file types, seed 21,
  profile `benchmark-balanced`, dataset version `2.1.1`
- Verification: 68 `verified`, 4 `verified_partial`, 0 `unverified`
- file open / extraction / entity location = 1.0; duplicate rates = 0.0
- Language: prompt th 27/en 21/mixed 24; attachment th 30/en 48/mixed 4;
  11 matrix pairs; mean Thai share 0.8075 (th prompt), 0.54 (mixed), 0.0049 (en);
  mismatch 0; residual labels 0
- Cross-file: 17 cases / 77 links; multi-file 17 cases (share 0.2361);
  same-archetype 8; old/new 5
- Consistency: 78 passed / 264 N/A / 0 failed / 0 not_evaluated
- Structure refs: 28 cases / 30 refs, resolved 1.0
- Negative 0.1944; multi-domain 0.2222; attachment share 0.7917
- Prompt-only: 15 cases, 9 forms, top share 0.2667; opening top 0.0278;
  repeated phrase top 0.0833; archetype concentration 0.0833
- `benchmark_ready: true`, safe cases 68, excluded 4
  (`verification_status:verified_partial` เท่านั้น)

## 6. ตัวอย่างที่ดีขึ้น (5)

1. **Log จริง** `pgt2-trn-00004/deployment_log.log` — bracket format เต็มเวลา
   `09:12:00 … 09:33:49`, ERROR ปิดท้าย, parsed order passed (9 items)
2. **Finance bundle** `pgt2-trn-00039` — invoice.xlsx, transaction_export.xlsx,
   purchase_order.docx: 193,519 THB, `TXN-2026-44116486` ตรงกัน 3/3 checks
3. **Image atomic** `pgt2-trn-00008/screenshot_chat.jpg` — full name + email
   ในบรรทัดเดียว, bbox ตรง, fragment_count 1
4. **Revision มีความหมาย** `pgt2-trn-00015` — `production → staging`
   พร้อม location ทั้ง v1/v2; `pgt2-trn-00058` — `09:12 → 09:17`
5. **Prompt-only หลายรูปแบบ + localized Thai** — 9 forms; Thai invoice
   มี `ยอดรวมก่อนภาษี / ภาษีมูลค่าเพิ่ม 7% / ยอดรวม` ไม่เหลือ `VAT 7%:`

## 7. ตัวอย่างที่ยังอ่อน (5) — รายงานตรงไปตรงมา

1. `pgt2-trn-00011` — prompt-only ขึ้นต้น `from the log:` แต่เนื้อหาเป็น
   Employee directory (framing กับชนิด snippet ไม่ตรง)
2. `pgt2-trn-00005` — `details: contact@example.com` เป็น placeholder ที่ดู
   สังเคราะห์เกินไปใน prompt ที่เหลือดูจริง
3. `pgt2-trn-00009` — `this one ตรวจเอกสาร please` ไวยากรณ์ mixed ยังแข็ง
4. `pgt2-trn-00001` — ขอ “เช็กยอด” จาก `app_log.log` (intent กับ artifact ไม่คู่กัน)
5. `pgt2-trn-00002` — `help หน่อย อันนี้มันแปลกๆ` กว้างเกินไป ไม่มี task ชัด

## 8. Known problems ที่เหลือ

- OCR ยังเป็น layout-only (4 partial cases ถูกกันออกจาก safe subset)
- Prompt composition ยังเป็น template; ตัวอย่างข้อ 7 คือข้อจำกัดจริง
- Prompt-only form ยังไม่ผูกกับชนิด content (log ควรมาจาก log จริง)
- Finance coverage ใน sample มี 1 bundle; validator ทดสอบแล้วแต่ coverage บาง
- Cross-file links รวม document-identity lookalike (detection false)
  ผู้บริโภคต้องกรองด้วย `detection_expected`
- Thai PDF/image ไม่รองรับ (ตาม Option B เดิม)
- `verification.json` เก็บ absolute dataset path (documented)
- CI รอบนี้รันในเครื่องเท่านั้น ยังไม่ได้รัน GitHub Actions
- Cross-platform byte-identical ยังไม่ได้พิสูจน์ (CI drift step จะเป็นตัวบอก)
- Collision risk ของ phone/national-ID ยังมี (documented, ยอมรับ tradeoff)

## 9. Commands ที่รัน

```bash
PYTHONPATH=src python -m unittest discover -s tests -t . -v
PYTHONPATH=src python -m privacy_gateway_testgen evaluate \
  --config configs/default.json --out reports --dataset-out datasets/sample
PYTHONPATH=src python -m privacy_gateway_testgen generate-v2 \
  --config configs/v2/default.json --profile benchmark-balanced \
  --out datasets/v2-sample
PYTHONPATH=src python -m privacy_gateway_testgen validate-v2 \
  --dataset datasets/v2-sample
PYTHONPATH=src python -m privacy_gateway_testgen verify-v2 \
  --dataset datasets/v2-sample
PYTHONPATH=src python -m privacy_gateway_testgen report-v2 \
  --dataset datasets/v2-sample --out reports/v2 --check-reproducible
PYTHONPATH=src python -m privacy_gateway_testgen validate-v2 \
  --dataset datasets/compat/v2.0-sample
```

Report determinism: รัน `report-v2` ด้วย `PYTHONHASHSEED=5` และ `888`
แล้วเทียบ SHA-256 ของ `evaluation.json`, `evaluation.md`, `verification.json`
— เท่ากันทั้งสามไฟล์

## 10. Benchmark-safe subset

- ไฟล์: `datasets/v2-sample/benchmark_safe_cases.jsonl` (68 cases)
- ไฟล์: `datasets/v2-sample/benchmark_excluded_cases.jsonl` (4 cases)
- เหตุผล exclusion ทั้งหมด: `verification_status:verified_partial`
- เกณฑ์เข้า subset: verified, language metadata ผ่าน, consistency ไม่มี
  failed/not_evaluated; partial OCR ถูกกันออกตามข้อกำหนด

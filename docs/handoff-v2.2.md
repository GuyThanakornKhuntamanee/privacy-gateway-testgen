# Handoff — v2.2 Thai PDF & Image Rendering Upgrade

วันที่: 2026-11-21
Branch: `feat/v2.2-thai-rendering` (แตกจาก `fix/v2.1.1-benchmark-readiness`, `main` ไม่ถูกแตะ)
Commit: ดู §2

---

## 1. Executive summary

- Native PDF รองรับภาษาไทยจริง: ฝังฟอนต์ Sarabun (TrueType) พร้อม ToUnicode map
  ข้อความไทยเป็น PDF text จริง ดึงกลับด้วย pypdf ได้ตรง และมี bounding box ระดับหน้า
- PNG / JPG / JPEG รองรับไทย อังกฤษ และ mixed ด้วย Pillow + FreeType + libraqm
  (mark positioning ถูกต้อง) พร้อม degradation จาก seed ของเคส
- Scanned PDF และ Hybrid PDF (ข้อความ native + บริเวณ screenshot) ทำงานได้
  และ provenance แยก `native_text` / `scanned_page` / `embedded_image`
- ถอด `pdf_latin_only` / `png_latin_only` ออกแล้ว `language_capability` ของ
  pdf/png/jpg/jpeg = `["th","en","mixed"]`; เหลือ `log_english_only` เท่านั้น
- ground truth ยังเป็น canonical text + layout เดิม ไม่ได้เอา OCR มาเป็น truth
  และ dataset แยก subset เป็น text / OCR-required ตาม `evaluation_requirement`
- Tests 197 ตัวผ่าน (เดิม 167 + ใหม่ 30) เครื่องหมาย benchmark: `benchmark_ready: true`,
  safe 72/72 (66 text + 6 OCR), 0 excluded

## 2. Branch and commit

```text
branch: feat/v2.2-thai-rendering
base:   fix/v2.1.1-benchmark-readiness (cb008bd)
commit: 4726f7f "feat: add Thai PDF and image rendering"
```

`main` ไม่ถูกแก้, ไม่มี push/PR/tag ในรอบนี้

## 3. Dependencies added

| Package | Constraint | ที่ติดตั้งจริง | License | ใช้กับ | ทำไม | ทางเลือกที่ไม่เลือก |
|---|---|---|---|---|---|---|
| Pillow | `>=10.0,<14` | 13.0.0 | MIT-CMU (HPND) | PNG/JPG/JPEG rendering, FreeType + libraqm shaping, degradation | ต้องมี Thai shaping และ JPEG encoder ที่ถูกต้อง; ฟอนต์ bitmap เดิมรองรับไทยไม่ได้เลย | เขียน outline rasterizer + shaper เอง (เท่ากับเขียน FreeType/HarfBuzz ใหม่) |
| reportlab | `>=4.0,<6` | 5.1.0 | BSD-3-Clause | native PDF canvas, TTF embedding, ToUnicode, deterministic mode | ต้องมี Type0/CIDFont + subset + ToUnicode ที่ถูกต้อง | เขียน PDF Unicode engine เอง (เปราะและเสี่ยงผิด) |
| pypdf | `>=4.0,<8` | 7.1.1 | BSD-3-Clause | reopen PDF แล้ว extract text เพื่อ verify | content stream เป็น Identity-H + compressed; regex เดิมอ่านไม่ได้ | parse content stream + ToUnicode เอง |

- ไม่มี paid/cloud API, ไม่มี runtime network, ไม่มี telemetry
- ประกาศใน `pyproject.toml` (`dependencies`) และ CI ติดตั้งด้วยเวอร์ชันเดียวกัน
- ขนาด: ฟอนต์ที่ vendor 2 ไฟล์รวม ~180 KB; ไฟล์ PDF ตัวอย่าง ~23–45 KB (reportlab subset ฟอนต์)
- ผลต่อ determinism: byte-identical ภายในชุด dependency ที่ pin ไว้ บนแพลตฟอร์มเดียว
  (ทดสอบ reportlab `invariant=1`, Pillow encoder คงที่)

## 4. Font strategy and license

| Field | Value |
|---|---|
| Family | Sarabun Regular + Bold |
| License | SIL Open Font License 1.1 (`assets/fonts/OFL.txt`) |
| Source | `https://github.com/google/fonts/tree/main/ofl/sarabun` (โปรเจกต์: cadsondemak/Sarabun) |
| Path | `src/privacy_gateway_testgen/assets/fonts/` (package-relative, ผ่าน `renderers/fonts.py`) |
| SHA-256 | Regular `226d4f36…b3b2f1`, Bold `d38308ca…7fa83b9` |
| ทำไม Sarabun | มีทั้งไทย/ละติน/เลขไทย/฿ ในฟอนต์เดียว จึงไม่ต้อง fallback ต่อ run |
| Fallback | ไม่มี: ฟอนต์หายหรือ Pillow ไม่มี libraqm → `RendererUnavailable` (ไม่เงียบ) |

ทดสอบ glyph coverage ด้วย `_missing_glyphs()`: ถ้าฟอนต์ไม่มี glyph จะ raise
ไม่ยอมให้ `?` หรือ notdef กลายเป็น ground truth

## 5. Thai PDF architecture

`v2/renderers/pdf.py` เขียนใหม่บน ReportLab แต่ยังคุม layout เอง (top-down y):

- ลงทะเบียน `Sarabun` / `Sarabun-Bold` จาก asset ภายในแพ็กเกจ (ไม่มี system font)
- `PdfWriter` เก็บ page/line box, ความกว้างจาก `stringWidth`, ตัดบรรทัดด้วย
  `textlayout.wrap_ranges` (cluster-safe + entity atomic)
- ตาราง: วัดความกว้างคอลัมน์จากข้อความจริง, วาดเส้นคั่น, บันทึก bbox ต่อเซลล์
- code/log: ASCII ใช้ Courier, มีภาษาไทยใช้ Sarabun (เพื่อไม่ให้ไทยหาย)
- slide deck ที่ render เป็น PDF: 1 สไลด์ = 1 หน้า (แก้บั๊กเดิมที่ได้แค่หน้า title)
- metadata: `mode: native|hybrid|scanned`, `font.embedded`, `canonical_lines`
- ความปลอดภัย: ไม่มี JavaScript/Launch/OpenAction/EmbeddedFile (มีเทสต์ตรวจ)

## 6. Thai image architecture

`v2/renderers/images.py` เขียนใหม่บน Pillow:

- ฟอนต์: Sarabun body 21px / heading 28px / code 19px
- bbox ของ entity วัดจาก “ความกว้างของ prefix ที่ render จริง” ไม่ใช่จำนวนตัวอักษร × fixed advance
- wrapping วัดเป็น pixel และไม่ตัดกลาง Thai cluster หรือกลาง entity; ถ้าคำยาวเกิน
  จะขยาย canvas (ทดสอบ: `image_width=420` → ขยายจริง)
- style: scan/document, receipt, form, id_card, terminal, config, code, dashboard,
  chat (bubble สลับซ้าย/ขวา), email
- degradation: noise (zero-mean), blur, หมุน ±1.1° (เฉพาะเอกสาร), gradient brightness;
  ทั้งหมดมาจาก `image_seed`
- หมุนแล้วแปลง bbox ของทุก entity และ line เป็นพิกัดสุดท้าย (`bbox_space: final`)

## 7. Native / scanned / hybrid PDF support

| Mode | เนื้อหา | Verification | หมายเหตุ |
|---|---|---|---|
| native | PDF text จริง (Sarabun + ToUnicode) | `verified` + `pdf_text_extracted` | ดึง entity และ canonical line กลับได้ |
| scanned | raster ทั้งหน้า (JPEG/PNG embedded) | `verified_layout` | ไม่ได้รัน OCR, bbox เป็น `image_pixels` + `page_bbox` (points) |
| hybrid | ข้อความ native + บริเวณภาพ embedded | `verified_layout` | entity ฝั่ง native = `pdf_text`/`native_text`, ฝั่งภาพ = `pdf_image`/`embedded_image` |

Hybrid ถูกเลือกทุกเคสคู่ (sequence คู่) ที่มี PDF และมี block ชนิด
code/log หรือ bullet ติดกัน ≥2 รายการ; block นั้นถูกวาดเป็นภาพเท่านั้น
จึงไม่มี ground truth ซ้ำสองที่

## 8. Ground-truth semantics

```text
canonical text (span-first)  +  entity value  +  rendered location  +  bbox/page/provenance
```

- ไม่มี OCR ในขั้น generation; ไม่มี `ocr_verified`
- raster: `expected_ocr_text` = ข้อความก่อน render, `entity_strategy: atomic_line`,
  `fragment_count: 1`
- native PDF: `character_start/end`, `x/y/width/height`, `page`, `source_type`
- attachment: `evaluation_requirement` = `direct_text_extraction` | `ocr_required`,
  `render_mode`, `text_shaping`

## 9. Bounding-box verification

- Image: เปิดไฟล์ด้วย Pillow, เทียบ width/height กับ metadata, bbox ต้องอยู่ในขอบ,
  entity ต้องอยู่ในบรรทัดเดียวกับ `expected_ocr_text`
- Scanned/hybrid PDF: bbox ต้องอยู่ในขอบภาพ และ `page_bbox` ต้องอยู่ใน 595×842 point
- หมุนภาพ: bbox ถูก transform ด้วยเมทริกซ์เดียวกับที่ใช้หมุน pixel แล้ว clip
- native PDF: entity ต้องปรากฏในข้อความของ “หน้านั้น” หลัง normalize ช่องว่างเท่านั้น

## 10. Language-routing changes

- `language_capability("pdf"|"png"|"jpg"|"jpeg") = ("th","en","mixed")`
- `log` ยังเป็น `("en",)` → `language_routing: log_english_only`
- ลบ `LATIN_ONLY_RENDERERS` และเส้นทาง `*_latin_only` ออก แต่คงตัวแปร routing ไว้
  (เผื่อ renderer ในอนาคตที่ capability แคบลง)
- `relabelled_from_*` ยังทำงาน (วัด script share จริงแล้วเปลี่ยน label)
- ตัวอย่าง: ใน `datasets/v2-sample` มี routing 40 รายการ = `log_english_only` 10 +
  `relabelled_from_*` 30 และ **ไม่มี** `*_latin_only` เลย

## 11. Capability matrix

| Format | Thai | English | Mixed | Text extraction | Layout GT | OCR needed |
|---|---:|---:|---:|---|---|---:|
| Native PDF | yes | yes | yes | yes (pypdf round-trip) | page/bbox | no |
| Hybrid PDF | yes | yes | yes | native part only | page bbox + image bbox | partly |
| Scanned PDF | yes | yes | yes | no | image + page bbox | yes |
| PNG | yes | yes | yes | no | bbox | yes |
| JPG / JPEG | yes | yes | yes | no | bbox | yes |

(ดู `docs/capability-matrix.md`; เขียน “yes” เฉพาะที่มีเทสต์และ gate ผ่าน)

## 12. Test results

```text
Ran 197 tests in 30s — OK
```

- ของเดิม 167 ผ่านทั้งหมด (v1, v2.0 fixture, v2.1, v2.1.1, benchmark readiness,
  safe subsets, ScenarioPlan, report determinism, finance, atomic images, identity)
- ใหม่ 30: `tests/test_v2_thai_rendering.py` 29 ตัว + regression ของ
  label localization 1 ตัวใน `test_v2_language.py`
- เทสต์ที่แก้เพราะพฤติกรรมเปลี่ยน (ไม่ใช่ผ่อน): `test_v2_consistency` อ่าน PDF
  ด้วย pypdf แทนการ decode latin-1, `test_v2_language` เลิกคาดหวัง `ValueError`
  กับภาษาไทย และตรวจ capability/routing แทน

## 13. Dataset / sample results

`datasets/v2-sample` (benchmark-balanced, seed 21, 72 cases):

```text
files 75 | file types 19 | verified 64 | verified_partial 8
benchmark_ready: true | safe 72 (66 direct_text + 6 ocr_required) | excluded 0
native PDF 6/6 verified | hybrid 2 | raster 9/9 verified, shaping 9/9 harfbuzz
Thai/mixed PDF+image 6/6 verified | routed 40 (log 10, relabelled 30, latin_only 0)
```

`datasets/v2-thai-sample` (profile `thai-rendering`, seed 21, 16 cases):

```text
files 24 (pdf 6, png 8, jpg 4, jpeg 1, docx 2, md 1) | Thai 19 / mixed 3 / en 2
native 4, scanned 2, hybrid 1 | Thai/mixed files 19/19 verified
reports/v2-thai: PASS, benchmark_ready true, safe 16 (3 text + 13 OCR)
```

ตัวอย่างที่ตรวจด้วยตา (rasterize ด้วย pypdfium2 นอก repo):

- `datasets/v2-thai-sample/attachments/pgt2-trn-00011/meeting_minutes_v1.pdf` (native Thai)
- `.../pgt2-trn-00010/meeting_minutes_v1.pdf` (hybrid: รายงานไทย + พาเนล terminal)
- `.../pgt2-trn-00002/scanned_invoice.pdf` (scanned Thai invoice)
- `.../pgt2-trn-00004/screenshot_chat.png` (chat ไทย)
- `.../pgt2-val-00002/screenshot_config_v1.png` (config screenshot ไทย)

## 14. Determinism results

- `report-v2 --check-reproducible` → `reproducible: True` ทั้ง v2-sample และ thai-sample
- `evaluation.json` / `evaluation.md` / `verification.json` SHA-256 เท่ากันเมื่อรัน
  ด้วย `PYTHONHASHSEED=5` และ `888`
- PDF/PNG/JPEG: render ซ้ำได้ byte เท่ากัน; subprocess คนละ `PYTHONHASHSEED`
  ให้ SHA-256 ของ PDF เท่ากัน (มีเทสต์)
- reportlab ใช้ `invariant=1` (creation date + /ID คงที่), Pillow encoder คงที่

## 15. Cross-platform status

- ทดสอบจริงเฉพาะ Windows 11 + Python 3.13.1 (สภาพแวดล้อมนี้)
- ไม่ได้รัน 3.9/3.12 locally; CI matrix 3.9/3.12/3.13 ถูกอัปเดตให้ติดตั้ง dependency
  และตรวจ shaping + Thai rendering แล้ว แต่ **ยังไม่เคยรันบน GitHub** (branch ยังไม่ push)
- byte-identical ข้าม OS/เวอร์ชัน library **ไม่รับประกัน** — รับประกันเฉพาะ content
  (extracted text, spans, boxes, case JSON) ตาม `docs/v2.2-thai-rendering-design.md`

## 16. Benchmark-ready status

```text
benchmark_ready: true
checks: no failed ground-truth verification, no known high issue, linked finance
consistent, timeline valid, entity fragments valid, no replacement glyphs,
Thai file rendering verified, language metadata valid, safety checks pass,
no schema errors, deterministic dataset/report output
benchmark_safe_text_cases.jsonl:  66 cases
benchmark_safe_ocr_cases.jsonl:    6 cases
benchmark_excluded_cases.jsonl:    0 cases
```

การเปลี่ยนจาก v2.1.1: เดิม raster/scan ถูก exclude เพราะ layout-only ตอนนี้แยกเป็น
subset `ocr_required` แทน เพราะ gateway เป็นผู้ทำ OCR ไม่ใช่ generator

## 17. OCR boundary

- generator ไม่รัน OCR และไม่อ้าง OCR accuracy
- ground truth คือ canonical text + layout; `expected_ocr_text` เป็นข้อความก่อน render
- `verified_partial` (ระดับเคส) / `verified_layout` (ระดับไฟล์) คือสถานะจริงของ raster
- OCR-required cases ใช้ตรวจ gateway ได้ แต่ต้องเทียบกับ ground truth และห้ามใช้
  วัด precision/recall ของ OCR เอง

## 18. Known limitations

1. Byte identity ของ PDF ขึ้นกับเวอร์ชัน ReportLab/Pillow และแพลตฟอร์ม
2. Scanned PDF = 1 หน้า (multi-page scan ยังไม่รองรับ)
3. `page_bbox` ของบริเวณ raster เป็น point space ขณะที่ `bbox` เป็น pixel space
   ผู้ใช้ต้องเลือกใช้ให้ตรง
4. Thai wrapping ไม่มี dictionary word-break: คำไทยยาวที่ไม่มีช่องว่างจะตัดที่
   cluster boundary (อ่านออก แต่บางคำถูกแบ่งตามที่พจนานุกรมไม่ต้องการ)
5. Hybrid panel เป็นข้อความ flattened (ไม่มีเส้นตาราง) เพราะวาดด้วย raster text layout
6. `log` ยัง English-only โดยเจตนา
7. PDF ของ deck ตอนนี้ 1 สไลด์ = 1 หน้า แต่ไม่มี speaker notes
8. ยังไม่ได้วัด OCR accuracy ของ raster ใด ๆ (นอกขอบเขต)

## 19. Remaining problems (examples ที่ยังอ่อน)

| # | ตัวอย่าง | ปัญหา |
|---|---|---|
| 1 | `datasets/v2-thai-sample` gate `min_file_type_count` = 4 | sample นี้เป็น focused sample (6 file types) จึงต้อง override gate ใน profile — ไม่ใช่ค่าเดียวกับ dataset หลัก |
| 2 | `pgt2-trn-00010/meeting_minutes_v1.pdf` | พาเนล screenshot แสดงผลแบบ terminal แต่เนื้อหาเป็นรายชื่อผู้เข้าร่วม (table/bullet ที่ถูก flatten) ยังไม่เหมือน screenshot จริง |
| 3 | `pgt2-trn-00002/scanned_invoice.pdf` | ใบเสร็จสแกนยังใช้เส้นคั่นแบบข้อความ `|` และไม่มีเส้นตาราง |
| 4 | `pgt2-trn-00004/screenshot_chat.png` | bubble ของ chat ไม่ตัดข้อความยาวตามความกว้าง bubble (ข้อความล้นออกนอกกรอบเล็กน้อย) |
| 5 | `pgt2-trn-00011/meeting_minutes_v2.pdf` | old/new revision คู่: PDF ทั้งสองเป็น native แต่ความต่างของเนื้อหาเป็นค่าใน scenario ไม่ได้แสดง diff ให้เห็นชัด |
| 6 | รายงาน `routed_attachments = 40` | ตัวเลขนี้รวม `relabelled_from_*` ด้วย (30 รายการ) ทำให้อ่านแล้วอาจเข้าใจผิดว่าเป็นการ route เพราะ renderer ไม่รองรับ |

## 20. Exact commands used

```powershell
# branch
git checkout -b feat/v2.2-thai-rendering

# dependencies (declared in pyproject.toml)
python -m pip install pillow reportlab pypdf

# tests
$env:PYTHONPATH="src"; python -m unittest discover -s tests -t . -v

# v1
$env:PYTHONPATH="src"; python -m privacy_gateway_testgen evaluate --config configs/default.json --out reports --dataset-out datasets/sample

# v2 main sample
$env:PYTHONPATH="src"; python -m privacy_gateway_testgen generate-v2 --config configs/v2/default.json --profile benchmark-balanced --out datasets/v2-sample
$env:PYTHONPATH="src"; python -m privacy_gateway_testgen validate-v2 --dataset datasets/v2-sample
$env:PYTHONPATH="src"; python -m privacy_gateway_testgen verify-v2 --dataset datasets/v2-sample
$env:PYTHONPATH="src"; python -m privacy_gateway_testgen report-v2 --dataset datasets/v2-sample --out reports/v2 --check-reproducible

# Thai rendering sample
$env:PYTHONPATH="src"; python -m privacy_gateway_testgen generate-v2 --config configs/v2/default.json --profile thai-rendering --count 16 --out datasets/v2-thai-sample
$env:PYTHONPATH="src"; python -m privacy_gateway_testgen validate-v2 --dataset datasets/v2-thai-sample
$env:PYTHONPATH="src"; python -m privacy_gateway_testgen verify-v2 --dataset datasets/v2-thai-sample
$env:PYTHONPATH="src"; python -m privacy_gateway_testgen report-v2 --dataset datasets/v2-thai-sample --out reports/v2-thai --check-reproducible

# schema 2.0 compatibility fixture
$env:PYTHONPATH="src"; python -m privacy_gateway_testgen validate-v2 --dataset datasets/compat/v2.0-sample

# report determinism under different hash seeds
$env:PYTHONHASHSEED="5";   $env:PYTHONPATH="src"; python -m privacy_gateway_testgen report-v2 --dataset datasets/v2-sample --out build/hash5
$env:PYTHONHASHSEED="888"; $env:PYTHONPATH="src"; python -m privacy_gateway_testgen report-v2 --dataset datasets/v2-sample --out build/hash888
```

## Appendix — concrete examples

**Native Thai PDF** (`pgt2-trn-00011/meeting_minutes_v1.pdf`, pypdf extract):

```text
รายงานการประชุม ประชุมแพลตฟอร์มรายสัปดาห์ วันที่: 18 มีนาคม 2569 | Location: internal video call
ผู้เข้าร่วม - อารีย์ อินทรีย์ - siriporn.maneerat25@example.net - ปิยะดา ศรีสุข ...
บันทึก ทีมทบทวน checklist การ deploy และแผนย้ายข้อมูลลูกค้า ...
รายการที่ต้องทำ - ผู้รับผิดชอบ: ปิยะดา ศรีสุข - confirm the migration window.
```

**Mixed PDF** (`pgt2-trn-00004/architecture_notes.pdf`):

```text
บันทึกสถาปัตยกรรมระบบ ... ทราฟฟิกเข้าผ่าน load balancer สาธารณะและไปถึงบริการ API
Worker ดึงงานจากคิวและเก็บผลลัพธ์ใน PostgreSQL
The worker uses this integration credential: sk_example_fake_6806355ad6e5b7ce8cb4c4b3
Platform ผู้รับผิดชอบ: อรทัย บุญมี (maneerat.siriporn25@example.net)
```

**Thai PNG** (`pgt2-trn-00004/screenshot_chat.png`) — ข้อความไทย render ด้วย
Sarabun + raqm, entity bbox อยู่ในขอบภาพ 900×737

**Thai JPEG** (`pgt2-val-00002/screenshot_config.jpeg`) — ภาพ JPEG คุณภาพ 82,
bbox ยังตรงหลัง compression (คู่กับ `screenshot_config_v1.png` ในเคสเดียวกัน)

**Scanned Thai PDF** (`pgt2-trn-00002/scanned_invoice.pdf`) — 1 หน้า,
`pdf_image` 3 รายการ, `source_type: scanned_page`, `page_bbox` ในขอบ 595×842

**Cross-file Thai** (`pgt2-trn-00010`): `meeting_minutes_v1.pdf` (hybrid) +
`meeting_minutes.md` (native text) — ชื่อ, อีเมล, host และรายการงานมาจาก
`ScenarioPlan` เดียวกัน; และ `pgt2-trn-00011` มี `meeting_minutes_v1.pdf` +
`meeting_minutes_v2.pdf` (old/new revision) ที่ค่าใน `revision_changes` ตรงกัน

# v2 sample dataset

Synthetic file-aware dataset generated with schema `2.0`, seed `7`, profile
`real-world-enterprise`:

```bash
PYTHONPATH=src python -m privacy_gateway_testgen generate-v2 \
  --config configs/v2/default.json --profile real-world-enterprise \
  --out datasets/v2-sample
```

- 72 cases, 70 attachment files
- 10 file types: CSV, DOCX, PDF, PPTX, TXT, XLSX, JSON, JPG/JPEG, MD
- Thai, English and mixed-language prompts
- 18 negative and 10 ambiguous cases
- 5 OCR-oriented image/scanned-PDF cases (`verified_partial`)

`cases.jsonl` is the case list, `ground_truth/entities.jsonl` is the flattened
annotation list, `attachments/<test_id>/` holds the real files, and
`manifest.json` records versions, seed, distributions, hashes and verification
status. All content is synthetic and non-functional. Do not add real customer
data, credentials or production infrastructure.

Re-verify the dataset from disk:

```bash
PYTHONPATH=src python -m privacy_gateway_testgen validate-v2 --dataset datasets/v2-sample
PYTHONPATH=src python -m privacy_gateway_testgen verify-v2 --dataset datasets/v2-sample
```

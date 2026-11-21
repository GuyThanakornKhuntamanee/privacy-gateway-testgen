# NOTICE — synthetic test data

Every prompt, entity value and attachment in this directory is synthetic.
It was produced deterministically from a seed by `privacy-gateway-testgen`.
No value describes a real person, account, credential, host or payment card.

## Where the synthetic marking lives (out-of-band)

- every attachment record in `cases.jsonl` carries `"synthetic": true`;
- `manifest.json` carries `"synthetic": true` and this notice's hash;
- reserved example domains, `.internal` hosts, test-BIN card numbers and `example`/`fake` credential markers stay in the content for detector realism.

## In-band disclosure

- `disclosure` mode: `metadata`
- generated files contain no "synthetic" notice: a detector under test must
  not read a hint that could suppress a real detection. Use this notice and
  `cases.jsonl` when the dataset is shared with people.

## Ground truth

- canonical text and layout are authoritative; no OCR engine was run;
- `ground_truth/entities.jsonl` lists every expected detection with its location;
- raster cases require OCR from the system under test and are listed separately
  in `benchmark_safe_ocr_cases.jsonl`.

# Bundled font assets

| Field | Value |
|---|---|
| Family | Sarabun (Regular, Bold) |
| Upstream | <https://github.com/google/fonts/tree/main/ofl/sarabun> (project: <https://github.com/cadsondemak/Sarabun>) |
| License | SIL Open Font License 1.1 — see `OFL.txt` in this directory |
| Fetched | 2026-11-21 from `google/fonts` (`Sarabun-Regular.ttf`, `Sarabun-Bold.ttf`, `OFL.txt`) |
| SHA-256 (Regular) | `226d4f368fbc0457990ddef2692679badfd2c1a4e89e5ac4d43c10ba7743b2f1` |
| SHA-256 (Bold) | `d38308ca27d067b9a1b79006337c1f9a66c29aa016d96a9d88d3801da7fa83b9` |

Sarabun is used because it carries Thai consonants and combining marks, Latin
letters, digits, Thai digits and `฿` in one family, so mixed Thai-English
documents need no per-run font fallback.

The renderers resolve these files through
`privacy_gateway_testgen.v2.renderers.fonts.font_path()` — a package-relative
path. No system font is discovered, and a missing asset raises
`RendererUnavailable` instead of silently substituting another face.

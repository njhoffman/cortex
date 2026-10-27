# Upstream fixtures

These small, unmodified source files were fetched on 2026-10-22 (eg and cheatsheets-zip on 2026-10-27) for offline parser regression tests. Devhints declares no content license, so its tests use synthetic Markdown only. `manifest.json` records the exact upstream Git commit, original paths, SHA-256 hashes, and reviewed extraction expectations. License files are copied unchanged beside each fixture. Synthetic edge cases live in the tests themselves.

| Directory | Original collection | Content license |
| --- | --- | --- |
| `tldr` | [tldr-pages team and contributors](https://github.com/tldr-pages/tldr) | CC BY 4.0; see `tldr/LICENSE.md` |
| `cheat` | [cheat/cheatsheets contributors](https://github.com/cheat/cheatsheets) | CC0 1.0; see `cheat/.github/LICENSE.txt` |
| `navi` | [denisidoro/cheats contributors](https://github.com/denisidoro/cheats) | CC0 1.0; see `navi/LICENSE` |
| `cheat-sheets` | [chubin/cheat.sheets contributors](https://github.com/chubin/cheat.sheets) | MIT; see `cheat-sheets/LICENSE` |
| `eg` | [srsudar/eg contributors](https://github.com/srsudar/eg) | MIT; see `eg/LICENSE.txt` |
| `cheatsheets-zip` | [Fechin/reference contributors](https://github.com/Fechin/reference) | GPL-3.0; see `cheatsheets-zip/LICENSE` |

Cortex transforms these examples during tests into its canonical description/template records. The original fixture files remain unmodified. The fixtures' content licenses are independent of Cortex's code.

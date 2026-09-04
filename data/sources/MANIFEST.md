# Two Point Campus source manifest

Append-only factual acquisition register. Source identities and acquisition
details remain repository-only; public surfaces expose only the permitted
build/coverage evidence.

| Date | Source | Scope | Class | Result |
|---|---|---|---|---|
| 2026-08-25 | `store.steampowered.com/api/appdetails` (`cc=us`, `l=english`) | appids 1649080, 1884560, 1907450, 2312070, 2195430 | official-api | DLC names resolved: 1884560=Space Academy, 1907450=School Spirits, 2312070=Soundtrack, 2195430=Medical School (not installed). Captured field `supported_languages_raw` on `steam-appdetails-1649080.json` lists **11** storefront languages (English, French, Italian, German, Spanish - Spain, Korean, Polish, Portuguese - Brazil, Simplified Chinese, Traditional Chinese, Turkish). Japanese and Russian are omitted from that storefront field even though the client's 13 localization bundles include both. This row is not equal to the client locale inventory. No `es-419` entry. |
| 2026-08-25 | `api.steampowered.com/ISteamNews/GetNewsForApp` v2 | appid 1649080, count=5 | official-api | latest 2026-08 store events; no patch-cadence signal; raw JSON beside this manifest |
| 2026-08-25 | Two Point Campus community-wiki API (MediaWiki 1.43.9), competitor ladder F3 | siteinfo, allcategories (282), 16 category-member pulls (Items complete 837), 91 page wikitexts in 6 batches | competitor-community | R6 input `competitor/fandom/model.jsonl` has 383 rows; provenance and paced-request results are recorded beside it |
| 2026-08-25 | second community-wiki instance, competitor ladder exhausted | API response 401; browser root returned an authentication wall after permitted attempts | competitor-community (WALL) | no content readable at any rung; exact wall and owner-corpus unblock in `competitor/wiki-gg/PROVENANCE.md` |
| 2026-08-25 | Steam Community guides for app 1649080, competitor ladder F2 | trend list (9 guides) + 4 guide bodies (~26 KB text: tips/mechanics, Kudosh/loans/R&D, level rosters, money) | competitor-community | R6 input `competitor/steam-guides/model.jsonl` has 34 rows; provenance beside it |

<!-- END OF data/sources/MANIFEST.md -->

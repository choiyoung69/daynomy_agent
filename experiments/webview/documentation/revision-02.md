# WebView documentation recheck — revision 02

2026-10-28. Static documentation review of implementation revision 02. This supplements `result.md`; it preserves the first review and its historical findings. No implementation, tests, source knowledge, original reference or existing product/design documents were changed by this role.

## Evidence and result

Rechecked `clients/webview/DESIGN.md` against `web/styles.css`, `PRODUCT.md`, `.impeccable/design.json`, and the changed `web/src/app.ts` / `web/src/market.ts`. Recomputed hashes for all 12 paths from the first review. Exactly DESIGN.md, app.ts and market.ts changed; the other nine reviewed files, including the original visual authority, are unchanged. Every overlapping path matches `experiments/webview/implementation/web/revision-02/source-hashes.json`. Exact hashes are in `revision-02-source-hashes.json`.

- **Earlier radius wording drift resolved.** DESIGN.md now explicitly records 8px inputs/type filters/secondary buttons, 7px country segments within a 10px group, and 4px result rows. These match CSS. Its clarification that JSON `controlRadiusPx: 8` means the primary control radius resolves the previous blanket interpretation without changing the custom JSON.
- **Responsive copy corrected.** The empty-state instruction now says “검색창에서 종목을 찾아보세요.” It no longer assumes search is to the left, and fits both the desktop split layout and the 720px single-column layout documented in DESIGN.md.
- **Fetch receiver correction observed in source.** MarketApi now defaults to `globalThis.fetch.bind(globalThis)`. Product constraints concerning real API responses, manual string input, raw dates and explicit retry are unchanged. This review observes the correction; it does not certify its browser/native behavior or adopt the implementation role's successful run as independent evidence.
- **Existing visual identity remains consistent.** The unchanged core palette, type sizes, layout values and Operate hierarchy continue to agree across PRODUCT, DESIGN, custom JSON and CSS. No replacement visual world is introduced.

## Continuing limits

DESIGN.md remains concise custom prose, and design.json remains a custom token snapshot. They are not the canonical frontmatter/section structure and schemaVersion 2 sidecar described by Impeccable's document reference. This is an existing format/portability limitation, not a new visual mismatch; no schema conversion or new design-system generation was performed. JSON still documents core tokens rather than every CSS color, state or component radius.

No new unresolved documentation mismatch was found within this comparison. This is not complete validation: no browser, emulator, device, server, DB or host build ran in this documentation recheck. The independent verifier/coordinator owns runtime acceptance, including actual focus, accessibility, clipping, keyboard/scroll and native lifecycle behavior. Earlier preflight evidence remains historical and was not rerun here.

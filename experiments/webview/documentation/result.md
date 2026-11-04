# WebView design documentation handoff

2026-10-28. Documentation role; static source comparison only. Existing files were preserved. This extends the original DAYNOMY utility interface rather than establishing a new visual identity. Runtime verification and source acceptance remain with the independent verifier/coordinator.

## Evidence checked

- Product/scope: `clients/webview/PRODUCT.md`, `clients/webview/README.md`, `spec/webview/README.md`.
- Existing visual documentation: `clients/webview/DESIGN.md`, `clients/webview/.impeccable/design.json`.
- Actual implementation: `clients/webview/web/styles.css`, `web/src/app.ts`, `web/src/market.ts`, `web/index.html`.
- Original authority: `reference/2026-DAYNOMY-dev/frontend/src/index.css`, portfolio form styles in `features/portfolio/portfolio.css`, and stock/price hierarchy in `features/portfolio/components/PortfolioTransactionEditor.tsx`.
- Impeccable `reference/document.md` and `reference/craft-floor.md`; implementation reports at `experiments/webview/implementation/web/report.md` and `implementation/hosts/result.json` were read as handoff context, not independent runtime evidence. The session's already-reported context-launcher unavailability was not retried.

## Comparison

The documented white surfaces, purple focus, blue actions and action tint match the implementation and original authority. The darker secondary text is explicitly documented as a readability adjustment. Body/label/heading sizes, 1064px maximum width, 720px one-column breakpoint, thin separators, minimum 48px controls, mobile safe-area padding, focus outline, input caret/selection colors, and reduced-motion handling are present in CSS. These are source findings; no computed-style or screenshot claim is made.

The interaction documentation matches source structure: country/type precede results; selecting a result focuses the labeled price field; clearing selection focuses search; Korean status/error/empty copy and explicit retry controls exist; manual input and deletion retain strings; dates remain raw strings; remote strings use textContent; foreground events are combined with document visibility. The draft is memory-only. The login/save limitation is visibly stated and no save control is rendered. Behavior under actual browser/WebView execution is outside this review.

## Documentation drift and format limits

1. **Small wording drift:** DESIGN.md's “8px input/control corners” is too broad. Inputs, category filters and secondary buttons use 8px, but country segments use 7px, their surrounding surface 10px, and stock results 4px. Suggested wording: “Inputs, type filters and secondary buttons use 8px corners; country segments use 7px within a 10px group, and result rows use 4px.” The JSON `controlRadiusPx: 8` should be read as the primary control radius, not a universal rule. This was reported to the coordinator; no implementation or existing documentation was changed.
2. **Portability limit, not a visual mismatch:** DESIGN.md is concise prose without the canonical frontmatter/section structure, and design.json is a custom token snapshot without schemaVersion 2, extensions or component snippets. Their values agree with the reviewed CSS, but they should not be described as a schema-validated Impeccable/Stitch design-system export. Migrating them would be separate authorized work; this handoff does not generate a new system or silently replace either file.
3. The JSON intentionally contains only core tokens; CSS also has soft surface, control border, hover/action-deep colors and component-specific radius values. Missing entries are not evidence those values are unused.

## Checks and limits

`python3 scripts/check.py preflight` exited 0: original snapshot 29/29 matched; cargo, rustc and psql were available. Preflight did not exercise behavior. No browser, emulator, device, host build, server or DB was run by this role. Accessibility contrast, clipping, keyboard/scroll behavior, actual focus movement, screen-reader announcements and native lifecycle behavior are not certified by this static documentation review. Separate implementation reports do not close those checks.

Only `experiments/webview/documentation/` was written. `source-hashes.json` identifies the exact reviewed source/document versions; later coordinator or implementation changes require a fresh comparison of the changed files.

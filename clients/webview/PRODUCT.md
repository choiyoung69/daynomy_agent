# DAYNOMY WebView pilot

## Platform
Web UI inside Android WebView and iOS WKWebView. The web remains a web interface.

## Confirmed scope
The user requested knowledge-base driven test writing, a separate implementation agent, then a separate verification agent. First flow: stock search → latest stored close → editable unit price. This is a local validation pilot; authentication and transaction saving are outside the current scope and visibly unavailable.

## Stack
TypeScript ESM, native CSS, Node same-origin static/API development server. Android and iOS host projects are separate. Contract: `spec/webview/README.md`; source evidence: `experiments/webview/knowledge/manifest.json`.

## Constraints
Use real backend responses. Preserve manual input as a string, including deletion; preserve API date strings without timezone conversion. No privileged JS bridge, token replication, invented portfolio data, or automatic retry loop. Preserve the original DAYNOMY utility interface hierarchy and white/purple/blue visual system.

## Accessibility
Korean visible labels, semantic fields/buttons, announced loading/error states, keyboard focus, 48px controls, mobile safe areas and scrollable content.

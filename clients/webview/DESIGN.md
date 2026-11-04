# WebView utility interface

Mode: Operate. This surface extends the original stock/transaction editor's task hierarchy. The visual authority is `reference/2026-DAYNOMY-dev/frontend/src/index.css` and portfolio editor/form styles, inspected 2026-10-28. The original uses white with purple/blue; it does not establish a green palette.

Tokens: background/surface #ffffff, text #171821, secondary #59616e (darkened for readable small labels), border #e4e7ef, action #326bd5, action tint #edf3fc, keyboard focus #5144d8, error #b32c3a. System UI sans, body 16px, labels 14px, primary heading 25.6px desktop / 22px mobile, section headings 18px. Flat sections with thin separators and no decorative shadows or data illustrations. Inputs, type filters and secondary buttons use 8px corners; country segments use 7px within a 10px group, and result rows use 4px. The JSON controlRadiusPx token describes the primary 8px control radius, not every component.

Desktop places stock search alongside selected stock and price. At 720px the sections form one scrollable column; search comes first. Country and category controls precede results. Selection moves keyboard focus to the labeled price field. Results and selected names wrap safely, with all remote strings inserted via textContent. Minimum controls are 48px. Automatic/manual/error price states remain explicit and no save affordance is shown.

Transitions only clarify control focus; reduced motion disables them. UI loading never hides existing typed price. Native foreground/background is merged with page visibility events. The draft is memory-only and not represented as durable process restoration.

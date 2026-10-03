# Accessibility intent — not verified conformance

Current 0.2.0 Signal UI has not completed runtime accessibility checks. The browser-check results below refer only to the September 24 v0.1.0 interface. Do not carry them forward to the new layout.

Source includes semantic controls, text-plus-icon statuses, a skip link, focus-visible rings, keyboard-native selects, labelled fields, a native modal dialog, explicit loading/error messages, wrapped evidence text, responsive layouts and reduced-motion styles. Run selectors include bounded local filtering. No tooltip or color is the only source of meaning.

T29/T30/T33 author keyboard/focus, widths1440/1024/390, long/error/partial states and screenshot review. Local browser checks exercised names, keyboard focus, dialog closure/return, reduced motion and overflow at the three target widths. The actual fixture images were reviewed separately. Dedicated screen-reader testing, browser zoom and exhaustive state/contrast audits remain pending. Do not claim WCAG conformance from source review. Preserve issues with actual viewport/snapshot and reproduction steps after optional evaluation.

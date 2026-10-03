# Signal 03 application mapping
Source design: Signal 03, authored in Figma. See the [public concept gallery](DESIGN.md).
The four approved design frames informed the source mapping. Existing shadcn/Radix Button behavior is retained; no generated standalone Tailwind component tree was substituted for the application.

| Figma pattern | Application source |
|---|---|
| Night navigation rail and compact mobile navigation | frontend/src/main.tsx, styles/tokens.css |
| Record rows, pair role selector, two-stage saved-baseline reason | screens/Assessments.tsx |
| Resource filters and side-by-side body/hash evidence | screens/Changes.tsx |
| Timeline and selected-state/frame inspection | screens/Journey.tsx |
| Evidence hero, metadata, headers, integrity and context | screens/Evidence.tsx |
| Signal fields, feedback, dialogs and actions | components/common.tsx, components/ui/button.tsx |
| New approved operational flows | components/TargetSetup.tsx, Monitoring.tsx, ReviewPanel.tsx |

The original mark and favicon are copied byte-for-byte from the approved Figma exports. Lucide 1.47.0 matches the design's glyph source. CSS implements Signal blue/night/lime/amber/coral semantic roles, 12px cards, 48px actions and responsive layout.
Typeface names reference Space Grotesk, Manrope and IBM Plex Mono with system fallbacks. No font binaries from the host are bundled, and no external font request occurs. Text metrics therefore require runtime review on the selected OS.
All record counts, byte sizes, hashes, roles, statuses and decisions come from the local API. Figma fixture values are not application defaults. Positive styling denotes a specific status such as artifact integrity or reached state, never a compliance score.
Baseline/candidate IDs, filter and selected evidence travel in the route. Native dialogs preserve trigger focus. Changes restores the selected row on return. Four primary destinations remain; Monitoring and Inbox are secondary views inside Assessments.
Static type/build checks do not establish keyboard, assistive-technology or viewport correctness. Verify 1440/1024/390, zoom, long URLs/hashes, empty/errors, expired session, partial evidence, dialog focus, review feedback and failed exports only in the subsequent authorized runtime phase.

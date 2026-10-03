# Current Signal design authority

Signal 03 supersedes the original warm/teal direction for 0.2.0. See [the design gallery](DESIGN.md), [implementation mapping](SIGNAL_IMPLEMENTATION.md) and [asset guide](../assets/signal/README.md). The interface uses original Signal CSS/tokens and existing Lucide/shadcn/Radix building blocks. Original brand and design-concept exports are included; the upstream Figma UI kit and font software are not redistributed. Runtime visual/accessibility verification remains pending.

## Historical v0.1.0 tooling record

# Design authority and tool adoption

Editorial Evidence Ledger is the original CEM direction: warm canvas, dark ink, restrained teal, evidence-first layout, descriptive status labels. The Changes/Evidence split defines the workbench. Four named screens remain stable across widths.

Research reviewed pinned Impeccable, shadcn/ui, tweakcn, UI UX Pro Max and Storybook sources. Only a small MIT shadcn Button adaptation is vendored into the app; original CSS/tokens and native form/dialog primitives provide the rest. No upstream admin template, CLI installer, external design skill runtime or global configuration was adopted. Storybook stories are authored; its runtime/build remains opt-in. See notices for exact source/license attribution.

Brand SVGs and diagrams were compiled with a standalone local sharp0.35.4 rasterizer, without a browser or CEM import. These are art assets, not proof of UI rendering quality. System fallback fonts are used; no installed font binary is in the export. Arabic text is supplied as natural editorial copy and alt text; artwork stays English.

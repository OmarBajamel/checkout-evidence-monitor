# Visual review protocol

After local TEST APPROVED, use the compiled UI with labelled synthetic records. Review Assessments, Journey, Changes and Evidence at 1440×900, 1024×768 and 390×844. The authored screenshot suite also captures partial records, incompatible profiles and missing bodies. Inspect every resulting image; an assertion pass alone does not establish visual quality.

Storybook source covers empty, loading, error, partial, incompatible, long text, unavailable body and modal states. Review them only after approval. Check keyboard order, visible focus, dialog autofocus/Escape/focus restoration, reduced motion, readable status text without reliance on color, overflow, evidence wrapping, and mobile Changes-to-Evidence back navigation with selection/filter preservation.

Save actual screenshot paths, viewport, fixture, source snapshot and review decisions in reports/screenshots/manifest.json and reports/VISUAL_REVIEW.md. Execution status is recorded in TESTING_STATUS.md; the protocol itself is not proof of a pass. Design concepts in public assets are labelled concepts.

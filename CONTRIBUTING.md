# Contributing

Thank you for helping make evidence review clearer and more reproducible. Issues and pull requests may be written in **English, Arabic or German**. Keep code identifiers, API contracts and canonical technical documentation in English; maintain corresponding Arabic and German guidance when its meaning changes.

## Start with a concrete problem

Check existing issues and [the roadmap](docs/ROADMAP.md). Describe the trigger, expected behavior, actual result and affected version/profile. Use synthetic examples. Security-sensitive reports belong in [the private reporting channel](SECURITY.md).

For a substantial feature, propose the scope and its evidence/privacy implications before implementation. Do not expand collection authority or weaken a failing control to make an example work.

## Prepare a change

1. Fork or create a local branch from the intended release; retain commit history.
2. Follow [Getting started](docs/GETTING_STARTED.md) using a project-local environment and the reviewed dependency locks.
3. Keep changes focused. Explain behavior, tradeoffs, verification and remaining limits in the PR.
4. Add meaningful assertions for changed behavior. Preserve failed/partial outcomes and source provenance.
5. Update relevant documentation, translations, schemas and release notes together.

## Verification

Formatting, linting, type checking and audited builds are distinct from running the application:

```powershell
.venv/Scripts/ruff check src/cem tools tests
Set-Location frontend
npm run typecheck
npm run build
Set-Location ..
```

Linux uses `.venv/bin/ruff`. Runtime tests, previews and collection require an explicit local session for the current source/profile; see [the runbook](docs/RUNBOOK.md). The public manual workflow has separate intent and commit inputs. Do not infer test success from an authored case or an available workflow. Do not add automatic push/PR/scheduled test or deployment hooks.

PILOT staging requires its own accepted boundary and named time-bounded scope. Never use an unrelated store as a test fixture.

## Language, accessibility and data

- Keep English, Arabic and German capability/status claims aligned. Translated documentation does not imply a translated application interface.
- Preserve keyboard access, names, focus, reduced motion, responsive layouts and explicit uncertainty; report what was actually checked.
- Never contribute credentials, customer evidence, browser profiles, host font binaries or private orchestration records.
- Retain licenses, ASVS attribution and visible concept labels. Dependency additions need reviewed provenance and lock updates.
- Use respectful, actionable discussion. No abusive or discriminatory content; maintainers may moderate contributions.
- Do not promise SLAs, certification, universal coverage, measured improvements or human-only authorship without evidence.

By contributing, you confirm you have the right to share your contribution under the project's applicable licensing terms.

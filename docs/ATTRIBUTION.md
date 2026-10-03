# Attribution and source use

Signal design concepts adapt the Material 3 Design Kit by Google. The project changes layout, colors, typography and icon placement; upstream component foundations retain CC BY 4.0 attribution under Figma's free Community terms. See [the full notice and source links](../THIRD_PARTY_NOTICES.md#signal-integration-september-2026). Original Signal brand illustrations remain MIT; composite concepts retain upstream rights.

Original code, UI composition, identity and editorial artwork: Omar Ba Jamel. The small shadcn Button adaptation retains its upstream MIT terms. Lucide/Radix/React and every installed locked dependency retain source notices in licenses/. The complete inventory is DEPENDENCIES.json; see THIRD_PARTY_NOTICES.md.

The Playwright-derived seccomp profile is Apache-2.0. ASVS-derived relationship data is CC-BY-SA-4.0 with exact version/source and modification notice. PCI/ISO proprietary text and insignia are not reproduced. Upstream research repositories were reviewed as references, not copied wholesale. No environment font binaries, third-party screenshots or customer material are distributed.

The pinned Playwright Dockerfile and dependency list were inspected to avoid assuming certutil was installed. Its separately pinned Ubuntu package is archive-inspected and extracted without maintainer hooks during a future authorized image build. References: https://github.com/microsoft/playwright-python/blob/v1.63.0/utils/docker/Dockerfile.noble and https://packages.ubuntu.com/noble/libnss3-tools . No image or browser was run to infer compatibility.

Licenses shown in the inventory describe upstream package terms; original MIT licensing does not override them. Preserve ASVS ShareAlike attribution with the derived data. The source export includes notices, not virtual environments, node_modules, browser installations or NSS binaries.

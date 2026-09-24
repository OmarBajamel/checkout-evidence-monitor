"""OBS-001–012: evidence-led, deterministic and explicit about unknowns."""

from .domain import Run, Finding, Comparison
from .mappings import relationships


def finding(
    rules,
    title,
    condition="MATCH",
    *,
    evidence=(),
    reason="",
    interpretation="",
    sufficient="SUFFICIENT",
    applicability="APPLICABLE",
    owner="Security reviewer",
    severity="INFO",
):
    mappings = []
    for rule in rules:
        for m in relationships(rule):
            if m not in mappings:
                mappings.append(m)
    return Finding(
        rule_ids=rules,
        title=title,
        condition=condition,
        applicability=applicability,
        evidence_sufficiency=sufficient,
        confidence="HIGH" if sufficient == "SUFFICIENT" else "LIMITED",
        severity=severity,
        reason_codes=[reason] if reason else [],
        evidence_ids=list(evidence),
        interpretation=interpretation,
        suggested_owner=owner,
        mappings=mappings,
    )


def evaluate(run: Run, comparison: Comparison | None = None) -> list[Finding]:
    out = []
    docs = [e for e in run.evidence if e.kind == "DOCUMENT" and e.response_observed]
    scripts = [e for e in run.evidence if e.kind == "SCRIPT"]
    out.append(
        finding(
            ["OBS-001"],
            "Observed security-relevant response headers",
            "MATCH" if docs else "NOT_RUN",
            evidence=[e.id for e in docs],
            sufficient="SUFFICIENT" if docs else "MISSING",
            reason="OBSERVED_RESPONSES_ONLY" if docs else "DOCUMENT_RESPONSE_MISSING",
            interpretation="Header inventory covers recorded responses only; absence is not a compliance verdict.",
        )
    )
    for e in docs:
        enforced = "content-security-policy" in e.headers
        report = "content-security-policy-report-only" in e.headers
        state = (
            "ENFORCED_HEADER_PRESENT" if enforced else ("REPORT_ONLY" if report else "NO_CSP_HEADER_OBSERVED")
        )
        out.append(
            finding(
                ["OBS-002"],
                "Content Security Policy: " + state,
                evidence=[e.id],
                reason=state,
                interpretation="Policy syntax and directive inventory are supporting evidence, not a bypass or policy-strength test.",
            )
        )
    if not docs:
        out.append(
            finding(
                ["OBS-002"],
                "CSP evidence unavailable",
                "NOT_RUN",
                sufficient="MISSING",
                reason="DOCUMENT_RESPONSE_MISSING",
            )
        )
    sessions = [c for c in run.cookies if c.role == "CONFIGURED_SESSION"]
    if not sessions:
        out.append(
            finding(
                ["OBS-003"],
                "Session cookie role not established",
                "INCONCLUSIVE",
                sufficient="MISSING",
                applicability="UNKNOWN",
                reason="COOKIE_ROLE_UNKNOWN",
                interpretation="Only explicitly configured synthetic session cookies are evaluated.",
            )
        )
    for c in sessions:
        missing = [
            name
            for name, present in (
                ("Secure", c.secure),
                ("HttpOnly", c.http_only),
                ("SameSite", c.same_site in ("Lax", "Strict", "None")),
            )
            if not present
        ]
        out.append(
            finding(
                ["OBS-003"],
                "Configured session cookie attribute review",
                "MATCH" if missing else "NO_MATCH",
                reason="ATTRIBUTES_MISSING" if missing else "ATTRIBUTES_OBSERVED",
                interpretation="Missing attributes: "
                + (", ".join(missing) or "none in this observation")
                + ". Cookie purpose and cross-site needs still require review.",
            )
        )
    insecure = [
        e
        for e in run.evidence
        if e.url_display.startswith("http://")
        and e.state in {d.state for d in docs if d.url_display.startswith("https://")}
    ]
    secure_docs = [d for d in docs if d.url_display.startswith("https://")]
    out.append(
        finding(
            ["OBS-004"],
            "Insecure resource context",
            "MATCH" if insecure else ("NO_MATCH" if secure_docs else "NOT_RUN"),
            evidence=[e.id for e in insecure],
            sufficient="SUFFICIENT" if secure_docs else "MISSING",
            applicability="APPLICABLE" if secure_docs else "UNKNOWN",
            reason="ATTEMPT_AND_RESPONSE_DISTINCT",
            interpretation="Delivery status is recorded separately; a blocked attempt is not delivered mixed content.",
        )
    )
    if comparison and comparison.eligibility == "COMPARABLE":
        for c in comparison.changes:
            if c.category != "SCRIPT" and c.kind == "CHANGED":
                out.append(
                    finding(
                        ["OBS-001" if c.category == "HEADERS" else "OBS-003"],
                        "Observed " + c.category.lower() + " differ",
                        reason=c.reason,
                        evidence=[x for x in (c.baseline_evidence_id, c.candidate_evidence_id) if x],
                        interpretation="Review the recorded context. Attribute changes do not establish compliance or intent.",
                    )
                )
            elif c.kind == "ADDED":
                rs = ["OBS-005", "OBS-008"] + (["OBS-007"] if c.new_origin else [])
                out.append(
                    finding(
                        rs,
                        "Newly observed script",
                        evidence=[c.candidate_evidence_id] if c.candidate_evidence_id else [],
                        reason=c.reason,
                        interpretation="New in this comparable window. Approval, ownership and maliciousness are unknown.",
                        owner="Store integration owner",
                        severity="REVIEW_NEEDED",
                    )
                )
            elif c.kind == "CHANGED":
                out.append(
                    finding(
                        ["OBS-006"],
                        "Captured script representation changed",
                        evidence=[x for x in (c.baseline_evidence_id, c.candidate_evidence_id) if x],
                        reason=c.reason,
                        interpretation="Comparable bytes differ. Legitimate dynamic output is possible; intent is unknown.",
                        owner="Frontend integration owner",
                        severity="REVIEW_NEEDED",
                    )
                )
            elif c.kind in ("AMBIGUOUS", "UNOBSERVABLE"):
                out.append(
                    finding(
                        ["OBS-012" if c.kind == "AMBIGUOUS" else "OBS-011"],
                        "Comparison evidence is incomplete",
                        "INCONCLUSIVE",
                        reason=c.reason,
                        sufficient="PARTIAL",
                        evidence=[x for x in (c.baseline_evidence_id, c.candidate_evidence_id) if x],
                        interpretation="Do not infer removal or unchanged security from unavailable evidence.",
                    )
                )
        incomplete = bool(run.limitation_codes) or any(
            c.kind in ("UNOBSERVABLE", "AMBIGUOUS") for c in comparison.changes
        )
        if not any(c.kind == "ADDED" for c in comparison.changes):
            out.append(
                finding(
                    ["OBS-005", "OBS-007"],
                    "Comparable script additions",
                    "INCONCLUSIVE" if incomplete or not scripts else "NO_MATCH",
                    sufficient="PARTIAL" if incomplete or not scripts else "SUFFICIENT",
                    reason="COMPARABLE_WINDOW_ONLY",
                    interpretation="This says nothing about maliciousness or unobserved states.",
                )
            )
        if not any(c.kind == "CHANGED" and c.category == "SCRIPT" for c in comparison.changes):
            out.append(
                finding(
                    ["OBS-006"],
                    "No comparable captured body change",
                    "INCONCLUSIVE" if incomplete or not scripts else "NO_MATCH",
                    sufficient="PARTIAL" if incomplete or not scripts else "SUFFICIENT",
                    reason="ELIGIBLE_BODIES_ONLY",
                )
            )
    else:
        for rule in ("OBS-005", "OBS-006", "OBS-007"):
            out.append(
                finding(
                    [rule],
                    "Comparable baseline required",
                    "NOT_RUN",
                    sufficient="MISSING",
                    reason="NO_COMPARABLE_BASELINE",
                )
            )
    out.append(
        finding(
            ["OBS-008"],
            "External script observation inventory",
            "MATCH" if scripts else "INCONCLUSIVE",
            evidence=[e.id for e in scripts],
            sufficient="SUFFICIENT" if scripts else "MISSING",
            interpretation="DOM reference, request and response are distinct. Execution was not measured; cross-origin does not establish ownership.",
        )
    )
    refs = [e for e in scripts if e.reference_observed]
    for e in refs:
        out.append(
            finding(
                ["OBS-009"],
                "Visible integrity metadata",
                "MATCH" if e.integrity_metadata else "NO_MATCH",
                evidence=[e.id],
                reason="INTEGRITY_ATTRIBUTE_PRESENT"
                if e.integrity_metadata
                else "NO_VISIBLE_INTEGRITY_ATTRIBUTE",
                interpretation="Visible metadata does not establish correct enforcement; absence does not rule out alternate integrity controls.",
            )
        )
    if not refs:
        out.append(
            finding(
                ["OBS-009"],
                "No script-element integrity evidence",
                "NOT_RUN",
                sufficient="MISSING",
                reason="DOM_REFERENCE_MISSING",
            )
        )
    blocked = [s for s in run.steps if s.status != "REACHED"]
    reached = any(s.state == "checkout" and s.status == "REACHED" for s in run.steps)
    out.append(
        finding(
            ["OBS-010"],
            "Journey coverage",
            "MATCH" if blocked or not reached else "NO_MATCH",
            reason="CHECKOUT_NOT_REACHED"
            if not reached
            else ("STEP_BLOCKED" if blocked else "DECLARED_STATES_REACHED"),
            sufficient="PARTIAL" if blocked or not reached else "SUFFICIENT",
            interpretation="Downstream checks require their declared state and evidence; no unsupported clean assessment.",
        )
    )
    out.append(
        finding(
            ["OBS-011"],
            "Collection limits and errors",
            "MATCH" if run.limitation_codes else "NO_MATCH",
            sufficient="PARTIAL" if run.limitation_codes else "SUFFICIENT",
            reason=";".join(run.limitation_codes) or "NO_RECORDED_LIMIT",
            interpretation="No recorded limit is not proof of complete execution visibility.",
        )
    )
    mismatch = comparison and comparison.eligibility != "COMPARABLE"
    out.append(
        finding(
            ["OBS-012"],
            "Profile comparability",
            "MATCH" if mismatch else ("NO_MATCH" if comparison else "NOT_RUN"),
            sufficient="MISSING" if not comparison else "SUFFICIENT",
            reason="PROFILE_MISMATCH" if mismatch else "PROFILE_CONTEXT",
            interpretation="Mismatching fields: " + ", ".join(comparison.mismatch_fields)
            if mismatch
            else "Only identical declared contexts qualify.",
        )
    )
    return out

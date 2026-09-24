"""Conservative comparison. Incomplete visits never prove a resource disappeared."""

from collections import defaultdict
from .domain import Run, Comparison, Change


def compare(baseline: Run, candidate: Run) -> Comparison:
    a, b = baseline.profile.model_dump(mode="json"), candidate.profile.model_dump(mode="json")
    mismatches = [key for key in a if a[key] != b[key]]
    if mismatches:
        return Comparison(
            baseline_id=baseline.id,
            candidate_id=candidate.id,
            eligibility="INCOMPATIBLE_PROFILE",
            mismatch_fields=mismatches,
        )
    result = Comparison(baseline_id=baseline.id, candidate_id=candidate.id, eligibility="COMPARABLE")
    ai, bi = defaultdict(list), defaultdict(list)
    for e in baseline.evidence:
        if e.kind == "SCRIPT":
            ai[e.identity or e.id].append(e)
    for e in candidate.evidence:
        if e.kind == "SCRIPT":
            bi[e.identity or e.id].append(e)
    origins = {e.origin for e in baseline.evidence if e.kind == "SCRIPT" and e.origin}
    for key in sorted(set(ai) | set(bi)):
        left, right = ai[key], bi[key]
        x = (right or left)[0]
        kw = dict(
            identity=key,
            url_display=x.url_display,
            state=x.state,
            baseline_evidence_id=left[0].id if left else None,
            candidate_evidence_id=right[0].id if right else None,
        )
        if len(left) > 1 or len(right) > 1 or not x.identity:
            result.changes.append(Change(kind="AMBIGUOUS", reason="MULTIPLE_OR_MISSING_IDENTITIES", **kw))
        elif not left:
            if x.state not in baseline.complete_states:
                result.changes.append(Change(kind="UNOBSERVABLE", reason="BASELINE_WINDOW_INCOMPLETE", **kw))
            else:
                result.changes.append(
                    Change(
                        kind="ADDED",
                        reason="NEWLY_OBSERVED_NOT_MALICIOUS",
                        new_origin=x.origin not in origins,
                        **kw,
                    )
                )
        elif not right:
            if x.state not in candidate.complete_states:
                result.changes.append(Change(kind="UNOBSERVABLE", reason="CANDIDATE_WINDOW_INCOMPLETE", **kw))
            else:
                result.changes.append(
                    Change(kind="NOT_OBSERVED", reason="NOT_OBSERVED_IN_COMPLETE_WINDOW", **kw)
                )
        else:
            y = left[0]
            if not x.body_sha256 or not y.body_sha256:
                result.changes.append(Change(kind="UNOBSERVABLE", reason="BODY_UNAVAILABLE", **kw))
            elif x.body_representation != y.body_representation:
                result.changes.append(Change(kind="AMBIGUOUS", reason="BODY_REPRESENTATION_MISMATCH", **kw))
            elif x.body_sha256 != y.body_sha256:
                result.changes.append(Change(kind="CHANGED", reason="CONTENT_DIFFERS_INTENT_UNKNOWN", **kw))
    # Only compare document headers in complete matching state/origin windows.
    ad, bd = defaultdict(list), defaultdict(list)
    for run, index in ((baseline, ad), (candidate, bd)):
        for e in run.evidence:
            if e.kind == "DOCUMENT" and e.response_observed:
                index[(e.state, e.origin, e.frame_id)].append(e)
    for key in sorted(set(ad) & set(bd)):
        left, right = ad[key], bd[key]
        if len(left) != 1 or len(right) != 1:
            continue
        a_doc, b_doc = left[0], right[0]
        if a_doc.headers != b_doc.headers:
            complete = key[0] in baseline.complete_states and key[0] in candidate.complete_states
            result.changes.append(
                Change(
                    category="HEADERS",
                    kind="CHANGED" if complete else "UNOBSERVABLE",
                    identity=b_doc.identity,
                    url_display=b_doc.url_display,
                    state=key[0],
                    baseline_evidence_id=a_doc.id,
                    candidate_evidence_id=b_doc.id,
                    reason="OBSERVED_HEADERS_DIFFER" if complete else "HEADER_WINDOW_INCOMPLETE",
                )
            )

    def cookie_rows(run):
        return {(c.name, c.domain, c.path): (c.secure, c.http_only, c.same_site, c.role) for c in run.cookies}

    ca, cb = cookie_rows(baseline), cookie_rows(candidate)
    if ca != cb:
        complete = (
            bool(baseline.complete_states)
            and baseline.complete_states == candidate.complete_states
            and not (baseline.limitation_codes or candidate.limitation_codes)
        )
        result.changes.append(
            Change(
                category="COOKIE",
                kind="CHANGED" if complete else "UNOBSERVABLE",
                identity="cookie-attributes",
                url_display="Cookie attribute inventory",
                state="run",
                reason="COOKIE_ATTRIBUTES_DIFFER_VALUES_NOT_RETAINED"
                if complete
                else "COOKIE_WINDOW_INCOMPLETE",
            )
        )
    return result

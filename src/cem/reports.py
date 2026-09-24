"""Offline reports: no remote resources, executable content or formula cells."""

from io import StringIO
import csv
import json
from jinja2 import Environment, BaseLoader, select_autoescape
from .domain import Run, Comparison, MAX_IMPORT
from .rules import evaluate
from .errors import CEMError

HTML = """<!doctype html><html lang="en"><meta charset="utf-8"><meta http-equiv="Content-Security-Policy" content="default-src 'none'; style-src 'unsafe-inline'; base-uri 'none'; form-action 'none'"><meta name="referrer" content="no-referrer"><title>Checkout evidence report</title>
<style>body{font:16px/1.55 system-ui,sans-serif;color:#182b2c;background:#f7f5f0;max-width:1050px;margin:40px auto;padding:24px}h1{font-size:30px}article,section{border-top:1px solid #6e8380;padding:20px 0}code,pre{white-space:pre-wrap;overflow-wrap:anywhere}dt{font-weight:600}table{border-collapse:collapse;width:100%}td,th{padding:8px;border-bottom:1px solid #d6deda;text-align:left}a{color:#12665e}</style>
<h1>Checkout Evidence Monitor</h1><p>Offline evidence report · {{run.label}}</p>
<p><strong>{{run.status}}</strong> · {{run.provenance}} · {{run.id}}</p>
<p>Evidence supports a bounded observation, not compliance, certification, maliciousness or proof that a script executed.</p>
<section><h2>Coverage and context</h2><p>Started {{run.started_at}} · ended {{run.ended_at or 'not recorded'}}</p><p>Complete observed windows: {{run.complete_states|join(', ') or 'none'}}</p><p>Limitations: {{run.limitation_codes|join(', ') or 'No recorded cap; visibility remains bounded'}}</p><pre>{{profile}}</pre></section>
{% if comparison %}<section><h2>Comparison</h2><p>{{comparison.eligibility}}</p><p>{{comparison.mismatch_fields|join(', ')}}</p>{% for c in comparison.changes %}<p>{{c.kind}}: {{c.url_display}} — {{c.reason}}</p>{% endfor %}</section>{% endif %}
<section><h2>Observations</h2>{% for f in findings %}<article><h3>{{f.rule_ids|join(' / ')}} · {{f.title}}</h3><p>{{f.condition}} · applicability {{f.applicability}} · evidence {{f.evidence_sufficiency}} · confidence {{f.confidence}}</p><p>{{f.interpretation}}</p><p>Suggested owner: {{f.suggested_owner}}</p>{% for eid in f.evidence_ids %}<a href="#e-{{eid}}">Evidence {{eid}}</a> {% endfor %}{% for m in f.mappings %}<p>{{m.standard}} {{m.id}} — {{m.relationship}}. {{m.limitation}} <a href="{{m.url}}">Official source (external)</a></p>{% endfor %}</article>{% endfor %}</section>
<section><h2>Sanitized evidence</h2>{% for e in run.evidence %}<article id="e-{{e.id}}"><h3>{{e.kind}} · {{e.state}}</h3><p>{{e.url_display}}</p><p>Reference {{e.reference_observed}} · request {{e.request_observed}} · response {{e.response_observed}} · execution NOT_OBSERVED</p><p>Body: {{e.body_sha256 or e.body_reason}} · {{e.body_representation or 'unavailable'}}</p><pre>{{e.headers|tojson(indent=2)}}</pre></article>{% endfor %}</section></html>"""


def cell(value):
    s = str(value if value is not None else "")
    return (
        "'" + s
        if s.lstrip(" \t\r\n").startswith(("=", "+", "-", "@")) or s.startswith(("\t", "\r", "\n"))
        else s
    )


def render(run: Run, format: str, comparison: Comparison | None = None) -> tuple[bytes, str, str]:
    findings = evaluate(run, comparison)
    if format == "json":
        raw = json.dumps(
            {
                "schema_version": "1.0",
                "run": run.model_dump(mode="json"),
                "comparison": comparison.model_dump(mode="json") if comparison else None,
                "findings": [f.model_dump() for f in findings],
                "notice": "Supporting evidence only; not a compliance verdict.",
            },
            indent=2,
        ).encode()
        mime = "application/json"
    elif format == "csv":
        output = StringIO(newline="")
        w = csv.writer(output)
        w.writerow(
            [
                "run_id",
                "rule_ids",
                "condition",
                "applicability",
                "evidence_sufficiency",
                "confidence",
                "reason",
                "interpretation",
                "evidence_ids",
            ]
        )
        for f in findings:
            w.writerow(
                [
                    cell(v)
                    for v in [
                        run.id,
                        ";".join(f.rule_ids),
                        f.condition,
                        f.applicability,
                        f.evidence_sufficiency,
                        f.confidence,
                        ";".join(f.reason_codes),
                        f.interpretation,
                        ";".join(f.evidence_ids),
                    ]
                ]
            )
        raw = output.getvalue().encode("utf-8-sig")
        mime = "text/csv"
    elif format == "html":
        env = Environment(loader=BaseLoader(), autoescape=select_autoescape(default=True))
        raw = (
            env.from_string(HTML)
            .render(
                run=run,
                comparison=comparison,
                findings=findings,
                profile=json.dumps(run.profile.model_dump(mode="json"), indent=2),
            )
            .encode()
        )
        mime = "text/html"
    else:
        raise CEMError("INVALID_INPUT", "Export format must be html, json or csv.")
    if len(raw) > MAX_IMPORT:
        raise CEMError("ARTIFACT_LIMIT", "Export exceeds its 50 MiB bound.")
    return raw, mime, f"cem-{run.id}.{format}"

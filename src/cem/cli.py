"""Explicit entry points only. No services start on import, install or build."""

from pathlib import Path
import json
import os
import typer
from .errors import CEMError
from .storage import Store, reject_symlink_chain
from .phase import require_runtime
from .config import load_job
from .comparison import compare
from .rules import evaluate
from .reports import render

app = typer.Typer(add_completion=False, no_args_is_help=True, pretty_exceptions_enable=False)


def store() -> Store:
    root = Path.cwd().resolve()
    data = Path(os.environ.get("CEM_DATA_DIR", str(root / ".cem-data"))).resolve()
    if not data.is_relative_to(root):
        raise CEMError("PATH_DENIED", "CEM_DATA_DIR must remain within this project directory.")
    reject_symlink_chain(data)
    return Store(data)


def output(obj):
    typer.echo(json.dumps(obj, ensure_ascii=True, indent=2, default=str))


@app.command("import")
def import_record(path: Path):
    output(store().import_file(path).model_dump(mode="json"))


@app.command("list")
def list_records(limit: int = 50, offset: int = 0, q: str = ""):
    output(store().list_runs(limit, offset, q))


@app.command("show")
def show(run_id: str):
    output(store().get(run_id).model_dump(mode="json"))


@app.command("compare")
def compare_runs(baseline: str, candidate: str):
    s = store()
    a, b = s.verified_get(baseline), s.verified_get(candidate)
    result = compare(a, b)
    result.findings = evaluate(b, result)
    output(result.model_dump(mode="json"))


@app.command("baseline")
def select_baseline(run_id: str, reason: str = typer.Option(...)):
    output(store().baseline(run_id, reason))


@app.command("integrity")
def check_integrity(run_id: str):
    output(store().integrity(run_id))


@app.command("recovery")
def recovery():
    output(store().recovery_status())


@app.command("report")
def report(run_id: str, format: str = typer.Option("html"), destination: Path = typer.Option(...)):
    s = store()
    raw, _, _ = render(s.verified_get(run_id), format)
    reject_symlink_chain(destination)
    if destination.exists():
        raise CEMError("FILE_EXISTS", "Choose a new report destination; existing files are preserved.")
    if not destination.resolve().is_relative_to(Path.cwd().resolve()):
        raise CEMError("PATH_DENIED", "Report output must remain within this project.")
    destination.parent.mkdir(parents=True, exist_ok=True)
    fd = os.open(destination, os.O_CREAT | os.O_EXCL | os.O_WRONLY, 0o600)
    with os.fdopen(fd, "wb") as f:
        f.write(raw)
    output(
        {
            "file": str(destination),
            "bytes": len(raw),
            "notice": "Sanitized offline report; not a compliance verdict.",
        }
    )


@app.command("retention")
def retention(run_ids: list[str], confirmation: str = typer.Option("")):
    s = store()
    output(s.retention_apply(run_ids, confirmation) if confirmation else s.retention_preview(run_ids))


@app.command("collect")
def collect_job(job_file: Path, profile: str = "LAB"):
    if profile != "LAB":
        raise CEMError(
            "PUBLIC_PROFILE_NOT_SUPPORTED", "Only the isolated synthetic LAB profile is supported."
        )
    from .lab_wrapper import run_lab

    job = load_job(job_file)
    output(run_lab(job, store(), Path.cwd()).model_dump(mode="json"))


@app.command("ui")
def ui(port: int = 8760, demo: bool = False):
    from .api import Session, create_app
    import uvicorn

    if not 1024 <= port <= 65535:
        raise CEMError("INVALID_INPUT", "Choose an unprivileged local port.")
    s = store()
    if demo:
        from .demo import demo_store

        s = demo_store(s.root.parent / ".cem-demo")
    session = Session()
    # Owner-facing terminal only. Uvicorn access/error logging is disabled; fragment is never in a URL query.
    typer.echo(
        f"Local bootstrap (expires in 60 seconds): http://127.0.0.1:{port}/#bootstrap={session.bootstrap}"
    )
    uvicorn.run(
        create_app(s, session, port),
        host="127.0.0.1",
        port=port,
        access_log=False,
        log_config=None,
        log_level="critical",
        proxy_headers=False,
    )


def main():
    try:
        require_runtime(Path.cwd())
        app()
    except CEMError as exc:
        typer.echo(f"{exc.code}: {exc.message}", err=True)
        raise SystemExit(3) from None


if __name__ == "__main__":
    main()

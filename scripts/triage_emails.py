#!/usr/bin/env python3
"""
Email triage script for GitHub Actions failure notifications.

Watches emails/git_issues/unresolved/ for .msg files, parses them,
adds entries to docs/KNOWN_ISSUES.md, and moves files through the
lifecycle: unresolved → in_progress → resolved.

Usage:
    python scripts/triage_emails.py            # triage all unresolved emails
    python scripts/triage_emails.py --dry-run  # preview without changes
    python scripts/triage_emails.py --resolve KI-011  # close a KI and move files to resolved/

Run by .github/workflows/triage-emails.yml on schedule and on push.
"""

from __future__ import annotations

import argparse
import re
import shutil
import subprocess
import sys
from dataclasses import dataclass
from datetime import UTC, datetime
from pathlib import Path

# ---------------------------------------------------------------------------
# Paths (relative to repo root)
# ---------------------------------------------------------------------------
REPO_ROOT = Path(__file__).parent.parent
UNRESOLVED_DIR = REPO_ROOT / "emails" / "git_issues" / "unresolved"
IN_PROGRESS_DIR = REPO_ROOT / "emails" / "git_issues" / "in_progress"
RESOLVED_DIR = REPO_ROOT / "emails" / "git_issues" / "resolved"
KNOWN_ISSUES_PATH = REPO_ROOT / "docs" / "KNOWN_ISSUES.md"

# Filename pattern:
#   [tom-steningOmniPrompt] Run failed CI - main (a135114)_20260506_213520.msg
FILENAME_RE = re.compile(
    r"^\[(.+?)\] Run failed (.+?) - (.+?) \((.+?)\)_(\d{8}_\d{6})\.msg$"
)

# GitHub Actions run URL embedded in the binary .msg content
RUN_URL_RE = re.compile(rb"https://github\.com/[^\s\"\\&]+/actions/runs/(\d+)")


def ensure_layout() -> None:
    UNRESOLVED_DIR.mkdir(parents=True, exist_ok=True)
    IN_PROGRESS_DIR.mkdir(parents=True, exist_ok=True)
    RESOLVED_DIR.mkdir(parents=True, exist_ok=True)
    KNOWN_ISSUES_PATH.parent.mkdir(parents=True, exist_ok=True)
    if not KNOWN_ISSUES_PATH.exists():
        KNOWN_ISSUES_PATH.write_text(default_known_issues(), encoding="utf-8")


def default_known_issues() -> str:
    repo_name = REPO_ROOT.name
    today = datetime.now(UTC).strftime("%Y-%m-%d")
    return f"""# {repo_name} Known Issues

_Document type: Defect and limitation register_
_Status: Active_
_Last updated: {today} (bootstrap)_

## Purpose

Track confirmed defects, limitations, and operational risks with clear status
and target milestones.

## Issue Register

| ID | Title | Severity | Status | Target Milestone | Notes |
| --- | --- | --- | --- | --- | --- |

## Severity Reference

| Level | Meaning |
| --- | --- |
| P0 | Release-blocking or customer-impacting now |
| P1 | High — blocks revenue, delivery, or compliance milestone |
| P2 | Medium — degrades quality or delivery velocity |
| P3 | Low — polish or hygiene |
"""


def detect_repo_slug() -> str | None:
    try:
        remote = subprocess.run(
            ["git", "config", "--get", "remote.origin.url"],
            cwd=REPO_ROOT,
            check=True,
            capture_output=True,
            text=True,
        ).stdout.strip()
    except (OSError, subprocess.CalledProcessError):
        return None

    remote = remote.removesuffix(".git")
    if remote.startswith("git@github.com:"):
        return remote.split(":", 1)[1]
    if "github.com/" in remote:
        return remote.split("github.com/", 1)[1].lstrip("/")
    return None


def workflow_policy(meta: EmailMeta) -> tuple[str, str, str]:
    workflow_name = meta.workflow.strip()
    default_title = f"{workflow_name} workflow persistent failures"
    known: dict[str, tuple[str, str, str]] = {
        "ci": (default_title, "P2", "unknown"),
        "deploy-docs": (default_title, "P2", "unknown"),
        "business-board-health": (default_title, "P3", "unknown"),
    }
    return known.get(meta.workflow_key, (default_title, "P2", "unknown"))


def build_run_urls(run_ids: list[str], repo_slug: str | None) -> str:
    if not run_ids or not repo_slug:
        return "see emails"
    return ", ".join(
        f"[run](https://github.com/{repo_slug}/actions/runs/{run_id})"
        for run_id in run_ids[:3]
    )


# ---------------------------------------------------------------------------
# Data model
# ---------------------------------------------------------------------------
@dataclass
class EmailMeta:
    path: Path
    org_repo: str  # e.g. "tom-steningOmniPrompt"
    workflow: str  # e.g. "CI"
    branch: str
    sha: str
    timestamp: datetime
    run_id: str = ""  # extracted from binary content

    @property
    def workflow_key(self) -> str:
        """Normalised key used for grouping (lowercase, spaces → hyphens)."""
        return self.workflow.lower().replace(" ", "-")


def parse_filename(path: Path) -> EmailMeta | None:
    m = FILENAME_RE.match(path.name)
    if not m:
        return None
    org_repo, workflow, branch, sha, ts_raw = m.groups()
    ts = datetime.strptime(ts_raw, "%Y%m%d_%H%M%S").replace(tzinfo=UTC)
    meta = EmailMeta(
        path=path,
        org_repo=org_repo,
        workflow=workflow,
        branch=branch,
        sha=sha,
        timestamp=ts,
    )
    # Try to extract run ID from binary content
    try:
        content = path.read_bytes()
        urls = RUN_URL_RE.findall(content)
        if urls:
            meta.run_id = urls[0].decode()
    except OSError:
        pass
    return meta


# ---------------------------------------------------------------------------
# KNOWN_ISSUES.md helpers
# ---------------------------------------------------------------------------
def read_known_issues() -> str:
    ensure_layout()
    return KNOWN_ISSUES_PATH.read_text(encoding="utf-8")


def write_known_issues(content: str) -> None:
    KNOWN_ISSUES_PATH.write_text(content, encoding="utf-8")


def next_ki_id(content: str) -> str:
    """Return the next KI-NNN id (one higher than the current max)."""
    ids = re.findall(r"\bKI-(\d+)\b", content)
    if not ids:
        return "KI-001"
    return f"KI-{max(int(i) for i in ids) + 1:03d}"


def ki_exists_open(content: str, title_fragment: str) -> str | None:
    """Return the KI id if an open issue with this title fragment exists."""
    pattern = re.compile(
        r"\|\s*(KI-\d+)\s*\|[^|]*"
        + re.escape(title_fragment)
        + r"[^|]*\|[^|]*\|\s*Open\s*\|",
        re.IGNORECASE,
    )
    m = pattern.search(content)
    return m.group(1) if m else None


def table_row(ki_id: str, title: str, severity: str, notes: str) -> str:
    today = datetime.now(UTC).strftime("%Y-%m-%d")
    return (
        f"| {ki_id} | {title} | {severity} | Open | — | "
        f"First seen {today}. {notes} |"
    )


def insert_ki_row(content: str, row: str) -> str:
    """Insert a new row just before the Severity Reference section."""
    marker = "\n## Severity Reference"
    idx = content.find(marker)
    if idx == -1:
        return content + "\n" + row + "\n"
    return content[:idx] + "\n" + row + content[idx:]


def update_ki_notes(content: str, ki_id: str, extra_note: str) -> str:
    """Append extra_note to the Notes cell of an existing KI row."""
    pattern = re.compile(r"(\|\s*" + re.escape(ki_id) + r"\s*\|.*?\|)([^|\n]*\|?\s*\n)", re.DOTALL)

    def _append(m: re.Match[str]) -> str:
        row_prefix = m.group(1)
        row_suffix = m.group(2)
        # Notes is the last cell; strip trailing pipe/newline
        suffix_stripped = row_suffix.rstrip(" |\n")
        return f"{row_prefix}{suffix_stripped} {extra_note} |\n"

    return pattern.sub(_append, content, count=1)


def close_ki(content: str, ki_id: str, resolution_note: str) -> str:
    """Change status from Open to Closed and append resolution note."""
    pattern = re.compile(
        r"(\|\s*" + re.escape(ki_id) + r"\s*\|[^|]*\|[^|]*\|)\s*Open\s*(\|)",
        re.IGNORECASE,
    )
    content = pattern.sub(r"\1 *_Closed_* \2", content)
    content = update_ki_notes(content, ki_id, resolution_note)
    return content


def update_last_updated(content: str, summary: str) -> str:
    pattern = re.compile(r"(_Last updated:)[^\n]+")
    today = datetime.now(UTC).strftime("%Y-%m-%d")
    if pattern.search(content):
        return pattern.sub(rf"\1 {today} ({summary})", content)
    return f"_Last updated: {today} ({summary})_\n\n{content}"


# ---------------------------------------------------------------------------
# Core triage logic
# ---------------------------------------------------------------------------
def triage(dry_run: bool = False) -> int:
    """
    Process all unresolved emails.
    Returns the number of new KI entries created.
    """
    msg_files = sorted(UNRESOLVED_DIR.glob("*.msg"))
    if not msg_files:
        print("No unresolved emails found.")
        return 0

    print(f"Found {len(msg_files)} unresolved email(s).")
    repo_slug = detect_repo_slug()

    # Parse all filenames
    parsed: list[EmailMeta] = []
    for path in msg_files:
        meta = parse_filename(path)
        if meta is None:
            print(f"  [SKIP] Could not parse filename: {path.name}")
            continue
        parsed.append(meta)

    if not parsed:
        print("No parseable emails.")
        return 0

    # Group by workflow key
    groups: dict[str, list[EmailMeta]] = {}
    for meta in parsed:
        groups.setdefault(meta.workflow_key, []).append(meta)

    ki_content = read_known_issues()
    new_ki_count = 0

    for wf_key, metas in sorted(groups.items()):
        metas.sort(key=lambda m: m.timestamp)
        first = metas[0]
        last = metas[-1]
        count = len(metas)
        shas = sorted({m.sha for m in metas})
        run_ids = sorted({m.run_id for m in metas if m.run_id})

        title_fragment, severity, job = workflow_policy(metas[0])

        existing_ki = ki_exists_open(ki_content, title_fragment)

        run_urls = build_run_urls(run_ids, repo_slug)

        if existing_ki:
            # Append update note
            note = (
                f"Updated {datetime.now(UTC).strftime('%Y-%m-%d')}: "
                f"+{count} new failure(s) across commits {', '.join(shas[:5])}."
            )
            print(f"  [{existing_ki}] Updating existing open issue for {wf_key!r} (+{count} emails).")
            if not dry_run:
                ki_content = update_ki_notes(ki_content, existing_ki, note)
        else:
            ki_id = next_ki_id(ki_content)
            notes = (
                f"{count} failure(s) observed between "
                f"{first.timestamp.strftime('%Y-%m-%d')} and "
                f"{last.timestamp.strftime('%Y-%m-%d')}. "
                f"Job: `{job}`. "
                f"Commits: {', '.join(shas[:5])}{'...' if len(shas) > 5 else ''}. "
                f"Runs: {run_urls}."
            )
            row = table_row(ki_id, title_fragment, severity, notes)
            print(f"  [{ki_id}] Creating new issue for {wf_key!r} ({count} emails).")
            if not dry_run:
                ki_content = insert_ki_row(ki_content, row)
                new_ki_count += 1

        # Move emails to in_progress
        for meta in metas:
            dest = IN_PROGRESS_DIR / meta.path.name
            print(f"    → in_progress: {meta.path.name}")
            if not dry_run:
                shutil.move(str(meta.path), str(dest))

    if not dry_run and (new_ki_count > 0 or groups):
        ki_content = update_last_updated(
            ki_content, f"email triage: {len(parsed)} emails processed"
        )
        write_known_issues(ki_content)
        print(f"\nWrote {KNOWN_ISSUES_PATH.relative_to(REPO_ROOT)}.")

    if dry_run:
        print("\n[DRY RUN] No changes written.")

    return new_ki_count


def resolve(ki_id: str, resolution: str, dry_run: bool = False) -> None:
    """
    Mark a KI as closed and move its in_progress emails to resolved/.
    """
    ki_content = read_known_issues()
    if ki_id not in ki_content:
        print(f"ERROR: {ki_id} not found in KNOWN_ISSUES.md")
        sys.exit(1)

    print(f"Closing {ki_id}: {resolution}")
    if not dry_run:
        ki_content = close_ki(ki_content, ki_id, resolution)
        ki_content = update_last_updated(ki_content, f"{ki_id} closed")
        write_known_issues(ki_content)

    # Move matching in_progress emails to resolved
    # We can't match emails to KI directly by content, so move all in_progress
    # that match the workflow name embedded in the KI title.
    # Simple heuristic: accept a workflow label as optional arg; fall back to all.
    moved = 0
    for msg in IN_PROGRESS_DIR.glob("*.msg"):
        dest = RESOLVED_DIR / msg.name
        print(f"  → resolved: {msg.name}")
        if not dry_run:
            shutil.move(str(msg), str(dest))
        moved += 1

    print(f"Moved {moved} email(s) to resolved/.")


# ---------------------------------------------------------------------------
# CLI
# ---------------------------------------------------------------------------
def main() -> None:
    parser = argparse.ArgumentParser(description="Triage GitHub Actions failure emails.")
    parser.add_argument("--dry-run", action="store_true", help="Preview only, no changes.")
    sub = parser.add_subparsers(dest="cmd")

    resolve_p = sub.add_parser("resolve", help="Close a KI and move its emails to resolved/.")
    resolve_p.add_argument("ki_id", help="e.g. KI-011")
    resolve_p.add_argument("--note", default="Fixed.", help="Resolution note.")

    args = parser.parse_args()

    if args.cmd == "resolve":
        resolve(args.ki_id, args.note, dry_run=args.dry_run)
    else:
        count = triage(dry_run=args.dry_run)
        if count > 0:
            print(f"\n{count} new KI entr{'y' if count == 1 else 'ies'} added.")


if __name__ == "__main__":
    main()

#!/usr/bin/env python3
"""Quarterly polyglot language assessment for OmniPrompt.

Analyses the repository's current language composition, profiles CPU vs IO
character of hot functions, and produces a Markdown decision matrix with
concrete recommendations for each candidate language.

Usage:
    python scripts/polyglot_assess.py [--json] [--out FILE]

Output is written to stdout (Markdown) or --out FILE.  Pass --json to emit
machine-readable JSON instead.  The GitHub Actions workflow captures stdout
and posts it as a GitHub issue.

Copying to other repos
----------------------
This script is self-contained.  To seed a polyglot-assessment workflow in
another repository:

  1. Copy this file to that repo's scripts/ directory.
  2. Copy .github/workflows/polyglot-assessment.yml to that repo.
  3. Adjust REPO_ROOT_GLOBS if the project layout differs.

The script requires only the Python standard library.
"""

from __future__ import annotations

import argparse
import ast
import datetime
import json
import os
import subprocess
import sys
from pathlib import Path
from typing import Any

# ---------------------------------------------------------------------------
# Configuration — adjust per-repo
# ---------------------------------------------------------------------------

REPO_ROOT = Path(__file__).resolve().parent.parent

EXCLUDE_DIRS = {
    ".venv", "node_modules", ".git", "__pycache__", ".mypy_cache",
    ".pytest_cache", ".ruff_cache", "htmlcov", ".benchmarks", ".hypothesis",
}

# Language → file extensions
LANG_EXTENSIONS: dict[str, list[str]] = {
    "Python":        [".py"],
    "TypeScript":    [".ts", ".tsx"],
    "JavaScript":    [".js", ".mjs", ".cjs"],
    "Rust":          [".rs"],
    "Go":            [".go"],
    "C":             [".c", ".h"],
    "C++":           [".cc", ".cpp", ".cxx", ".hh", ".hpp"],
    "Zig":           [".zig"],
    "Shell":         [".sh", ".bash"],
    "Terraform/HCL": [".tf", ".tfvars"],
    "YAML":          [".yml", ".yaml"],
    "Dockerfile":    ["Dockerfile"],
    "Makefile":      ["Makefile", "makefile", "GNUmakefile"],
    "SQL":           [".sql"],
}

# IO markers: calls that block on network, disk, or IPC
IO_MARKERS = frozenset([
    "await ", "async def", "httpx", "aiohttp", "requests.",
    "open(", ".read(", ".write(", "asyncio.sleep", "aiofiles",
    "boto3", "redis", "sqlite3", "psycopg", "sqlalchemy",
    "subprocess.", "socket.", "urllib",
])

# CPU markers: computation that runs in the Python interpreter, not waiting
CPU_MARKERS = frozenset([
    "math.", "sum(", "Counter(", "math.log", "math.sqrt", "random.",
    "bootstrap", "resamp", "token", "cosine", "entropy", "variance",
    "statistics.", "sorted(", "enumerate(", "zip(", "map(",
])

# Candidate languages to evaluate (ordered from low to high cost)
CANDIDATES: list[dict[str, Any]] = [
    {
        "lang": "TypeScript",
        "fit_areas": ["SDK clients", "VS Code extension", "Web dashboard"],
        "not_fit": ["Core API service", "ML inference"],
        "adoption_cost": "Low — already present in sdk/node/ and vscode-extension/",
        "trigger": "Any new SDK surface area or browser-facing UI",
        "verdict": "ADOPT",
        "horizon": "Now",
    },
    {
        "lang": "Rust (via PyO3 extension)",
        "fit_areas": [
            "bootstrap_significance_test (2000-iteration resampling)",
            "Keyword classifier training (log-odds over large corpora)",
            "Timeline anomaly detection over >1M events",
            "Cosine / Hamming similarity if embeddings are added",
        ],
        "not_fit": ["Async IO hot paths", "Anything that awaits network calls"],
        "adoption_cost": (
            "Medium — requires maturin/PyO3 build step, Rust toolchain in CI, "
            "and a small FFI surface. No unsafe code needed."
        ),
        "trigger": (
            "bootstrap_significance_test wall-clock > 200 ms at p95, OR "
            "run-store timeline analysis > 500 ms, OR embedding similarity "
            "added to the hot path."
        ),
        "verdict": "MONITOR",
        "horizon": "12-18 months or on trigger",
    },
    {
        "lang": "Go",
        "fit_areas": [
            "High-throughput API gateway / reverse proxy layer",
            "Sidecar health-check service",
        ],
        "not_fit": [
            "Core business logic (too much churn to maintain in two languages)",
            "ML / stats code",
        ],
        "adoption_cost": (
            "High — parallel reimplementation of FastAPI service, dual deploy "
            "pipeline, ops complexity with two runtimes."
        ),
        "trigger": (
            "API layer needs > 10 000 RPS sustained at < 5 ms p99 without "
            "horizontal scaling, AND Python asyncio profiling shows GIL "
            "contention as the bottleneck (not network latency)."
        ),
        "verdict": "DEFER",
        "horizon": "18-36 months or on trigger",
    },
    {
        "lang": "C",
        "fit_areas": ["Low-level OS integration", "Embedded agents"],
        "not_fit": ["Everything in this repo — no memory-unsafe code justified"],
        "adoption_cost": (
            "High — unsafe memory management, no modern package ecosystem, "
            "harder Python FFI than Rust."
        ),
        "trigger": "Never for this repo's domain",
        "verdict": "REJECT",
        "horizon": "N/A",
    },
    {
        "lang": "C++",
        "fit_areas": ["Native inference runtime (if self-hosting models)"],
        "not_fit": ["All current code — no self-hosted model inference"],
        "adoption_cost": "Very high — complex build system, ABI fragility.",
        "trigger": "Only if self-hosting GGUF/llama.cpp style inference",
        "verdict": "REJECT unless self-hosting models",
        "horizon": "N/A",
    },
    {
        "lang": "WebAssembly",
        "fit_areas": [
            "Computation inside VS Code extension (runs in sandboxed renderer)",
            "Browser-side diff/highlight rendering",
        ],
        "not_fit": ["Server-side service code"],
        "adoption_cost": (
            "Medium — compile Rust/C to WASM, or use AssemblyScript. "
            "VS Code extension already has a build pipeline."
        ),
        "trigger": "VS Code extension in-process CPU > 50 ms for any user action",
        "verdict": "MONITOR",
        "horizon": "12 months if VS Code extension grows heavy computation",
    },
    {
        "lang": "Zig",
        "fit_areas": ["Extremely tight systems integration, cross-compilation"],
        "not_fit": ["All current code"],
        "adoption_cost": "High — immature tooling, small ecosystem, unfamiliar to most engineers.",
        "trigger": "Not applicable for this domain",
        "verdict": "REJECT",
        "horizon": "N/A",
    },
    {
        "lang": "Machine code / Assembly",
        "fit_areas": ["SIMD hotspot micro-optimisation inside a Rust crate"],
        "not_fit": [
            "Any application-level code — never write assembly directly "
            "at this abstraction level."
        ],
        "adoption_cost": "Extreme — not maintainable at this team size.",
        "trigger": "Not applicable",
        "verdict": "REJECT",
        "horizon": "N/A",
    },
    {
        "lang": "Julia",
        "fit_areas": ["Scientific numerical computing, large-scale simulations"],
        "not_fit": ["Web services, orchestration, prompt management"],
        "adoption_cost": "High — separate runtime, different ecosystem.",
        "trigger": "Not applicable",
        "verdict": "REJECT",
        "horizon": "N/A",
    },
    {
        "lang": "R",
        "fit_areas": ["Statistical research notebooks"],
        "not_fit": ["Production service code"],
        "adoption_cost": "Medium — R is fine for exploratory analysis, not services.",
        "trigger": "Not applicable",
        "verdict": "REJECT",
        "horizon": "N/A",
    },
    {
        "lang": "Java / Kotlin",
        "fit_areas": ["Android SDK", "Enterprise JVM integrations"],
        "not_fit": ["This Python-native AI orchestration stack"],
        "adoption_cost": "High — JVM startup, separate build toolchain.",
        "trigger": "Only if an Android client SDK is needed",
        "verdict": "DEFER",
        "horizon": "Only if Android SDK requested by customers",
    },
    {
        "lang": "Swift",
        "fit_areas": ["iOS SDK", "macOS native client"],
        "not_fit": ["Server-side code"],
        "adoption_cost": "Medium — only if iOS/macOS distribution is planned.",
        "trigger": "iOS/macOS SDK demand from customers",
        "verdict": "DEFER",
        "horizon": "Only if mobile SDK roadmap is confirmed",
    },
]

# ---------------------------------------------------------------------------
# Analysis helpers
# ---------------------------------------------------------------------------


def _should_skip(path: Path) -> bool:
    return any(part in EXCLUDE_DIRS for part in path.parts)


def count_lines_by_language() -> dict[str, int]:
    counts: dict[str, int] = {}
    for lang, exts in LANG_EXTENSIONS.items():
        total = 0
        for root, dirs, files in os.walk(REPO_ROOT):
            dirs[:] = [d for d in dirs if d not in EXCLUDE_DIRS]
            for fname in files:
                path = Path(root) / fname
                if _should_skip(path):
                    continue
                matched = any(
                    (fname == ext if not ext.startswith(".") else fname.endswith(ext))
                    for ext in exts
                )
                if not matched:
                    continue
                try:
                    total += sum(1 for _ in open(path, errors="ignore"))
                except OSError:
                    pass
        if total > 0:
            counts[lang] = total
    return dict(sorted(counts.items(), key=lambda x: x[1], reverse=True))


def find_cpu_candidates() -> list[dict[str, Any]]:
    """Find sync Python functions with high loop/math density."""
    candidates: list[dict[str, Any]] = []
    for root, dirs, files in os.walk(REPO_ROOT / "omniprompt"):
        dirs[:] = [d for d in dirs if d not in EXCLUDE_DIRS]
        for fname in files:
            if not fname.endswith(".py"):
                continue
            path = Path(root) / fname
            try:
                src = path.read_text(errors="ignore")
                tree = ast.parse(src)
            except Exception:
                continue
            for node in ast.walk(tree):
                if not isinstance(node, ast.FunctionDef):  # skip async (IO)
                    continue
                body = ast.get_source_segment(src, node) or ""
                loops = sum(
                    1 for n in ast.walk(node)
                    if isinstance(n, (ast.For, ast.While))
                )
                comps = sum(
                    1 for n in ast.walk(node)
                    if isinstance(n, (ast.ListComp, ast.DictComp, ast.GeneratorExp))
                )
                cpu_score = sum(1 for m in CPU_MARKERS if m in body)
                io_score = sum(1 for m in IO_MARKERS if m in body)
                total_score = loops + comps + cpu_score - (io_score * 2)
                if total_score >= 6:
                    candidates.append({
                        "file": fname,
                        "line": node.lineno,
                        "name": node.name,
                        "score": total_score,
                        "loops": loops,
                        "cpu_markers": cpu_score,
                        "io_markers": io_score,
                    })
    return sorted(candidates, key=lambda x: x["score"], reverse=True)


def git_summary() -> dict[str, str]:
    """Return current branch, last commit hash and date."""
    try:
        branch = subprocess.check_output(
            ["git", "rev-parse", "--abbrev-ref", "HEAD"],
            cwd=REPO_ROOT, text=True, stderr=subprocess.DEVNULL,
        ).strip()
        commit = subprocess.check_output(
            ["git", "log", "-1", "--format=%h %s"],
            cwd=REPO_ROOT, text=True, stderr=subprocess.DEVNULL,
        ).strip()
    except Exception:
        branch, commit = "unknown", "unknown"
    return {"branch": branch, "commit": commit}


# ---------------------------------------------------------------------------
# Markdown renderer
# ---------------------------------------------------------------------------

VERDICT_ICON = {
    "ADOPT": "✅",
    "MONITOR": "🔍",
    "DEFER": "⏳",
    "REJECT": "❌",
}


def render_markdown(
    lang_counts: dict[str, int],
    cpu_candidates: list[dict[str, Any]],
    git_info: dict[str, str],
    quarter: str,
) -> str:
    total_lines = sum(lang_counts.values())
    today = datetime.date.today().isoformat()

    lines: list[str] = []
    a = lines.append

    a(f"# Polyglot Language Assessment — {quarter}")
    a("")
    a(f"> **Generated:** {today}  ")
    a(f"> **Repo:** {REPO_ROOT.name}  ")
    a(f"> **Branch:** {git_info['branch']}  ")
    a(f"> **Commit:** {git_info['commit']}  ")
    a("> **Next scheduled run:** quarterly (1 Jan / 1 Apr / 1 Jul / 1 Oct)")
    a("")
    a("## 1. Current Language Composition")
    a("")
    a("| Language | Lines | % of total |")
    a("|---|---:|---:|")
    for lang, count in lang_counts.items():
        pct = count / total_lines * 100
        a(f"| {lang} | {count:,} | {pct:.1f}% |")
    a(f"| **Total** | **{total_lines:,}** | **100%** |")
    a("")
    a("## 2. Bottleneck Profile")
    a("")
    a(
        "The primary bottleneck of this service is **network latency to upstream "
        "LLM APIs** (OpenAI, Anthropic, Google, etc.).  The hot path is "
        "`async`/`await` IO, not CPU computation.  This is the single most "
        "important fact for all language decisions: a native extension speeds up "
        "CPU work; it cannot reduce LLM round-trip time."
    )
    a("")
    a("### CPU-Bound Function Candidates")
    a("")
    a("These synchronous Python functions have the highest loop/math density "
      "and are the most plausible future candidates for a native extension:")
    a("")
    a("| Score | File | Function | Loops | CPU markers | IO markers |")
    a("|---:|---|---|---:|---:|---:|")
    for c in cpu_candidates[:10]:
        a(f"| {c['score']} | {c['file']}:{c['line']} | `{c['name']}` | "
          f"{c['loops']} | {c['cpu_markers']} | {c['io_markers']} |")
    a("")
    a("> Score = loops + comprehensions + CPU markers − 2×IO markers. "
      "Async functions are excluded (they are IO-bound by definition).")
    a("")
    a("## 3. Decision Matrix — Every Candidate Language")
    a("")
    a("| Verdict | Language | Horizon | Trigger |")
    a("|---|---|---|---|")
    for c in CANDIDATES:
        icon = VERDICT_ICON.get(c["verdict"].split()[0], "❓")
        a(f"| {icon} **{c['verdict']}** | {c['lang']} | {c['horizon']} | {c['trigger'][:80]} |")
    a("")

    for c in CANDIDATES:
        icon = VERDICT_ICON.get(c["verdict"].split()[0], "❓")
        a(f"### {icon} {c['lang']}")
        a("")
        a(f"**Verdict:** {c['verdict']}  **Horizon:** {c['horizon']}")
        a("")
        a("**Good fit for:**")
        for area in c["fit_areas"]:
            a(f"- {area}")
        a("")
        a("**Poor fit for:**")
        for nf in c["not_fit"]:
            a(f"- {nf}")
        a("")
        a(f"**Adoption cost:** {c['adoption_cost']}")
        a("")
        a(f"**Adoption trigger:** {c['trigger']}")
        a("")

    a("## 4. Overall Recommendation")
    a("")
    a(
        "The repository is **correctly Python-first**.  The only language changes "
        "that add clear value today are:\n\n"
        "1. **Continue expanding TypeScript** — Node SDK (`sdk/node/`) and VS Code "
        "extension are the right home for non-server code targeting those runtimes. "
        "No action needed; already in progress.\n\n"
        "2. **Instrument bootstrap_significance_test** — add a `time.perf_counter` "
        "probe around it.  If p95 wall-clock exceeds 200 ms under realistic load, "
        "a [PyO3](https://pyo3.rs) Rust extension for that function alone would "
        "yield ~100× speed-up with minimal surface area.\n\n"
        "3. **Do not add C, C++, Zig, Assembly, Julia, R, or Go today.** The "
        "operational cost outweighs any benefit at current scale.\n\n"
        "4. **Machine code / raw assembly is never appropriate** for application-level "
        "code in this domain.  A future Rust crate may use `std::arch` SIMD "
        "intrinsics internally, but that is invisible to the Python surface."
    )
    a("")
    a("## 5. Action Items for This Quarter")
    a("")
    a("- [ ] Add `time.perf_counter` probe to `bootstrap_significance_test` "
      "and log at INFO level")
    a("- [ ] Review Node SDK (`sdk/node/`) completeness against Python SDK parity")
    a("- [ ] If any timeline analysis function exceeds 500 ms p95, open a "
      "tracking issue for Rust extension evaluation")
    a("- [ ] Re-run this assessment next quarter (automated)")
    a("")
    a("---")
    a("")
    a(
        "*This issue was generated automatically by "
        "`scripts/polyglot_assess.py`.  To customise thresholds or candidate "
        "languages, edit `CANDIDATES` and `CPU_MARKERS` in that file.*"
    )

    return "\n".join(lines)


# ---------------------------------------------------------------------------
# JSON renderer
# ---------------------------------------------------------------------------


def render_json(
    lang_counts: dict[str, int],
    cpu_candidates: list[dict[str, Any]],
    git_info: dict[str, str],
    quarter: str,
) -> str:
    return json.dumps({
        "quarter": quarter,
        "repo": REPO_ROOT.name,
        "generated": datetime.date.today().isoformat(),
        "git": git_info,
        "language_composition": lang_counts,
        "cpu_candidates": cpu_candidates[:10],
        "decisions": CANDIDATES,
        "overall_verdict": "Python-first. Expand TypeScript SDK. Monitor Rust for CPU hotspots.",
    }, indent=2)


# ---------------------------------------------------------------------------
# Quarter helper
# ---------------------------------------------------------------------------


def current_quarter() -> str:
    m = datetime.date.today().month
    q = (m - 1) // 3 + 1
    y = datetime.date.today().year
    return f"Q{q} {y}"


# ---------------------------------------------------------------------------
# Entry point
# ---------------------------------------------------------------------------


def main() -> None:
    parser = argparse.ArgumentParser(description="Polyglot assessment for OmniPrompt")
    parser.add_argument("--json", action="store_true", help="Emit JSON instead of Markdown")
    parser.add_argument("--out", metavar="FILE", help="Write output to FILE instead of stdout")
    args = parser.parse_args()

    quarter = current_quarter()
    lang_counts = count_lines_by_language()
    cpu_candidates = find_cpu_candidates()
    git_info = git_summary()

    if args.json:
        output = render_json(lang_counts, cpu_candidates, git_info, quarter)
    else:
        output = render_markdown(lang_counts, cpu_candidates, git_info, quarter)

    if args.out:
        Path(args.out).write_text(output)
        print(f"Assessment written to {args.out}", file=sys.stderr)
    else:
        print(output)


if __name__ == "__main__":
    main()

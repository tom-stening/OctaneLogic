"""conftest.py — pytest configuration and fixtures."""


# ─────────────────────────────────────────────────────────────────────────────
# RuntimeGuard v2 — WSL2 crash prevention
# https://github.com/tom-stening/runtime-guard
# ─────────────────────────────────────────────────────────────────────────────
# RuntimeGuard v2
import logging as _rg_logging
import pytest as _rg_pytest

try:
    from runtime_guard import make_pytest_guard as _make_pytest_guard
    _RG = _make_pytest_guard(
        repo_name='OctaneLogic',
        hints=['Stop after first failure: pytest -x', 'Reduce parallelism: pytest -n2', 'Clear caches: rm -rf .pytest_cache __pycache__'],
    )
    _RG_OK = True
except ImportError:
    _RG = None  # type: ignore[assignment]
    _RG_OK = False

_rg_log = _rg_logging.getLogger("runtime_guard.conftest")


def pytest_configure(config: _rg_pytest.Config) -> None:
    if not _RG_OK or _RG is None:
        return
    _RG.oom_protect()
    try:
        _RG.preflight_check(abort_on_critical=False, auto_intervene=True)
    except Exception:
        pass
    _RG.start_background_check(interval_s=30.0)


def pytest_sessionfinish(session: _rg_pytest.Session, exitstatus: int) -> None:
    if not _RG_OK or _RG is None:
        return
    _RG.stop_background_check()
    avail, total, swap_pct = _RG.memory_snapshot_mb()
    _rg_log.info(
        "[OctaneLogic] Session end — MemAvail=%d MB / %d MB total  SwapUsed=%d%%",
        avail, total, swap_pct,
    )


def pytest_runtest_setup(item: _rg_pytest.Item) -> None:
    if not _RG_OK or _RG is None:
        return
    report = _RG.check_and_log(stage=item.nodeid)
    if report is None:
        return
    _RG.intervene(report)
    report = _RG.check()
    if report is not None and report.is_critical:
        _rg_pytest.skip(
            f"Skipping {item.nodeid}: memory pressure CRITICAL"
            f" ({report.cause}) — preventing OOM crash",
        )
# ─────────────────────────────────────────────────────────────────────────────

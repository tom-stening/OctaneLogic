# Routine Maintenance — OctaneLogic

_Document type: Recurring maintenance cadence_
_Status: Active_
_Last updated: 2026-05-18_

## Purpose

Define the repeating maintenance tasks that keep OctaneLogic secure, accurate,
and operationally reliable.

---

## Cadence Overview

| Trigger | Scope | Est. effort | Owner |
|---|---|---|---|
| **Weekly** | Dependency vulnerability scan | 30 min | Maintainer |
| **Monthly** | Dependency and accuracy review | 2 hours | Maintainer |
| **Quarterly** | Architecture review, AI output audit, compliance check | half day | Maintainer |

---

## Weekly Tasks

### W-01 — Dependency Vulnerability Scan

```bash
pip-audit --requirement <(pip freeze)
```

- CVSS ≥ 7.0: patch within 72 hours.
- Log lower-severity findings in `docs/KNOWN_ISSUES.md` or `KNOWN_ISSUES.md`.

---

## Monthly Tasks

### M-01 — Dependency and Accuracy Review

- Update unpinned dev dependencies where safe.
- Review any domain-specific data sources (APIs, databases, reference data) for
  freshness and correctness.
- File issues for any outdated data sources before the next release.

---

## Quarterly Tasks

### Q1 — Architecture and Compliance Review

- Review the main architecture and foundation documentation for accuracy.
- Confirm open issues are triaged.

### Q2 — AI Output Verification Audit

Review all agent-assisted or agent-generated code and documentation merged in the
quarter.

**Checklist:**

- [ ] Run static type checking on the full codebase; confirm zero new errors.
- [ ] Run the test suite and confirm coverage did not regress; flag AI-generated
  modules with insufficient coverage.
- [ ] Spot-check domain-specific claims in generated code and documentation: verify
  at least three constants, formulas, or citations against their authoritative source.
- [ ] Review generated code in high-risk categories (see `.github/copilot-instructions.md`)
  for the specific verification requirements.

**Logging:** Create `docs/archive/AI_AUDIT_<YYYY-MM>.md` with findings. Escalate
unresolved issues to the backlog.

**Reference**: `.github/copilot-instructions.md` for the full AI verification policy.

### Q3 — Dependency and Licence Audit

- Full dependency vulnerability scan.
- Review all dependency licences for compatibility.

### Q4 — Release Hardening Review

- Confirm all P1 and P2 issues are resolved or have accepted-risk justification.
- Update `KNOWN_ISSUES.md` or `docs/KNOWN_ISSUES.md`.
- Tag the quarterly release candidate and run the full CI suite.

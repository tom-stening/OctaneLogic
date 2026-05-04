# OctaneLogic Known Issues

<!-- markdownlint-disable MD013 -->

_Document type: Defect and limitation register_
_Status: Active_
_Audience: maintainers, contributors, and operators_
_Last updated: 2026-05-04_

---

## Purpose

This register tracks confirmed defects and known limitations with stable IDs,
current severity, mitigations, and planned fixes. It is reviewed and updated
at every `OL-910` ritual.

---

## Status key

| Status | Meaning |
| --- | --- |
| `Open` | Confirmed and not yet fixed |
| `In Progress` | Fix underway |
| `Resolved` | Fix merged and verified |
| `Limitation` | Acknowledged constraint with documented workaround; may never be "fixed" |

---

## Severity key

| Severity | Meaning |
| --- | --- |
| `P0` | Release-blocking or safety-critical |
| `P1` | High-impact correctness or reliability risk |
| `P2` | Medium-impact maintainability or robustness issue |
| `P3` | Low-impact polish or ergonomics issue |

---

## Active issue snapshot

- Open or limitation items: 0
- Severity split: `P0` = 0, `P1` = 0, `P2` = 0, `P3` = 0

---

## Issue register

_No active issues. Add entries as they are discovered using the template below._

---

## Issue template

```
### OL-XXX — <Short title>

| Field | Value |
| --- | --- |
| ID | OL-XXX |
| Status | Open |
| Severity | P? |
| Affected component | <module or file> |
| First observed | YYYY-MM-DD |
| Introduced in | <commit or version> |
| Fixed in | — |

**Symptom**

<What the user or developer observes.>

**Root cause**

<Technical explanation of why it happens.>

**Mitigation**

<Workaround or partial fix available today.>

**Planned fix**

<Description of the intended correct fix and target milestone.>
```

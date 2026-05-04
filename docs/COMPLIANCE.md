# Compliance reference

_Status: Active_
_Audience: maintainers, contributors, operators, and auditors_
_Last updated: 2026-05-05_

## Purpose

This document is the single reference point for ISO standards, legal obligations,
and regulatory requirements that apply to **OctaneLogic** and any system that uses its
outputs.  Every contributor and operator is expected to be aware of these
frameworks.  It is not a substitute for qualified legal advice; when in doubt,
seek counsel from a qualified professional before releasing, deploying, or
commercialising OctaneLogic in a regulated context.

---

## ISO standards

The following standards are broadly relevant to software systems.  Code and
documentation must remain consistent with applicable standards unless a
documented exception is recorded here.

| Standard | Area | Relevance |
| --- | --- | --- |
| **ISO 8601** | Date and time representation | All date/time values in data models, API responses, logs, and documentation must use ISO 8601 UTC notation. |
| **ISO 4217** | Currency codes | Any currency identifiers must use the three-letter ISO 4217 code. |
| **ISO 3166-1 alpha-2** | Country codes | Jurisdiction and locale identifiers must use the two-letter ISO 3166-1 code. |
| **ISO/IEC 27001:2022** | Information security management | Security controls should be mappable to ISO 27001 Annex A; a formal gap register is recommended before v1.0 release. |
| **ISO/IEC 27017:2015** | Cloud security | Applicable if deployed to a cloud provider.  Controls supplement ISO 27001. |
| **ISO/IEC 27018:2019** | PII protection in cloud | Applicable wherever the system processes personally identifiable information in a cloud environment. |
| **ISO/IEC 25010:2023** | Software product quality | Quality attributes (reliability, security, maintainability, portability) should be evaluated against this model at each major release. |
| **ISO/IEC 2382** | IT vocabulary | Standard vocabulary for data quality and measurement concepts used in documentation. |
| **ISO 31000:2018** | Risk management | Risk-identification and risk-evaluation vocabulary; apply when designing risk-scoring or alerting features. |

---

## Data protection and privacy

- Do not ingest, store, or export personally identifiable information (PII)
  unless a lawful basis under the applicable privacy framework has been
  established and documented.
- Audit logs must be designed to avoid logging PII in cleartext.
- Retention periods for ingested raw data must be defined and enforced before
  any production deployment.

### European Union

| Regulation | Area | Key obligation |
| --- | --- | --- |
| **GDPR** (2016/679/EU) | Data protection | Any personal data must be handled in compliance with GDPR.  Minimum data collection, documented lawful basis, and right-to-erasure support are required. |
| **DORA** (2022/2554/EU, from Jan 2025) | Digital operational resilience | API deployments serving financial entities must comply with DORA ICT risk-management and incident-reporting obligations. |
| **eIDAS 2.0** | Digital identity | Applicable if the system processes digital identities or authentication in EU contexts. |

### Australia

| Regulation | Area | Key obligation |
| --- | --- | --- |
| **Australian Privacy Act 1988** | Personal information | The Privacy Act and Australian Privacy Principles (APPs) apply where the system processes personal information about Australian individuals. |
| **APRA CPS 234** | Information security (financial entities) | Applicable if deployed within or on behalf of an APRA-regulated entity. |

### United States

| Regulation | Area | Key obligation |
| --- | --- | --- |
| **CCPA / CPRA** | California consumer privacy | Applicable if the system processes personal data of California residents. |
| **COPPA** | Children's online privacy | Applicable if any features or data collection could reach users under 13. |

### Multi-lateral / international

| Framework | Area | Key obligation |
| --- | --- | --- |
| **FATF Recommendations** | AML / CTF | Any feature involving financial flows or identity must not circumvent FATF-aligned transaction monitoring. |

---

## Security

- Credentials, API keys, and secrets must never be committed to version control.
- Dependencies must be kept up to date; known-vulnerable versions must be
  resolved before any production release.
- Any security vulnerability must be reported via the process documented in
  `SECURITY.md`.

---

## Export control and sanctions

- The software must not be used to circumvent economic sanctions or to provide
  intelligence to sanctioned entities.
- Consult the current OFAC, UN, EU, and DFAT consolidated sanctions lists
  before adding new data sources or deploying in sanctioned-adjacent regions.

---

## Contribution obligations

All contributors are responsible for:

1. Flagging any new feature, connector, or data source that may implicate a
   regulation listed in this document — in the PR description.
2. Not introducing code that could be used to circumvent regulatory reporting
   obligations (e.g., intentionally masking data provenance or suppressing
   audit events).
3. Using ISO 4217, ISO 3166-1, and ISO 8601 conventions in all data models
   and API contracts.
4. Tagging the relevant regulation in code comments when a function's output
   is specifically intended to satisfy a regulatory obligation
   (e.g., `# Satisfies: GDPR Art. 5(1)(e) storage limitation`).

---

## Compliance review cadence

A compliance review should be performed at each major release or at minimum
annually.  At each review:

- Confirm this document accurately reflects the current regulatory landscape.
- Check for newly enacted regulations relevant to new features added since the
  last review.
- Verify that ISO standard version numbers are current (standards are revised
  periodically).
- Update the `_Last updated_` date at the top of this file.

---

## Further reading

- [ISO Standards catalogue](https://www.iso.org/standards-catalogue/browse-by-ics.html)
- [EUR-Lex — EU regulation texts](https://eur-lex.europa.eu/)
- [GDPR full text](https://gdpr-info.eu/)
- [DORA regulation text](https://eur-lex.europa.eu/legal-content/EN/TXT/?uri=CELEX:32022R2554)
- [Australian Privacy Act](https://www.legislation.gov.au/Details/C2022C00361)
- [CCPA official text](https://oag.ca.gov/privacy/ccpa)
- [NIST Cybersecurity Framework](https://www.nist.gov/cyberframework)
- [FATF Recommendations](https://www.fatf-gafi.org/en/recommendations.html)
- [OFAC Sanctions Lists](https://ofac.treasury.gov/sanctions-list-search)
- [DFAT Sanctions](https://www.dfat.gov.au/international-relations/security/sanctions)

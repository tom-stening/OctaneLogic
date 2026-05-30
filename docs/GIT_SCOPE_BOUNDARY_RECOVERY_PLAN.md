# Git Scope Boundary Recovery Plan - OctaneDrive

Document type: Repository-specific incident recovery plan  
Status: Active - Phase 1 in progress
Created: 2026-05-29

## Scope

This plan tracks repository-specific actions for resolving Git boundary and file explorer delete/untracked artifacts.

## Repository Context

- Repository: OctaneDrive
- Expected Git Top-Level: /home/thomas_stening/OctaneDrive
- Expected Recovery Plan Path: docs/GIT_SCOPE_BOUNDARY_RECOVERY_PLAN.md

## Old-to-New Repository Name Mapping

| Old Name (remote slug) | New Name (local folder) | Renamed |
| --- | --- | --- |
| Airlines-Manager-Optimiser | AirlineOps | Yes |
| ApexLogic | ApexBeacon | Yes |
| TrueLedger | AssuranceNode | Yes |
| AudioMesh | AudioMesh | No |
| AxiomTrace | AxiomInsight | Yes |
| BIP-Electrical-Inductions-Website | BIP-Electrical-Inductions-Website | No |
| BIP-Induction-Website | BIP-Induction-Website | No |
| BondGraph | BondGraph | No |
| FiscalMesh | BudgetClerk | Yes |
| BushPalate | BushPalate | No |
| NexusCAD | CadenceWorks | Yes |
| EquityTrace | CapitalWatch | Yes |
| EquityMesh | CivicCompass | Yes |
| EcoMesh | EcoImpact | Yes |
| FieldSpace | FieldSpace | No |
| tax-legislation-scraper | FilingScraper | Yes |
| FluxSign | FluxSign | No |
| FoundryLogic | FoundryForge | Yes |
| CargoVector | FreightLane | Yes |
| runtime-guard | HostGauge | Yes |
| KinBase | KinBase | No |
| LeafLogic | LeafGarden | Yes |
| ML-Trading- | ML-Trading | Yes |
| ForgeMetric | MetricMotion | Yes |
| UrbanTrace | MetroSpark | Yes |
| AudioMesh | MixHarbor | Yes |
| Movie-Finder | Movie-Finder | No |
| OctaneLogic | OctaneDrive | Yes |
| OmniTrace | OrbitAxis | Yes |
| Plant_Database | PlantDatabase | Yes |
| PrimeForge | PrimeNova | Yes |
| OmniPrompt | PromptCanvas | Yes |
| RangeMind | RangeMind | No |
| TraceSync | RelayBridge | Yes |
| SovereignFlow | RepatriationFlow | Yes |
| RipGrid | RipChart | Yes |
| RuleSet | RuleSet | No |
| AudioMesh | SonicWave | Yes |
| SynapseLogic | SynapseVector | Yes |
| UnitPulse | SystemMechanic | Yes |
| TaxScenarioEngine | TaxScenarioEngine | No |
| TrunkLine | TrunkLine | No |
| CivicNode | UrbanVista | Yes |
| VaneFlow | VaneStream | Yes |
| VaultPath | VaultRoute | Yes |
| VividPath | VividJourney | Yes |
| VoltForge | VoltArc | Yes |
| Wine_Bottle_Storage_Optimiser | WineBottleStorageOptimiser | Yes |
| wsl-system-guard | WslSentinel | Yes |

## Current Assessment

- Top-level check: pass
- Remote check: https://github.com/tom-stening/OctaneLogic.git
- Default branch check: main
- Unexplained delete check: modified=0, added=0, deleted=0, untracked=7

## Phase 1 Tasks

1. Confirm git top-level equals /home/thomas_stening/OctaneDrive.
2. Record origin remote and default branch.
3. Record current git status --short and classify each change as expected or unexpected.
4. Confirm required docs and governance files are present.

## Phase 2+ Tasks (Queued)

1. Apply boundary correction steps from OmniTrace master plan if top-level mismatch exists.
2. Reconcile rename history and restore missing files where required.
3. Run project health checks and capture evidence.
4. Close only after clean boundary and explained working tree state.

## Evidence Log

- 2026-05-29: Plan scaffold created and normalized.

## Operational Guardrails (Preventative)

1. Validate boundary before risky operations:
   - cd /home/thomas_stening/OctaneDrive && git rev-parse --show-toplevel
   - cd /home/thomas_stening/OctaneDrive && git remote get-url origin
   - cd /home/thomas_stening/OctaneDrive && git symbolic-ref refs/remotes/origin/HEAD || true
   - cd /home/thomas_stening/OctaneDrive && git status --short
2. Preserve work before boundary correction using manual fallback snapshot:
   - cd /home/thomas_stening/OctaneDrive && mkdir -p docs/archive/git-scope-phase2/work-preservation
   - cd /home/thomas_stening/OctaneDrive && TS=$(date -u +%Y%m%dT%H%M%SZ) && git status --short > docs/archive/git-scope-phase2/work-preservation/status_${TS}.txt
   - cd /home/thomas_stening/OctaneDrive && TS=$(date -u +%Y%m%dT%H%M%SZ) && git diff > docs/archive/git-scope-phase2/work-preservation/tracked_diff_${TS}.patch
   - cd /home/thomas_stening/OctaneDrive && TS=$(date -u +%Y%m%dT%H%M%SZ) && git ls-files --others --exclude-standard > docs/archive/git-scope-phase2/work-preservation/untracked_${TS}.txt
3. If the CLI exposes triage preserve-work in this repo, it may be used instead of the fallback.

## Prevention Notes

- Treat /home/thomas_stening/OrbitAxis/docs/archive/copilot-conversations as the canonical continuity archive.
- Keep the handoff + session-start files updated together after each major migration step.

# OctaneDrive Session Continuation - Start Here

Status date: 2026-05-29

## Copy-Paste Prompt For New Copilot Chat

Read /home/thomas_stening/OctaneDrive/docs/COPILOT_CONVERSATION_HANDOFF.md and summarize prior decisions from the local archive files, then continue from the latest recovery status in /home/thomas_stening/OctaneDrive/docs/GIT_SCOPE_BOUNDARY_RECOVERY_PLAN.md.

## Immediate Working Files

1. /home/thomas_stening/OctaneDrive/docs/GIT_SCOPE_BOUNDARY_RECOVERY_PLAN.md
2. /home/thomas_stening/OctaneDrive/docs/COPILOT_CONVERSATION_HANDOFF.md
3. /home/thomas_stening/OrbitAxis/docs/archive/copilot-conversations/export-summary.json
4. /home/thomas_stening/OrbitAxis/docs/archive/copilot-conversations/CONVERSATION_MIGRATION_STATUS.md

## Operational Guardrails

1. Validate repository boundary before risky operations:
   - cd /home/thomas_stening/OctaneDrive && git rev-parse --show-toplevel
   - cd /home/thomas_stening/OctaneDrive && git remote get-url origin
   - cd /home/thomas_stening/OctaneDrive && git symbolic-ref refs/remotes/origin/HEAD || true
   - cd /home/thomas_stening/OctaneDrive && git status --short
2. Preserve viable work before any boundary-correction step (manual fallback snapshot):
   - cd /home/thomas_stening/OctaneDrive && mkdir -p docs/archive/git-scope-phase2/work-preservation
   - cd /home/thomas_stening/OctaneDrive && TS=$(date -u +%Y%m%dT%H%M%SZ) && git status --short > docs/archive/git-scope-phase2/work-preservation/status_${TS}.txt
   - cd /home/thomas_stening/OctaneDrive && TS=$(date -u +%Y%m%dT%H%M%SZ) && git diff > docs/archive/git-scope-phase2/work-preservation/tracked_diff_${TS}.patch
   - cd /home/thomas_stening/OctaneDrive && TS=$(date -u +%Y%m%dT%H%M%SZ) && git ls-files --others --exclude-standard > docs/archive/git-scope-phase2/work-preservation/untracked_${TS}.txt

## Notes

- Conversation archives are readable/searchable continuity artifacts.
- Copilot live chat state cannot be auto-imported from transcript files.
- The repo-local preservation fallback is preferred if a repo-specific triage preserve-work command is unavailable.

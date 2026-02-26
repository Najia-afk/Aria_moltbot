# Repo Cleanup Risk Register

## Risk Format
| Risk ID | Description | Trigger/Indicator | Likelihood | Impact | Mitigation | Owner | Residual Risk |
|---------|-------------|-------------------|------------|--------|------------|-------|---------------|

---

| Risk ID | Description | Trigger/Indicator | Likelihood | Impact | Mitigation | Owner | Residual Risk |
|---------|-------------|-------------------|------------|--------|------------|-------|---------------|
| R-001 | Deleted script is actually imported by a test or CI step not discovered | Test failure after deletion | Low | Medium | grep_search for each script name before deletion; run pytest after Wave 1 | Sprint owner | Low — comprehensive reference check done |
| R-002 | Deleted audit doc contains unrealized action items | Lost institutional knowledge | Low | Low | Scan each doc for TODO/action items before deletion | Sprint owner | Low — docs are snapshots, not action trackers |
| R-003 | Moving API_ENDPOINT_INVENTORY.md breaks cross-references | 404 links in docs | Low | Low | Search and update all references before committing move | Sprint owner | Low |
| R-004 | STRUCTURE.md update introduces inconsistency | Incorrect file listings | Low | Low | Targeted update only for removed files, not full rewrite | Sprint owner | Low |
| R-005 | CI workflows become inconsistent if tests.yml references deleted files | CI failure | Low | Medium | Check tests.yml references before deletion | Sprint owner | Low |
| R-006 | Docker stack regression from file moves | Container build/start failure | Very Low | High | No Docker-referenced files are being deleted; compose only references src/, aria_*/ packages | Sprint owner | Very Low |

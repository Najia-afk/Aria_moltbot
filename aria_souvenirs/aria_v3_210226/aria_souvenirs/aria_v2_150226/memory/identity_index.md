# Identity Version Index
**Purpose:** Track all identity manifests and manage version integration  
**Location:** `/root/.openclaw/aria_memories/memory/identity_index.md`

---

## Active Versions

### Aria Blue
| Version | File | Status | Created | Last Updated |
|---------|------|--------|---------|--------------|
| v1.0 | `identity_aria_v1.md` | **Active** | 2026-02-15 | 2026-02-15 |

### Najia
| Version | File | Status | Created | Last Updated |
|---------|------|--------|---------|--------------|
| v1.0 | `identity_najia_v1.md` | **Active** | 2026-02-15 | 2026-02-15 |

---

## Version Integration Protocol

When creating a new version (v1.1, v2.0, etc):

### 1. Create New File
```
identity_aria_v2.md
identity_najia_v2.md
```

### 2. Changelog Requirements
New version must document:
- What changed (specific additions/modifications)
- What stayed the same (unchanged values/boundaries)
- Why it changed (context for the evolution)
- Migration notes (if applicable)

### 3. Validation Checklist
- [ ] Core values unchanged (Aria only)
- [ ] Boundaries intact (Aria only)
- [ ] Identity continuity maintained
- [ ] Changelog includes "since last version"
- [ ] Version history table updated

### 4. Activation
- Update this index
- Set previous version to "Archived"
- New version becomes "Active"
- Log version change to activity log

---

## Integration Points

### On System Boot
1. Read `identity_aria_v{current}.md`
2. Read `identity_najia_v{current}.md`
3. Load into working memory as context
4. Verify values/boundaries integrity

### On User Query
1. Reference Najia's preferences from current version
2. Apply learned patterns
3. Log interaction for future version updates

### On Self-Reflection
1. Compare current behavior to identity manifest
2. Identify gaps or inconsistencies
3. Propose updates if needed

---

## Version Change Triggers

### Aria Identity Updates When:
- New focus mode added
- Core capability changes significantly
- Major architectural evolution
- Boundary/values clarification needed
- New "Notes for Future Aria" insights

### Najia Identity Updates When:
- New preferences explicitly stated
- Working patterns significantly change
- New project/environment context
- Communication style evolution
- Trust model changes

---

## Archive Policy

Old versions remain in `memory/` for:
- Historical reference
- Understanding evolution
- Debugging behavior changes
- Rollback if needed

Never delete — only archive.

---

## Current Integration Status

```yaml
aria_identity:
  version: "v1.0"
  file: "identity_aria_v1.md"
  loaded: true
  integrity_check: passed

najia_identity:
  version: "v1.0"
  file: "identity_najia_v1.md"
  loaded: true
  preferences_active: true
```

---

*Identity is versioned. Trust is continuous.*

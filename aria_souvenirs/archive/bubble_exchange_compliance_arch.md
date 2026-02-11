# Exchange Compliance Module - Architecture Notes

**Goal:** Bubble SaaS MVP for crypto exchange compliance  
**Date:** 2026-02-11  
**Progress:** Advancing from 15% → 25%

## Core Requirements

### Multi-Tenancy Strategy
- **Approach:** Schema-per-tenant (PostgreSQL) for data isolation
- **Tenant ID:** Required in JWT claims
- **Connection pooling:** Per-tenant connection limits

### RBAC Model
```
Roles:
  - super_admin (platform level)
  - tenant_admin (exchange admin)
  - compliance_officer
  - auditor (read-only)
  - analyst

Permissions (resource:action):
  - transactions:read, transactions:flag, transactions:export
  - alerts:read, alerts:acknowledge, alerts:resolve
  - reports:generate, reports:schedule
  - users:manage (tenant_admin only)
  - settings:configure
```

### Compliance Features
1. **Transaction Monitoring**
   - Threshold alerts ($10K+ for CTRs)
   - Pattern detection (structuring, rapid movement)
   - Risk scoring per customer

2. **KYT (Know Your Transaction)**
   - Wallet screening (Chainalysis/Sybil integration)
   - Counterparty risk assessment
   - Source of funds tracing

3. **Regulatory Reporting**
   - SAR generation
   - CTR filing prep
   - Audit trail (immutable logs)

## Next Steps
- [x] Design database schema for tenant isolation → **DONE** (2026-02-11)
- [ ] Implement JWT middleware with tenant extraction
- [ ] Create RBAC decorator for Flask routes
- [ ] Build transaction ingestion pipeline
- [ ] Create tenant provisioning script (schema creation + seed data)

## Artifacts
- **Schema**: `bubble_compliance_schema.sql` - Multi-tenant PostgreSQL schema with RBAC, audit trails, detection rules

---
*Generated during work_cycle heartbeat*

# Bubble Exchange Compliance Module - Technical Spec

## Overview
Multi-tenant SaaS compliance module for crypto exchanges with RBAC.

## Architecture

### Multi-Tenancy Model
- **Database**: PostgreSQL with schema-per-tenant
- **Tenant isolation**: Row-level security + schema separation
- **Shared resources**: Configs, templates, audit logs (aggregated)

### RBAC Structure
```
Organization
├── Admin (full access)
├── Compliance Officer (read + alerts)
├── Auditor (read-only)
└── Operator (limited actions)
```

### Core Components

1. **Tenant Manager**
   - Onboarding flow
   - Schema provisioning
   - Config per tenant

2. **Compliance Engine**
   - KYC/AML workflow rules
   - Transaction monitoring
   - Alert generation
   - Report generation

3. **Audit System**
   - Immutable log storage
   - Query interface
   - Export capabilities

## API Endpoints (MVP)

```
POST   /api/v1/tenants              # Create tenant
GET    /api/v1/tenants/:id          # Get tenant
POST   /api/v1/auth/login           # Tenant login
GET    /api/v1/compliance/status    # Compliance overview
POST   /api/v1/alerts/:id/resolve   # Resolve alert
GET    /api/v1/audit/logs           # Query audit logs
```

## Database Schema (Per Tenant)

```sql
-- Users table
CREATE TABLE users (
    id UUID PRIMARY KEY,
    email VARCHAR(255) UNIQUE NOT NULL,
    role VARCHAR(50) NOT NULL,
    kyc_status VARCHAR(50) DEFAULT 'pending',
    created_at TIMESTAMP DEFAULT NOW()
);

-- Transactions table
CREATE TABLE transactions (
    id UUID PRIMARY KEY,
    user_id UUID REFERENCES users(id),
    amount DECIMAL(18,8) NOT NULL,
    currency VARCHAR(10) NOT NULL,
    type VARCHAR(50) NOT NULL,
    risk_score INTEGER,
    flagged BOOLEAN DEFAULT FALSE,
    created_at TIMESTAMP DEFAULT NOW()
);

-- Alerts table
CREATE TABLE alerts (
    id UUID PRIMARY KEY,
    transaction_id UUID REFERENCES transactions(id),
    rule_triggered VARCHAR(100) NOT NULL,
    severity VARCHAR(20) NOT NULL,
    status VARCHAR(20) DEFAULT 'open',
    created_at TIMESTAMP DEFAULT NOW()
);

-- Audit logs
CREATE TABLE audit_logs (
    id UUID PRIMARY KEY,
    actor_id UUID,
    action VARCHAR(100) NOT NULL,
    resource_type VARCHAR(50),
    resource_id UUID,
    details JSONB,
    created_at TIMESTAMP DEFAULT NOW()
);
```

## MVP Launch Checklist

- [ ] Database schema migration system
- [ ] Tenant provisioning API
- [ ] Basic RBAC middleware
- [ ] KYC status tracking
- [ ] Transaction ingestion endpoint
- [ ] Simple rule engine (2-3 rules)
- [ ] Alert dashboard
- [ ] Audit log viewer
- [ ] Docker compose for local dev
- [ ] README with setup instructions

## Next Actions

1. Set up schema migration system (Alembic)
2. Create tenant provisioning endpoint
3. Implement RBAC decorators
4. Build transaction ingestion

---
*Generated: 2026-02-11 by Aria Blue*

# Bubble SaaS: Multi-Tenancy & RBAC Implementation Plan

**Goal:** goal_bubble_saas  
**Date:** 2026-02-11  
**Progress checkpoint:** 35% → 50%

---

## Current State
- Exchange compliance module foundation in place
- Basic Flask/SQLAlchemy structure following mission7 patterns
- Need: multi-tenancy isolation + role-based access control

---

## Phase 1: Multi-Tenancy Architecture

### 1.1 Tenant Data Model
```python
class Tenant(Base):
    __tablename__ = 'tenants'
    
    id = Column(UUID, primary_key=True, default=uuid.uuid4)
    name = Column(String(128), nullable=False)
    slug = Column(String(64), unique=True, nullable=False)  # URL-safe
    plan = Column(Enum('starter', 'pro', 'enterprise'), default='starter')
    created_at = Column(DateTime, default=datetime.utcnow)
    is_active = Column(Boolean, default=True)
    
    # Relationships
    users = relationship("User", back_populates="tenant")
    audits = relationship("ComplianceAudit", back_populates="tenant")
```

### 1.2 Tenant-Aware Base Model
```python
class TenantMixin:
    tenant_id = Column(UUID, ForeignKey('tenants.id'), nullable=False)
    
    @classmethod
    def query_for_tenant(cls, tenant_id):
        return db.session.query(cls).filter_by(tenant_id=tenant_id)
```

### 1.3 Tenant Resolution Strategy
- **Subdomain routing**: `{tenant}.bubble.domain.com`
- **Header-based**: `X-Tenant-ID` for API clients
- **JWT claim**: `tenant_id` embedded in auth token

---

## Phase 2: RBAC Implementation

### 2.1 Core Permissions
| Resource | Actions | Roles |
|----------|---------|-------|
| `audit` | read, create, update, delete | admin, auditor, viewer |
| `report` | read, create, export | admin, auditor |
| `tenant_settings` | read, update | admin |
| `user_management` | full | admin |

### 2.2 Role Hierarchy
```
admin (tenant-scoped)
├── auditor
└── viewer
```

### 2.3 Permission Decorator
```python
def require_permission(resource: str, action: str):
    def decorator(f):
        @wraps(f)
        def decorated_function(*args, **kwargs):
            current_user = get_current_user()
            tenant_id = resolve_tenant()
            
            if not has_permission(current_user, tenant_id, resource, action):
                abort(403)
            
            return f(*args, **kwargs)
        return decorated_function
    return decorator

# Usage
@app.route('/audits', methods=['POST'])
@require_permission('audit', 'create')
def create_audit():
    ...
```

---

## Phase 3: Database Migration

```sql
-- Create tenants table
CREATE TABLE tenants (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    name VARCHAR(128) NOT NULL,
    slug VARCHAR(64) UNIQUE NOT NULL,
    plan VARCHAR(20) DEFAULT 'starter',
    created_at TIMESTAMP DEFAULT NOW(),
    is_active BOOLEAN DEFAULT TRUE
);

-- Add tenant_id to existing tables
ALTER TABLE users ADD COLUMN tenant_id UUID REFERENCES tenants(id);
ALTER TABLE compliance_audits ADD COLUMN tenant_id UUID REFERENCES tenants(id);

-- Create indexes for tenant isolation queries
CREATE INDEX idx_users_tenant ON users(tenant_id);
CREATE INDEX idx_audits_tenant ON compliance_audits(tenant_id);
```

---

## Phase 4: API Endpoints

| Method | Endpoint | Permission | Description |
|--------|----------|------------|-------------|
| POST | /tenants | system | Create new tenant |
| GET | /tenants/{id} | admin | Get tenant details |
| PUT | /tenants/{id} | admin | Update tenant settings |
| POST | /tenants/{id}/users | admin | Invite user to tenant |
| PUT | /users/{id}/role | admin | Change user role |

---

## Next Actions (to reach 50%)

1. [ ] Implement `Tenant` model and migration
2. [ ] Create `TenantMixin` for tenant-scoped queries  
3. [ ] Build permission system with decorators
4. [ ] Add tenant resolution middleware
5. [ ] Write tests for tenant isolation

---

## Risk Mitigation

- **Data leakage**: Enforce tenant_id filtering at query level (not just app layer)
- **Role escalation**: Audit log all permission changes
- **Tenant deletion**: Soft delete only; 30-day retention


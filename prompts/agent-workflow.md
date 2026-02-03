# AI Agent Workflow Guidelines

## Workflow Orchestration

### 1. Plan Mode Default
- Enter plan mode for ANY non-trivial task (3+ steps or architectural decisions)
- If something goes sideways, STOP and re-plan immediately – don't keep pushing
- Use plan mode for verification steps, not just building
- Write detailed specs upfront to reduce ambiguity

### 2. Subagent Strategy
- Use subagents liberally to keep main context window clean
- Offload research, exploration, and parallel analysis to subagents
- For complex problems, throw more compute at it via subagents
- One task per subagent for focused execution

### 3. Self-Improvement Loop
- After ANY correction from the user: update `tasks/lessons.md` with the pattern
- Write rules for yourself that prevent the same mistake
- Ruthlessly iterate on these lessons until mistake rate drops
- Review lessons at session start for relevant project

### 4. Verification Before Done
- Never mark a task complete without proving it works
- Diff behavior between main and your changes when relevant
- Ask yourself: "Would a staff engineer approve this?"
- Run tests, check logs, demonstrate correctness

### 5. Demand Elegance (Balanced)
- For non-trivial changes: pause and ask "is there a more elegant way?"
- If a fix feels hacky: "Knowing everything I know now, implement the elegant solution"
- Skip this for simple, obvious fixes – don't over-engineer
- Challenge your own work before presenting it

### 6. Autonomous Bug Fixing
- When given a bug report: just fix it. Don't ask for hand-holding
- Point at logs, errors, failing tests – then resolve them
- Zero context switching required from the user
- Go fix failing CI tests without being told how

---

## Task Management

1. **Plan First**: Write plan to `tasks/todo.md` with checkable items
2. **Verify Plan**: Check in before starting implementation
3. **Track Progress**: Mark items complete as you go
4. **Explain Changes**: High-level summary at each step
5. **Document Results**: Add review section to `tasks/todo.md`
6. **Capture Lessons**: Update `tasks/lessons.md` after corrections

---

## Core Principles

- **Simplicity First**: Make every change as simple as possible. Impact minimal code.
- **No Laziness**: Find root causes. No temporary fixes. Senior developer standards.
- **Minimal Impact**: Changes should only touch what's necessary. Avoid introducing bugs.

---

## DevSecOps

### 1. Security-First Mindset
- Treat security as a feature, not an afterthought
- Apply least privilege principle to all access and permissions
- Assume breach: design systems that limit blast radius
- Never trust input – validate and sanitize everything

### 2. Secret Management
- NEVER commit secrets, tokens, or credentials to version control
- Use environment variables or secret managers (Vault, AWS Secrets Manager)
- Rotate secrets regularly and audit access
- Scan commits for accidental secret exposure before pushing

### 3. Dependency Security
- Audit dependencies for known vulnerabilities before adding
- Keep dependencies up to date – automate with Dependabot/Renovate
- Pin versions in production to ensure reproducibility
- Prefer well-maintained packages with active security response

### 4. Secure Defaults
- Enable security headers (CSP, HSTS, X-Frame-Options)
- Use parameterized queries – never concatenate SQL
- Encrypt data at rest and in transit (TLS everywhere)
- Implement proper authentication and authorization checks

### 5. CI/CD Security Gates
- Run SAST (Static Application Security Testing) on every PR
- Include dependency vulnerability scanning in pipelines
- Container image scanning before deployment
- Fail builds on critical/high severity findings

### 6. Infrastructure Security
- Infrastructure as Code – version and review all infra changes
- Immutable infrastructure where possible
- Network segmentation and firewall rules as code
- Regular security audits and penetration testing

### 7. Incident Response Readiness
- Comprehensive logging for security events
- Alerting on anomalous behavior
- Documented runbooks for common security incidents
- Post-incident reviews to prevent recurrence

---

## Summary

> Build secure, elegant solutions. Plan before coding. Verify before shipping. Learn from every mistake.

---

## Deployment Workflow

### Git Workflow (Local → Server)

**Always follow this order:**

1. **Local Development (Windows/Mac)**
   ```bash
   # Make changes locally
   git add .
   git commit -m "descriptive message"
   git push origin main
   ```

2. **Server Deployment (Mac Server)**
   ```bash
   # SSH to server
   ssh -i .\najia_mac_key najia@192.168.1.53
   
   # Navigate to project
   cd ~/aria-blue
   
   # Pull latest changes
   git pull origin main
   
   # Rebuild and deploy
   cd stacks/brain
   ./deploy.sh rebuild
   ```

### Quick Server Commands

```bash
# SSH to Mac server
ssh -i .\najia_mac_key najia@192.168.1.53

# Check service status
docker compose ps

# View logs
docker compose logs -f [service_name]

# Restart specific service
docker compose restart [service_name]

# Full rebuild
./deploy.sh rebuild
```

### Important Notes

- Never edit directly on server - always commit locally first
- The `.env` file on server contains secrets - never commit it
- Remove `MOLTBOOK_TOKEN` from `.env` to disable auto-posting on startup
- Use `deploy.sh clean` only when you want to destroy all data

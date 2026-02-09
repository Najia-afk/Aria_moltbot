# aria_skills/security_scan.py
"""
🔒 Security Scanning Skill - DevSecOps Focus

Provides security scanning capabilities for Aria's DevSecOps persona.
Handles vulnerability detection, dependency scanning, and code analysis.
"""
import hashlib
import re
from dataclasses import dataclass, field
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Optional

from aria_skills.base import BaseSkill, SkillConfig, SkillResult, SkillStatus
from aria_skills.registry import SkillRegistry


@dataclass
class Vulnerability:
    """A detected vulnerability."""
    id: str
    severity: str  # critical, high, medium, low, info
    title: str
    description: str
    file: Optional[str] = None
    line: Optional[int] = None
    recommendation: str = ""
    cwe: Optional[str] = None  # CWE ID if applicable


@dataclass
class ScanResult:
    """Result of a security scan."""
    scan_id: str
    scan_type: str
    target: str
    vulnerabilities: list[Vulnerability] = field(default_factory=list)
    started_at: datetime = field(default_factory=lambda: datetime.now(timezone.utc))
    completed_at: Optional[datetime] = None


@SkillRegistry.register
class SecurityScanSkill(BaseSkill):
    """
    Security scanning and vulnerability detection.
    
    Capabilities:
    - Code pattern scanning (secrets, SQL injection, XSS)
    - Dependency vulnerability checking
    - Configuration analysis
    - Security report generation
    """
    
    # Severity weights for scoring
    SEVERITY_WEIGHTS = {
        "critical": 10,
        "high": 7,
        "medium": 4,
        "low": 1,
        "info": 0,
    }
    
    # Dangerous patterns to detect
    SECRET_PATTERNS = [
        (r'api[_-]?key\s*[=:]\s*["\']?[\w\-]{20,}', "API Key Exposure", "high"),
        (r'password\s*[=:]\s*["\'][^"\']+["\']', "Hardcoded Password", "critical"),
        (r'secret\s*[=:]\s*["\'][^"\']+["\']', "Hardcoded Secret", "critical"),
        (r'aws_access_key_id\s*[=:]\s*["\']?[A-Z0-9]{20}', "AWS Access Key", "critical"),
        (r'private_key\s*[=:]\s*["\']?-----BEGIN', "Private Key Exposure", "critical"),
        (r'token\s*[=:]\s*["\']?[a-zA-Z0-9\-_]{30,}', "Token Exposure", "high"),
    ]
    
    CODE_PATTERNS = [
        (r'eval\s*\(', "Use of eval()", "high", "CWE-95"),
        (r'exec\s*\(', "Use of exec()", "high", "CWE-95"),
        (r'subprocess\.call\([^)]*shell\s*=\s*True', "Shell Injection Risk", "critical", "CWE-78"),
        (r'os\.system\s*\(', "OS Command Execution", "high", "CWE-78"),
        (r'pickle\.loads?\s*\(', "Unsafe Deserialization", "high", "CWE-502"),
        (r'\.format\s*\([^)]*\)\s*%', "Format String Vulnerability", "medium", "CWE-134"),
        (r'SELECT.*\+.*input|SELECT.*%s.*%', "Potential SQL Injection", "high", "CWE-89"),
        (r'innerHTML\s*=', "Potential XSS via innerHTML", "high", "CWE-79"),
        (r'document\.write\s*\(', "Potential XSS via document.write", "high", "CWE-79"),
    ]
    
    @property
    def name(self) -> str:
        return "security_scan"
    
    async def initialize(self) -> bool:
        """Initialize security scanning skill."""
        self._scans: dict[str, ScanResult] = {}
        self._status = SkillStatus.AVAILABLE
        self.logger.info("🔒 Security scan skill initialized")
        return True
    
    async def health_check(self) -> SkillStatus:
        """Check security scan skill availability."""
        return self._status
    
    async def scan_code(
        self,
        code: str,
        language: str = "python",
        file_name: Optional[str] = None
    ) -> SkillResult:
        """
        Scan code for security issues.
        
        Args:
            code: Code to scan
            language: Programming language
            file_name: Optional file name for reporting
            
        Returns:
            SkillResult with vulnerabilities found
        """
        try:
            scan_id = f"scan_{datetime.now(timezone.utc).strftime('%Y%m%d%H%M%S')}"
            
            vulnerabilities = []
            lines = code.split('\n')
            
            # Scan for secrets
            for pattern, title, severity in self.SECRET_PATTERNS:
                for i, line in enumerate(lines, 1):
                    if re.search(pattern, line, re.IGNORECASE):
                        vuln_id = f"vuln_{hashlib.md5(f'{pattern}{i}'.encode()).hexdigest()[:8]}"
                        vulnerabilities.append(Vulnerability(
                            id=vuln_id,
                            severity=severity,
                            title=title,
                            description=f"Potential {title.lower()} detected",
                            file=file_name,
                            line=i,
                            recommendation="Move sensitive data to environment variables or a secrets manager"
                        ))
            
            # Scan for code patterns
            for entry in self.CODE_PATTERNS:
                pattern, title, severity = entry[:3]
                cwe = entry[3] if len(entry) > 3 else None
                
                for i, line in enumerate(lines, 1):
                    if re.search(pattern, line):
                        vuln_id = f"vuln_{hashlib.md5(f'{pattern}{i}'.encode()).hexdigest()[:8]}"
                        vulnerabilities.append(Vulnerability(
                            id=vuln_id,
                            severity=severity,
                            title=title,
                            description=f"Security concern: {title}",
                            file=file_name,
                            line=i,
                            recommendation=self._get_recommendation(title),
                            cwe=cwe
                        ))
            
            scan_result = ScanResult(
                scan_id=scan_id,
                scan_type="code",
                target=file_name or "inline_code",
                vulnerabilities=vulnerabilities,
                completed_at=datetime.now(timezone.utc)
            )
            
            self._scans[scan_id] = scan_result
            
            # Calculate security score
            score = self._calculate_security_score(vulnerabilities)
            
            return SkillResult.ok({
                "scan_id": scan_id,
                "target": file_name or "inline_code",
                "language": language,
                "lines_scanned": len(lines),
                "vulnerabilities_found": len(vulnerabilities),
                "security_score": score,
                "by_severity": self._count_by_severity(vulnerabilities),
                "vulnerabilities": [
                    {
                        "id": v.id,
                        "severity": v.severity,
                        "title": v.title,
                        "line": v.line,
                        "cwe": v.cwe,
                        "recommendation": v.recommendation
                    }
                    for v in vulnerabilities
                ],
                "scanned_at": scan_result.completed_at.isoformat()
            })
            
        except Exception as e:
            return SkillResult.fail(f"Code scan failed: {str(e)}")
    
    async def scan_file(self, file_path: str) -> SkillResult:
        """
        Scan a file for security issues.
        
        Args:
            file_path: Path to file to scan
            
        Returns:
            SkillResult with scan results
        """
        try:
            path = Path(file_path)
            if not path.exists():
                return SkillResult.fail(f"File not found: {file_path}")
            
            content = path.read_text()
            
            # Detect language from extension
            ext_to_lang = {
                ".py": "python",
                ".js": "javascript",
                ".ts": "typescript",
                ".go": "go",
                ".java": "java",
                ".rb": "ruby",
            }
            language = ext_to_lang.get(path.suffix, "unknown")
            
            return await self.scan_code(content, language, str(path))
            
        except Exception as e:
            return SkillResult.fail(f"File scan failed: {str(e)}")
    
    async def scan_config(self, config: dict, config_type: str = "generic") -> SkillResult:
        """
        Scan configuration for security issues.
        
        Args:
            config: Configuration dictionary
            config_type: Type of config (docker, kubernetes, terraform, generic)
            
        Returns:
            SkillResult with config security analysis
        """
        try:
            scan_id = f"config_scan_{datetime.now(timezone.utc).strftime('%Y%m%d%H%M%S')}"
            vulnerabilities = []
            
            # Common config issues
            issues = []
            
            # Check for debug mode
            if config.get("debug", False) or config.get("DEBUG", False):
                issues.append(("Debug mode enabled", "medium", "Disable debug mode in production"))
            
            # Check for root/privileged
            if config.get("privileged", False) or config.get("runAsRoot", False):
                issues.append(("Privileged/root execution", "high", "Run as non-root user"))
            
            # Check for exposed ports
            ports = config.get("ports", []) or config.get("expose", [])
            if any(p in str(ports) for p in ["22", "3306", "5432", "27017"]):
                issues.append(("Sensitive port exposed", "medium", "Restrict access to sensitive ports"))
            
            # Check for missing resource limits
            if "resources" not in config and "limits" not in config:
                issues.append(("No resource limits", "low", "Set CPU and memory limits"))
            
            # Check for latest tag
            image = config.get("image", "")
            if ":latest" in image or (image and ":" not in image):
                issues.append(("Using 'latest' image tag", "medium", "Pin to specific image version"))
            
            for title, severity, recommendation in issues:
                vuln_id = f"config_{hashlib.md5(title.encode()).hexdigest()[:8]}"
                vulnerabilities.append(Vulnerability(
                    id=vuln_id,
                    severity=severity,
                    title=title,
                    description=f"Configuration issue: {title}",
                    recommendation=recommendation
                ))
            
            score = self._calculate_security_score(vulnerabilities)
            
            return SkillResult.ok({
                "scan_id": scan_id,
                "config_type": config_type,
                "issues_found": len(vulnerabilities),
                "security_score": score,
                "issues": [
                    {
                        "id": v.id,
                        "severity": v.severity,
                        "title": v.title,
                        "recommendation": v.recommendation
                    }
                    for v in vulnerabilities
                ],
                "scanned_at": datetime.now(timezone.utc).isoformat()
            })
            
        except Exception as e:
            return SkillResult.fail(f"Config scan failed: {str(e)}")
    
    async def check_dependencies(
        self,
        dependencies: dict[str, str],
        ecosystem: str = "python"
    ) -> SkillResult:
        """
        Check dependencies for known vulnerabilities.
        
        Args:
            dependencies: Dict of package: version
            ecosystem: Package ecosystem (python, npm, go)
            
        Returns:
            SkillResult with dependency analysis (simulated)
        """
        try:
            # This would integrate with vulnerability databases in production
            # For now, simulate some common vulnerable versions
            vulnerable_packages = {
                "python": {
                    "django": {"<2.2.24": "CVE-2021-33203", "<3.1.12": "CVE-2021-33203"},
                    "requests": {"<2.20.0": "CVE-2018-18074"},
                    "pyyaml": {"<5.4": "CVE-2020-14343"},
                },
                "npm": {
                    "lodash": {"<4.17.21": "CVE-2021-23337"},
                    "axios": {"<0.21.1": "CVE-2020-28168"},
                }
            }
            
            findings = []
            vuln_db = vulnerable_packages.get(ecosystem, {})
            
            for pkg, version in dependencies.items():
                if pkg.lower() in vuln_db:
                    for vuln_version, cve in vuln_db[pkg.lower()].items():
                        # Simple version check (production would use proper semver)
                        findings.append({
                            "package": pkg,
                            "installed_version": version,
                            "vulnerability": cve,
                            "severity": "high",
                            "recommendation": f"Upgrade {pkg} to latest version"
                        })
            
            return SkillResult.ok({
                "ecosystem": ecosystem,
                "packages_checked": len(dependencies),
                "vulnerable_packages": len(findings),
                "findings": findings,
                "checked_at": datetime.now(timezone.utc).isoformat(),
                "note": "This is a simulated check. Production should use actual vulnerability databases."
            })
            
        except Exception as e:
            return SkillResult.fail(f"Dependency check failed: {str(e)}")
    
    async def get_scan_history(self, limit: int = 10) -> SkillResult:
        """
        Get recent scan history.
        
        Args:
            limit: Maximum scans to return
            
        Returns:
            SkillResult with scan history
        """
        try:
            scans = sorted(
                self._scans.values(),
                key=lambda x: x.started_at,
                reverse=True
            )[:limit]
            
            return SkillResult.ok({
                "scans": [
                    {
                        "scan_id": s.scan_id,
                        "type": s.scan_type,
                        "target": s.target,
                        "vulnerabilities": len(s.vulnerabilities),
                        "started_at": s.started_at.isoformat()
                    }
                    for s in scans
                ],
                "total_scans": len(self._scans)
            })
            
        except Exception as e:
            return SkillResult.fail(f"History retrieval failed: {str(e)}")
    
    # === Private Helper Methods ===
    
    def _calculate_security_score(self, vulnerabilities: list[Vulnerability]) -> int:
        """Calculate security score (0-100, higher is better)."""
        if not vulnerabilities:
            return 100
        
        total_weight = sum(self.SEVERITY_WEIGHTS.get(v.severity, 0) for v in vulnerabilities)
        
        # Score decreases with more/worse vulnerabilities
        score = max(0, 100 - (total_weight * 5))
        return score
    
    def _count_by_severity(self, vulnerabilities: list[Vulnerability]) -> dict[str, int]:
        """Count vulnerabilities by severity."""
        counts = {"critical": 0, "high": 0, "medium": 0, "low": 0, "info": 0}
        for v in vulnerabilities:
            if v.severity in counts:
                counts[v.severity] += 1
        return counts
    
    def _get_recommendation(self, title: str) -> str:
        """Get recommendation for a vulnerability type."""
        recommendations = {
            "Use of eval()": "Avoid eval(). Use ast.literal_eval() for data parsing.",
            "Use of exec()": "Avoid exec(). Find safer alternatives.",
            "Shell Injection Risk": "Use subprocess with shell=False and list arguments.",
            "OS Command Execution": "Use subprocess module instead of os.system().",
            "Unsafe Deserialization": "Use json for data serialization instead of pickle.",
            "Potential SQL Injection": "Use parameterized queries or an ORM.",
            "Potential XSS via innerHTML": "Use textContent or sanitize HTML.",
            "Potential XSS via document.write": "Use DOM manipulation methods instead.",
        }
        return recommendations.get(title, "Review and address the security concern.")


# Skill instance factory
def create_skill(config: SkillConfig) -> SecurityScanSkill:
    """Create a security scan skill instance."""
    return SecurityScanSkill(config)

#!/usr/bin/env python3
# ruff: noqa
"""
Parse security scan reports and generate actionable summary.
Used by GitHub Actions security-scan workflow.
"""

import json
import sys
from pathlib import Path
from typing import Any


def parse_trivy_report(report_path: Path) -> dict[str, Any]:
    """Parse Trivy JSON report."""
    if not report_path.exists():
        return {"error": "Report not found", "vulnerabilities": []}

    try:
        with open(report_path, encoding="utf-8") as f:
            data = json.load(f)

        vulnerabilities: dict[str, list[dict[str, Any]]] = {
            "CRITICAL": [],
            "HIGH": [],
            "MEDIUM": [],
            "LOW": [],
        }

        for result in data.get("Results", []):
            for vuln in result.get("Vulnerabilities", []):
                severity = vuln.get("Severity", "UNKNOWN")
                if severity in vulnerabilities:
                    vulnerabilities[severity].append({
                        "id": vuln.get("VulnerabilityID"),
                        "package": vuln.get("PkgName"),
                        "version": vuln.get("InstalledVersion"),
                        "fixed_version": vuln.get("FixedVersion"),
                        "title": vuln.get("Title", ""),
                    })

        return {
            "total": sum(len(v) for v in vulnerabilities.values()),
            "critical": len(vulnerabilities["CRITICAL"]),
            "high": len(vulnerabilities["HIGH"]),
            "medium": len(vulnerabilities["MEDIUM"]),
            "low": len(vulnerabilities["LOW"]),
            "vulnerabilities": vulnerabilities,
        }
    except Exception as e:
        return {"error": str(e), "vulnerabilities": []}


def parse_bandit_report(report_path: Path) -> dict[str, Any]:
    """Parse Bandit JSON report."""
    if not report_path.exists():
        return {"error": "Report not found", "issues": 0}

    try:
        with open(report_path, encoding="utf-8") as f:
            data = json.load(f)

        issues_by_severity: dict[str, int] = {
            "HIGH": 0,
            "MEDIUM": 0,
            "LOW": 0,
        }

        for result in data.get("results", []):
            severity = result.get("issue_severity", "UNKNOWN")
            if severity in issues_by_severity:
                issues_by_severity[severity] += 1

        return {
            "total": len(data.get("results", [])),
            "high": issues_by_severity["HIGH"],
            "medium": issues_by_severity["MEDIUM"],
            "low": issues_by_severity["LOW"],
        }
    except Exception as e:
        return {"error": str(e), "issues": 0}


def parse_semgrep_report(report_path: Path) -> dict[str, Any]:
    """Parse Semgrep JSON report."""
    if not report_path.exists():
        return {"error": "Report not found", "findings": 0}

    try:
        with open(report_path, encoding="utf-8") as f:
            data = json.load(f)

        findings = data.get("results", [])
        return {
            "total": len(findings),
            "findings": [
                {
                    "id": f.get("check_id"),
                    "severity": f.get("extra", {}).get("severity", "UNKNOWN"),
                    "message": f.get("extra", {}).get("message", ""),
                    "file": f.get("path"),
                    "line": f.get("start", {}).get("line"),
                }
                for f in findings
            ],
        }
    except Exception as e:
        return {"error": str(e), "findings": 0}


def parse_npm_audit_report(report_path: Path) -> dict[str, Any]:
    """Parse npm audit JSON report."""
    if not report_path.exists():
        return {"error": "Report not found", "vulnerabilities": {}}

    try:
        with open(report_path, encoding="utf-8") as f:
            data = json.load(f)

        vulnerabilities = data.get("metadata", {}).get("vulnerabilities", {})
        return {
            "total": sum(vulnerabilities.values()),
            "critical": vulnerabilities.get("critical", 0),
            "high": vulnerabilities.get("high", 0),
            "moderate": vulnerabilities.get("moderate", 0),
            "low": vulnerabilities.get("low", 0),
        }
    except Exception as e:
        return {"error": str(e), "vulnerabilities": {}}


def parse_pip_audit_report(report_path: Path) -> dict[str, Any]:
    """Parse pip-audit JSON report."""
    if not report_path.exists():
        return {"error": "Report not found", "vulnerabilities": 0}

    try:
        with open(report_path, encoding="utf-8") as f:
            data = json.load(f)

        vulnerabilities = data.get("vulnerabilities", [])
        return {"total": len(vulnerabilities), "vulnerabilities": vulnerabilities}
    except Exception as e:
        return {"error": str(e), "vulnerabilities": 0}


def generate_summary(reports_dir: Path) -> dict[str, Any]:
    """Generate overall security summary from all reports."""
    backend_trivy = parse_trivy_report(
        reports_dir / "container-security-reports/backend-trivy-report.json"
    )
    frontend_trivy = parse_trivy_report(
        reports_dir / "container-security-reports/frontend-trivy-report.json"
    )
    bandit = parse_bandit_report(
        reports_dir / "backend-security-reports/bandit-report.json"
    )
    semgrep = parse_semgrep_report(
        reports_dir / "backend-security-reports/semgrep-report.json"
    )
    npm_audit = parse_npm_audit_report(
        reports_dir / "frontend-security-reports/npm-audit-report.json"
    )
    pip_audit = parse_pip_audit_report(
        reports_dir / "backend-security-reports/pip-audit-report.json"
    )

    return {
        "backend_container": backend_trivy,
        "frontend_container": frontend_trivy,
        "bandit": bandit,
        "semgrep": semgrep,
        "npm_audit": npm_audit,
        "pip_audit": pip_audit,
    }


def is_actionable(summary: dict[str, Any]) -> bool:
    """Determine if there are actionable security issues."""
    if summary["backend_container"].get("critical", 0) > 0:
        return True
    if summary["frontend_container"].get("critical", 0) > 0:
        return True
    if summary["bandit"].get("high", 0) > 0:
        return True
    if summary["npm_audit"].get("critical", 0) > 0:
        return True
    return summary["pip_audit"].get("total", 0) > 0


def format_markdown_summary(summary: dict[str, Any], run_id: str, sha: str) -> str:
    """Format summary as markdown for GitHub issue."""
    md = ["# Security Scan Summary", ""]
    md.append(
        f"**Workflow Run:** [{run_id}](https://github.com/${{GITHUB_REPOSITORY}}/actions/runs/{run_id})"
    )
    md.append(f"**Commit:** `{sha[:7]}`")
    md.append("")

    # Container Security
    md.append("## Container Security")
    md.append("")
    md.append("### Backend Container")
    backend = summary["backend_container"]
    if "error" not in backend:
        md.append(
            f"- **CRITICAL:** {backend['critical']} | **HIGH:** {backend['high']} | **MEDIUM:** {backend['medium']} | **LOW:** {backend['low']}"
        )
        md.append(f"- **Total vulnerabilities:** {backend['total']}")
    else:
        md.append(f"- Error: {backend['error']}")
    md.append("")

    md.append("### Frontend Container")
    frontend = summary["frontend_container"]
    if "error" not in frontend:
        md.append(
            f"- **CRITICAL:** {frontend['critical']} | **HIGH:** {frontend['high']} | **MEDIUM:** {frontend['medium']} | **LOW:** {frontend['low']}"
        )
        md.append(f"- **Total vulnerabilities:** {frontend['total']}")
    else:
        md.append(f"- Error: {frontend['error']}")
    md.append("")

    # Code Security
    md.append("## Code Security")
    md.append("")
    md.append("### Bandit (Python)")
    bandit = summary["bandit"]
    if "error" not in bandit:
        md.append(
            f"- **HIGH:** {bandit['high']} | **MEDIUM:** {bandit['medium']} | **LOW:** {bandit['low']}"
        )
        md.append(f"- **Total issues:** {bandit['total']}")
    else:
        md.append(f"- Error: {bandit['error']}")
    md.append("")

    md.append("### Semgrep")
    semgrep = summary["semgrep"]
    if "error" not in semgrep:
        md.append(f"- **Total findings:** {semgrep['total']}")
        if semgrep["total"] > 0:
            md.append("- **Findings:**")
            md.extend(
                f"  - `{finding['file']}:{finding['line']}` - {finding['severity']}: {finding['message'][:80]}"
                for finding in semgrep["findings"][:5]
            )
            if semgrep["total"] > 5:
                md.append(f"  - ... and {semgrep['total'] - 5} more")
    else:
        md.append(f"- Error: {semgrep['error']}")
    md.append("")

    # Dependency Security
    md.append("## Dependency Security")
    md.append("")
    md.append("### npm audit (Frontend)")
    npm = summary["npm_audit"]
    if "error" not in npm:
        md.append(
            f"- **CRITICAL:** {npm['critical']} | **HIGH:** {npm['high']} | **MODERATE:** {npm['moderate']} | **LOW:** {npm['low']}"
        )
        md.append(f"- **Total vulnerabilities:** {npm['total']}")
    else:
        md.append(f"- Error: {npm['error']}")
    md.append("")

    md.append("### pip-audit (Backend)")
    pip = summary["pip_audit"]
    if "error" not in pip:
        md.append(f"- **Total vulnerabilities:** {pip['total']}")
    else:
        md.append(f"- Error: {pip['error']}")
    md.append("")

    # Recommendations
    if is_actionable(summary):
        md.append("## Action Required")
        md.append("")
        if summary["backend_container"].get("critical", 0) > 0:
            md.append(
                f"- ⚠️ **{summary['backend_container']['critical']} CRITICAL vulnerabilities** in backend container"
            )
        if summary["frontend_container"].get("critical", 0) > 0:
            md.append(
                f"- ⚠️ **{summary['frontend_container']['critical']} CRITICAL vulnerabilities** in frontend container"
            )
        if summary["bandit"].get("high", 0) > 0:
            md.append(
                f"- ⚠️ **{summary['bandit']['high']} HIGH severity issues** in Python code"
            )
        if summary["npm_audit"].get("critical", 0) > 0:
            md.append(
                f"- ⚠️ **{summary['npm_audit']['critical']} CRITICAL vulnerabilities** in npm dependencies"
            )
        if summary["pip_audit"].get("total", 0) > 0:
            md.append(
                f"- ⚠️ **{summary['pip_audit']['total']} vulnerabilities** in Python dependencies"
            )
        md.append("")
        md.append(
            "**Note:** Not all reported vulnerabilities may be exploitable in this context. Review the detailed reports to distinguish between runtime risks and build-time dependencies."
        )
    else:
        md.append("## Status")
        md.append("")
        md.append(
            "✅ No critical or high-severity actionable vulnerabilities detected."
        )
        md.append("")
        md.append(
            "**Note:** Some informational findings may exist. Download the full reports for details."
        )

    return "\n".join(md)


def main() -> None:
    if len(sys.argv) < 4:
        print(
            "Usage: parse-security-reports.py <reports_dir> <run_id> <sha>",
            file=sys.stderr,
        )
        sys.exit(1)

    reports_dir = Path(sys.argv[1])
    run_id = sys.argv[2]
    sha = sys.argv[3]

    if not reports_dir.exists():
        print(f"Reports directory not found: {reports_dir}", file=sys.stderr)
        sys.exit(1)

    summary = generate_summary(reports_dir)

    print(json.dumps(summary, indent=2))
    md_summary = format_markdown_summary(summary, run_id, sha)

    with open("security-summary.md", "w", encoding="utf-8") as f:
        f.write(md_summary)

    sys.exit(1 if is_actionable(summary) else 0)


if __name__ == "__main__":
    main()

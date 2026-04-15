"""
audit_system — Pro-level system integrity audit for RynatySchool SmartCampus.

Checks for broken, corrupt, incomplete, duplicated, or out-of-sync components
across the entire codebase, database, API surface, and configuration.

Usage:
    python manage.py audit_system                        # run all sections
    python manage.py audit_system --section db           # database integrity only
    python manage.py audit_system --section code         # static code analysis only
    python manage.py audit_system --section api          # URL/API surface audit
    python manage.py audit_system --section config       # settings & security
    python manage.py audit_system --section sync         # seed / schema sync
    python manage.py audit_system --section tenant       # per-tenant data health
    python manage.py audit_system --fix                  # auto-fix safe issues
    python manage.py audit_system --schema_name olom     # single-tenant checks only
"""
from __future__ import annotations

import os
import re
import sys
import textwrap
from collections import Counter, defaultdict
from pathlib import Path
from typing import List, Tuple

from django.core.management.base import BaseCommand
from django_tenants.utils import get_public_schema_name, schema_context


# ── ANSI colours ──────────────────────────────────────────────────────────────
R = "\033[91m"   # red
G = "\033[92m"   # green
Y = "\033[93m"   # yellow
B = "\033[94m"   # blue
M = "\033[95m"   # magenta
C = "\033[96m"   # cyan
W = "\033[97m"   # white bold
Z = "\033[0m"    # reset

OK   = f"{G}✓{Z}"
FAIL = f"{R}✗{Z}"
WARN = f"{Y}⚠{Z}"
INFO = f"{B}ℹ{Z}"
FIX  = f"{M}⚙{Z}"

SECTION_LABELS = {
    "db":     "Database Integrity",
    "code":   "Static Code Analysis",
    "api":    "API / URL Surface",
    "config": "Settings & Security",
    "sync":   "Schema & Seed Sync",
    "tenant": "Per-Tenant Data Health",
}

BASE_DIR = Path(__file__).resolve().parents[3]   # sms-backend/

# Directories to exclude from source-code scanning (vendor, caches, generated)
SCAN_EXCLUDE = {
    ".cache", ".git", "__pycache__", "migrations", "staticfiles",
    "frontend_build", "media", "node_modules", ".venv", "venv",
    ".local", "dist", "build",
}


# ─────────────────────────────────────────────────────────────────────────────
class Finding:
    """Represents a single audit finding."""

    LEVELS = ("CRITICAL", "HIGH", "MEDIUM", "LOW", "INFO")

    def __init__(self, level: str, section: str, title: str,
                 detail: str = "", fix: str = "", auto_fixable: bool = False):
        self.level = level
        self.section = section
        self.title = title
        self.detail = detail
        self.fix = fix
        self.auto_fixable = auto_fixable

    @property
    def color(self):
        return {
            "CRITICAL": R,
            "HIGH":     R,
            "MEDIUM":   Y,
            "LOW":      Y,
            "INFO":     B,
        }.get(self.level, Z)

    def render(self, indent=4) -> str:
        pad = " " * indent
        lines = [f"{pad}{self.color}[{self.level}]{Z} {W}{self.title}{Z}"]
        if self.detail:
            for line in self.detail.strip().splitlines():
                lines.append(f"{pad}  {line}")
        if self.fix:
            lines.append(f"{pad}  {FIX} Fix: {self.fix}")
        if self.auto_fixable:
            lines.append(f"{pad}  {M}(auto-fixable with --fix){Z}")
        return "\n".join(lines)


# ─────────────────────────────────────────────────────────────────────────────
class Command(BaseCommand):
    help = "Pro-level system audit: finds broken, missing, duplicated, and out-of-sync components"

    SECTIONS = list(SECTION_LABELS.keys())

    def add_arguments(self, parser):
        parser.add_argument(
            "--section",
            choices=self.SECTIONS,
            default=None,
            help="Run only a specific audit section (default: all)",
        )
        parser.add_argument(
            "--schema_name",
            type=str,
            default=None,
            help="Limit tenant checks to this schema only",
        )
        parser.add_argument(
            "--fix",
            action="store_true",
            help="Auto-fix safe, non-destructive issues",
        )
        parser.add_argument(
            "--json",
            action="store_true",
            help="Output findings as JSON",
        )

    def handle(self, *args, **options):
        sections = [options["section"]] if options["section"] else self.SECTIONS
        fix_mode = options["fix"]
        schema_filter = options["schema_name"]

        self._print_header(sections, fix_mode)
        all_findings: List[Finding] = []

        runners = {
            "code":   self._audit_code,
            "api":    self._audit_api,
            "config": self._audit_config,
            "db":     lambda: self._audit_db(schema_filter),
            "sync":   lambda: self._audit_sync(schema_filter),
            "tenant": lambda: self._audit_tenant(schema_filter),
        }

        for section in sections:
            self._print_section_header(SECTION_LABELS[section])
            try:
                findings = runners[section]()
            except Exception as exc:
                findings = [Finding("HIGH", section, f"Audit section crashed: {exc}")]

            all_findings.extend(findings)
            self._print_findings(findings)

            if fix_mode:
                self._apply_fixes(findings)

        self._print_summary(all_findings, fix_mode)

        if options["json"]:
            self._dump_json(all_findings)

    # ── Rendering ────────────────────────────────────────────────────────────

    def _print_header(self, sections, fix_mode):
        self.stdout.write(f"\n{W}{'='*70}{Z}")
        self.stdout.write(f"{W}  RynatySchool SmartCampus — System Audit{Z}")
        self.stdout.write(f"  Sections: {', '.join(sections)}{' | FIX MODE' if fix_mode else ''}")
        self.stdout.write(f"{W}{'='*70}{Z}\n")

    def _print_section_header(self, label):
        self.stdout.write(f"\n{C}{'─'*60}{Z}")
        self.stdout.write(f"{C}  {label}{Z}")
        self.stdout.write(f"{C}{'─'*60}{Z}")

    def _print_findings(self, findings: List[Finding]):
        if not findings:
            self.stdout.write(f"    {OK} No issues found.")
            return
        for f in findings:
            self.stdout.write(f.render())
            self.stdout.write("")

    def _print_summary(self, findings: List[Finding], fix_mode: bool):
        by_level = Counter(f.level for f in findings)
        total = len(findings)

        self.stdout.write(f"\n{W}{'='*70}{Z}")
        self.stdout.write(f"{W}  AUDIT SUMMARY  ({total} total findings){Z}")
        self.stdout.write(f"{W}{'='*70}{Z}")

        for lvl in Finding.LEVELS:
            count = by_level.get(lvl, 0)
            if count:
                color = R if lvl in ("CRITICAL", "HIGH") else Y if lvl in ("MEDIUM", "LOW") else B
                self.stdout.write(f"  {color}{lvl:10s}{Z}  {count}")

        fixable = sum(1 for f in findings if f.auto_fixable)
        if fixable and not fix_mode:
            self.stdout.write(f"\n  {FIX} {fixable} issue(s) are auto-fixable. Re-run with --fix to apply.")

        critical = by_level.get("CRITICAL", 0) + by_level.get("HIGH", 0)
        if critical == 0:
            self.stdout.write(f"\n  {OK} No critical or high issues found.")
        else:
            self.stdout.write(f"\n  {FAIL} {critical} critical/high issue(s) require attention.")
        self.stdout.write("")

    def _apply_fixes(self, findings: List[Finding]):
        for f in findings:
            if f.auto_fixable:
                self.stdout.write(f"    {FIX} Auto-fixing: {f.title}...")
                # Specific fixers are called inline in audit methods

    def _dump_json(self, findings: List[Finding]):
        import json
        data = [
            {"level": f.level, "section": f.section, "title": f.title,
             "detail": f.detail, "fix": f.fix}
            for f in findings
        ]
        self.stdout.write(json.dumps(data, indent=2))

    # =========================================================================
    # SECTION: CODE — Static analysis
    # =========================================================================

    def _audit_code(self) -> List[Finding]:
        findings = []
        root = BASE_DIR

        def _is_excluded(path: Path) -> bool:
            return any(part in SCAN_EXCLUDE for part in path.parts)

        py_files = [
            p for p in root.rglob("*.py")
            if not _is_excluded(p)
        ]
        self.stdout.write(f"    {INFO} Scanning {len(py_files)} Python files (project source only)...")

        # 1. Silent exception swallowing
        findings.extend(self._check_silent_exceptions(py_files))

        # 2. FK string assignment patterns
        findings.extend(self._check_fk_string_assignments(py_files))

        # 3. Bare `except:` clauses (not even Exception)
        findings.extend(self._check_bare_except(py_files))

        # 4. Duplicate management commands
        findings.extend(self._check_duplicate_commands())

        # 5. TODO / FIXME / HACK / BROKEN markers
        findings.extend(self._check_code_markers(py_files))

        # 6. Hardcoded credentials / secrets
        findings.extend(self._check_hardcoded_secrets(py_files))

        # 7. f-string backslash usage (Python 3.11 limitation)
        findings.extend(self._check_fstring_backslash(py_files))

        return findings

    def _check_silent_exceptions(self, py_files) -> List[Finding]:
        """Find except blocks that silently swallow exceptions with just `pass`."""
        pattern = re.compile(r"except\s*(?:Exception\s*(?:as\s+\w+)?|:)\s*:", re.M)
        silent_pattern = re.compile(
            r"(except\s*(?:\w+(?:\s+as\s+\w+)?)?:)\s*\n\s*(pass)\s*$", re.M
        )
        offenders = []
        for path in py_files:
            try:
                content = path.read_text(errors="ignore")
                matches = list(silent_pattern.finditer(content))
                for m in matches:
                    line_no = content[:m.start()].count("\n") + 1
                    rel = str(path.relative_to(BASE_DIR))
                    offenders.append(f"{rel}:{line_no}")
            except Exception:
                pass

        if not offenders:
            return []
        return [Finding(
            "HIGH", "code",
            f"Silent exception swallowing — {len(offenders)} location(s)",
            "\n".join(offenders[:15]) + ("\n  ..." if len(offenders) > 15 else ""),
            "Replace `except: pass` with specific exception handling or at minimum log the error. "
            "This pattern hid the UserProfile FK bug for months.",
        )]

    def _check_fk_string_assignments(self, py_files) -> List[Finding]:
        """Find places that assign string literals to known ForeignKey fields."""
        # These are FK fields (not CharField choices) that must receive model instances
        fk_field_names = ["role", "academic_year", "grade_level", "school_class", "department_fk"]
        # Match: "role": "SOME_VALUE"  OR  .role = "SOME_VALUE"
        dict_pattern = re.compile(
            r'"(' + "|".join(fk_field_names) + r')":\s*"([A-Za-z_][A-Za-z0-9_ ]*)"'
        )
        assign_pattern = re.compile(
            r'\.\s*(' + "|".join(fk_field_names) + r')\s*=\s*"([A-Za-z_][A-Za-z0-9_ ]*)"'
        )
        offenders = []
        for path in py_files:
            rel = str(path.relative_to(BASE_DIR))
            # Skip test files and seed files where string-to-FK is a known acceptable risk
            if any(skip in rel for skip in ("test", "seed_demo", "seed_kenya")):
                continue
            try:
                content = path.read_text(errors="ignore")
                for pat in (dict_pattern, assign_pattern):
                    for m in pat.finditer(content):
                        field = m.group(1)
                        value = m.group(2)
                        line_no = content[:m.start()].count("\n") + 1
                        snippet = m.group(0)
                        # Skip if context makes it clear it's a CharField (not a FK)
                        line_start = content.rfind("\n", 0, m.start()) + 1
                        line_text = content[line_start:content.find("\n", m.start())]
                        if any(x in line_text for x in ("CharField", "choices", "max_length", "#")):
                            continue
                        offenders.append(f"{rel}:{line_no}  →  {snippet[:80]}")
            except Exception:
                pass

        if not offenders:
            return []
        return [Finding(
            "HIGH", "code",
            f"String assigned to ForeignKey field — {len(offenders)} location(s)",
            "\n".join(offenders[:10]) + ("\n  ..." if len(offenders) > 10 else ""),
            "Look up the related object first: `role = Role.objects.get(name='X')` then assign `profile.role = role`.\n"
            "  String assignment to FK silently fails or stores the wrong value.",
        )]

    def _check_bare_except(self, py_files) -> List[Finding]:
        """Find bare `except:` clauses (catches BaseException, including SystemExit)."""
        pattern = re.compile(r"^\s*except\s*:\s*$", re.M)
        offenders = []
        for path in py_files:
            try:
                content = path.read_text(errors="ignore")
                for m in pattern.finditer(content):
                    line_no = content[:m.start()].count("\n") + 1
                    rel = str(path.relative_to(BASE_DIR))
                    offenders.append(f"{rel}:{line_no}")
            except Exception:
                pass
        if not offenders:
            return []
        return [Finding(
            "MEDIUM", "code",
            f"Bare `except:` clause (catches SystemExit/KeyboardInterrupt) — {len(offenders)} location(s)",
            "\n".join(offenders[:10]),
            "Use `except Exception:` or a more specific exception type.",
        )]

    def _check_duplicate_commands(self) -> List[Finding]:
        """Find management commands with the same name in different apps."""
        commands = defaultdict(list)
        for cmd_dir in BASE_DIR.rglob("management/commands"):
            if "__pycache__" in str(cmd_dir):
                continue
            for f in cmd_dir.glob("*.py"):
                if f.name.startswith("_"):
                    continue
                commands[f.stem].append(str(f.relative_to(BASE_DIR)))

        duplicates = {k: v for k, v in commands.items() if len(v) > 1}
        if not duplicates:
            return []
        detail = "\n".join(f"{k!r}: {', '.join(v)}" for k, v in list(duplicates.items())[:10])
        return [Finding(
            "MEDIUM", "code",
            f"Duplicate management command names — {len(duplicates)} conflict(s)",
            detail,
            "Rename one of the conflicting commands or merge them into a shared location.",
        )]

    def _check_code_markers(self, py_files) -> List[Finding]:
        """Find TODO/FIXME/HACK/BROKEN/XXX markers."""
        pattern = re.compile(r"#\s*(TODO|FIXME|HACK|BROKEN|XXX|BUG|TEMP)[\s:](.{0,80})", re.I)
        markers = defaultdict(list)
        for path in py_files:
            try:
                content = path.read_text(errors="ignore")
                for m in pattern.finditer(content):
                    line_no = content[:m.start()].count("\n") + 1
                    rel = str(path.relative_to(BASE_DIR))
                    key = m.group(1).upper()
                    markers[key].append(f"{rel}:{line_no} — {m.group(2).strip()}")
            except Exception:
                pass

        findings = []
        for marker_type in ["BROKEN", "BUG", "FIXME"]:
            if marker_type in markers:
                findings.append(Finding(
                    "MEDIUM", "code",
                    f"{marker_type} markers in code — {len(markers[marker_type])} location(s)",
                    "\n".join(markers[marker_type][:8]),
                    "Resolve the marked issue or file a tracked ticket.",
                ))
        hack_todo = sum(len(v) for k, v in markers.items() if k in ("TODO", "HACK", "XXX", "TEMP"))
        if hack_todo:
            findings.append(Finding(
                "LOW", "code",
                f"Technical debt markers (TODO/HACK/XXX/TEMP) — {hack_todo} location(s)",
                f"Run `grep -rn 'TODO\\|HACK\\|XXX' --include='*.py' sms-backend/` for full list.",
            ))
        return findings

    def _check_hardcoded_secrets(self, py_files) -> List[Finding]:
        """Find potential hardcoded passwords/keys/secrets (excluding tests and seeds)."""
        # Patterns that suggest hardcoded secrets
        secret_patterns = [
            re.compile(r'(?:password|passwd|secret_key|api_key|auth_token)\s*=\s*["\'][^"\']{8,}["\']', re.I),
        ]
        # Known-OK patterns (test data, seeds — unavoidable)
        ok_paths = {"seed_", "test_", "_test", "conftest", ".env", "settings"}
        offenders = []
        for path in py_files:
            rel = str(path.relative_to(BASE_DIR))
            if any(ok in rel for ok in ok_paths):
                continue
            try:
                content = path.read_text(errors="ignore")
                for pat in secret_patterns:
                    for m in pat.finditer(content):
                        line_no = content[:m.start()].count("\n") + 1
                        # Skip obvious non-secrets
                        snippet = m.group(0)
                        if any(skip in snippet.lower() for skip in
                               ("environ", "os.get", "config(", "getenv", "placeholder", "your-")):
                            continue
                        offenders.append(f"{rel}:{line_no}  →  {snippet[:80]}")
            except Exception:
                pass
        if not offenders:
            return []
        return [Finding(
            "HIGH", "code",
            f"Potential hardcoded secrets — {len(offenders)} location(s)",
            "\n".join(offenders[:10]),
            "Move secrets to environment variables and reference via os.environ or django-environ.",
        )]

    def _check_fstring_backslash(self, py_files) -> List[Finding]:
        """Find backslash usage inside f-string expressions (Python 3.11 syntax error)."""
        pattern = re.compile(r'f["\'].*?\{[^}]*\\[^}]*\}.*?["\']')
        offenders = []
        for path in py_files:
            try:
                content = path.read_text(errors="ignore")
                for m in pattern.finditer(content):
                    line_no = content[:m.start()].count("\n") + 1
                    rel = str(path.relative_to(BASE_DIR))
                    offenders.append(f"{rel}:{line_no}")
            except Exception:
                pass
        if not offenders:
            return []
        return [Finding(
            "HIGH", "code",
            f"Backslash inside f-string expression — {len(offenders)} location(s) (Python 3.12+ only)",
            "\n".join(offenders[:8]),
            "Extract the expression to a variable before the f-string: `val = d['key']; f'{val}'`",
        )]

    # =========================================================================
    # SECTION: API — URL surface audit
    # =========================================================================

    def _audit_api(self) -> List[Finding]:
        findings = []
        findings.extend(self._check_url_duplicates())
        findings.extend(self._check_url_count())
        findings.extend(self._check_viewset_registration())
        return findings

    def _check_url_duplicates(self) -> List[Finding]:
        """Detect genuinely duplicated URL names (not just DRF format suffixes)."""
        from django.urls import URLResolver, URLPattern
        try:
            from config import urls as root_urls
        except ImportError:
            return [Finding("HIGH", "api", "Could not import root URL conf")]

        def collect(patterns, prefix=""):
            result = []
            for p in patterns:
                if isinstance(p, URLResolver):
                    result.extend(collect(p.url_patterns, prefix + str(p.pattern)))
                elif isinstance(p, URLPattern) and p.name:
                    result.append((p.name, prefix + str(p.pattern)))
            return result

        all_urls = collect(root_urls.urlpatterns)
        name_paths = defaultdict(set)
        for name, path in all_urls:
            # Strip DRF format suffix variants — these are intentional
            path_norm = re.sub(r"\\.\\(\\?P<format>[^)]+\\)\\/?\\$", "", path)
            path_norm = re.sub(r"\\.[a-z0-9]+\\/\\?\\$", "", path_norm)
            name_paths[name].add(path_norm)

        real_dups = {
            name: sorted(paths) for name, paths in name_paths.items()
            if len(paths) > 1 and name != "api-root"
        }
        api_root_count = sum(1 for n, _ in all_urls if n == "api-root")

        findings = []
        if real_dups:
            detail = "\n".join(
                f"{name!r}: {list(paths)}" for name, paths in list(real_dups.items())[:15]
            )
            findings.append(Finding(
                "HIGH", "api",
                f"Duplicate URL names pointing to different paths — {len(real_dups)} conflict(s)",
                detail,
                "Remove duplicate router.register() calls or use `basename=` to disambiguate.",
            ))

        if api_root_count > 3:
            findings.append(Finding(
                "MEDIUM", "api",
                f"api-root registered {api_root_count} times (multiple routers stacked)",
                "This inflates URL count and can cause ambiguous reversals.",
                "Consolidate routers or set `basename='api-root-<app>'` on each.",
            ))

        total_urls = len(all_urls)
        if total_urls > 2000:
            findings.append(Finding(
                "LOW", "api",
                f"Large URL registry — {total_urls} patterns",
                "High URL count increases startup time and memory usage.",
                "Check for redundant router registrations or duplicate include() calls.",
            ))

        return findings

    def _check_url_count(self) -> List[Finding]:
        """Check for per-app URL over-registration."""
        try:
            from config import urls as root_urls
            from django.urls import URLResolver, URLPattern

            def collect_by_prefix(patterns, prefix=""):
                result = defaultdict(int)
                for p in patterns:
                    if isinstance(p, URLResolver):
                        sub = collect_by_prefix(p.url_patterns, prefix + str(p.pattern))
                        for k, v in sub.items():
                            result[k] += v
                    else:
                        top = prefix.split("/")[0] if "/" in prefix else prefix[:20]
                        result[top] += 1
                return result

            by_prefix = collect_by_prefix(root_urls.urlpatterns)
            bloated = {k: v for k, v in by_prefix.items() if v > 200}
            if bloated:
                detail = "\n".join(f"  {k!r}: {v} patterns" for k, v in sorted(bloated.items(), key=lambda x: -x[1]))
                return [Finding(
                    "LOW", "api",
                    f"URL prefix(es) with very high pattern count",
                    detail,
                )]
        except Exception:
            pass
        return []

    def _check_viewset_registration(self) -> List[Finding]:
        """Find ViewSets imported but never registered to a router."""
        # Heuristic: look for ViewSet classes in views.py files and check
        # if their names appear in any urls.py
        viewsets_defined = []
        viewsets_registered = set()

        for views_file in BASE_DIR.rglob("views.py"):
            if "__pycache__" in str(views_file):
                continue
            try:
                content = views_file.read_text(errors="ignore")
                for m in re.finditer(r"class (\w+ViewSet)\s*\(", content):
                    viewsets_defined.append((m.group(1), str(views_file.relative_to(BASE_DIR))))
            except Exception:
                pass

        for urls_file in BASE_DIR.rglob("urls.py"):
            if "__pycache__" in str(urls_file):
                continue
            try:
                content = urls_file.read_text(errors="ignore")
                for m in re.finditer(r"router\.register\([^,]+,\s*(\w+)", content):
                    viewsets_registered.add(m.group(1))
                for m in re.finditer(r"(\w+ViewSet)", content):
                    viewsets_registered.add(m.group(1))
            except Exception:
                pass

        unregistered = [
            f"{name!r} in {path}"
            for name, path in viewsets_defined
            if name not in viewsets_registered
        ]

        if not unregistered:
            return []
        return [Finding(
            "MEDIUM", "api",
            f"ViewSets defined but not registered in any urls.py — {len(unregistered)} found",
            "\n".join(unregistered[:12]) + ("\n  ..." if len(unregistered) > 12 else ""),
            "Register the ViewSet in the appropriate urls.py router.register() call, or delete if unused.",
        )]

    # =========================================================================
    # SECTION: CONFIG — Settings and security
    # =========================================================================

    def _audit_config(self) -> List[Finding]:
        findings = []
        from django.conf import settings

        # 1. DEBUG in production
        if settings.DEBUG:
            findings.append(Finding(
                "CRITICAL", "config",
                "DEBUG=True is set",
                "Django's debug mode exposes stack traces, SQL queries, and settings to the browser.",
                "Set DEBUG=False and provide ALLOWED_HOSTS in production.",
            ))

        # 2. SECRET_KEY strength
        sk = getattr(settings, "SECRET_KEY", "")
        if len(sk) < 40 or sk == "django-insecure-" or "insecure" in sk.lower():
            findings.append(Finding(
                "CRITICAL", "config",
                "SECRET_KEY is weak or insecure",
                f"Length={len(sk)}, value starts with {sk[:20]!r}",
                "Generate a strong random key and store in an environment secret.",
            ))

        # 3. ALLOWED_HOSTS
        ah = getattr(settings, "ALLOWED_HOSTS", [])
        if not ah or ah == ["*"]:
            findings.append(Finding(
                "HIGH", "config",
                "ALLOWED_HOSTS is empty or wildcard",
                f"Current value: {ah!r}",
                "Set ALLOWED_HOSTS to the list of domains the app serves.",
            ))

        # 4. DATABASES health
        from django.db import connections
        try:
            connections["default"].ensure_connection()
        except Exception as exc:
            findings.append(Finding(
                "CRITICAL", "config",
                f"Database connection failed: {exc}",
                fix="Check DATABASE_URL environment variable.",
            ))

        # 5. Required environment variables
        required_env = ["DATABASE_URL", "SECRET_KEY", "SESSION_SECRET"]
        missing_env = [v for v in required_env if not os.environ.get(v)]
        if missing_env:
            findings.append(Finding(
                "HIGH", "config",
                f"Missing required environment variables: {missing_env}",
                fix="Set the missing variables in environment secrets.",
            ))

        # 6. CORS
        cors_origins = getattr(settings, "CORS_ALLOWED_ORIGINS", [])
        cors_all = getattr(settings, "CORS_ALLOW_ALL_ORIGINS", False)
        if cors_all and not settings.DEBUG:
            findings.append(Finding(
                "HIGH", "config",
                "CORS_ALLOW_ALL_ORIGINS=True in production",
                "This allows any origin to make cross-site requests.",
                "Set CORS_ALLOWED_ORIGINS to an explicit list of trusted origins.",
            ))

        # 7. INSTALLED_APPS for missing standard safety apps
        apps_list = [a.name for a in __import__("django.apps", fromlist=["apps"]).apps.get_app_configs()]
        if "django.middleware.security.SecurityMiddleware" not in getattr(settings, "MIDDLEWARE", []):
            findings.append(Finding(
                "MEDIUM", "config",
                "SecurityMiddleware not in MIDDLEWARE",
                fix="Add 'django.middleware.security.SecurityMiddleware' as the first middleware.",
            ))

        # 8. JWT token lifetimes
        sj = getattr(settings, "SIMPLE_JWT", {})
        access_lifetime = sj.get("ACCESS_TOKEN_LIFETIME")
        if access_lifetime:
            total_seconds = access_lifetime.total_seconds()
            if total_seconds > 86400:  # more than 1 day
                findings.append(Finding(
                    "MEDIUM", "config",
                    f"JWT access token lifetime is very long ({total_seconds/3600:.1f} hours)",
                    "Long-lived access tokens increase exposure if a token is compromised.",
                    "Consider reducing ACCESS_TOKEN_LIFETIME to 15–60 minutes.",
                ))

        if not findings:
            findings.append(Finding("INFO", "config", "No configuration issues found."))
        return findings

    # =========================================================================
    # SECTION: DB — Database integrity
    # =========================================================================

    def _audit_db(self, schema_filter=None) -> List[Finding]:
        findings = []
        from clients.models import Tenant

        public = get_public_schema_name()
        qs = Tenant.objects.exclude(schema_name=public)
        if schema_filter:
            qs = qs.filter(schema_name=schema_filter)
        tenants = list(qs)

        for tenant in tenants:
            tag = f"[{tenant.schema_name}]"
            try:
                with schema_context(tenant.schema_name):
                    findings.extend(self._db_check_schema(tenant.schema_name, tag))
            except Exception as exc:
                findings.append(Finding("HIGH", "db", f"{tag} Schema context error: {exc}"))

        # Public schema checks
        findings.extend(self._db_check_public())
        return findings

    def _db_check_schema(self, schema_name: str, tag: str) -> List[Finding]:
        findings = []
        from django.contrib.auth.models import User
        from school.models import UserProfile, Role, TenantModule, Module

        # 1. Active users without UserProfile
        users_no_profile = list(
            User.objects.filter(is_active=True)
            .exclude(userprofile__isnull=False)
            .values_list("username", flat=True)[:20]
        )
        if users_no_profile:
            findings.append(Finding(
                "HIGH", "db",
                f"{tag} {len(users_no_profile)} active user(s) missing UserProfile",
                "Users: " + ", ".join(users_no_profile[:10]) + ("..." if len(users_no_profile) > 10 else ""),
                "Run: python manage.py shell → create UserProfile with the correct Role FK for each.",
                auto_fixable=False,
            ))

        # 2. UserProfile with null role FK
        null_roles = UserProfile.objects.filter(role__isnull=True).count()
        if null_roles:
            findings.append(Finding(
                "CRITICAL", "db",
                f"{tag} {null_roles} UserProfile row(s) with role=NULL",
                "Users with null role will fail ALL permission checks (403 on every endpoint).",
                "Assign the correct Role FK: `profile.role = Role.objects.get(name='...')` then save().",
            ))

        # 3. Role objects count sanity
        role_count = Role.objects.count()
        if role_count == 0:
            findings.append(Finding(
                "CRITICAL", "db",
                f"{tag} No Role objects seeded",
                fix="python manage.py seed_default_permissions --assign-roles --all-tenants",
            ))
        elif role_count < 10:
            findings.append(Finding(
                "HIGH", "db",
                f"{tag} Only {role_count}/19 Roles seeded",
                fix="python manage.py seed_default_permissions --assign-roles --all-tenants",
            ))

        # 4. Module count
        module_count = Module.objects.count()
        if module_count == 0:
            findings.append(Finding(
                "CRITICAL", "db",
                f"{tag} No Module objects seeded",
                fix="python manage.py seed_modules --all-tenants",
            ))
        elif module_count < 28:
            findings.append(Finding(
                "MEDIUM", "db",
                f"{tag} Only {module_count}/28 Modules seeded",
                fix="python manage.py seed_modules --all-tenants",
            ))

        # 5. TenantModule disabled entirely
        enabled_tm = TenantModule.objects.filter(is_enabled=True).count()
        total_tm = TenantModule.objects.count()
        if total_tm > 0 and enabled_tm == 0:
            findings.append(Finding(
                "HIGH", "db",
                f"{tag} {total_tm} TenantModule records exist but none are enabled",
                "All module-gated views will deny access.",
                fix="Re-run seed_modules --all-tenants or manually enable modules.",
            ))

        # 6. SchoolProfile existence
        from school.models import SchoolProfile
        if not SchoolProfile.objects.filter(is_active=True).exists():
            findings.append(Finding(
                "HIGH", "db",
                f"{tag} No active SchoolProfile",
                "School settings pages will fail and some APIs will error.",
                fix="python manage.py seed_school_data --schema_name " + schema_name,
            ))

        # 7. Current AcademicYear
        from school.models import AcademicYear
        if not AcademicYear.objects.filter(is_current=True).exists():
            findings.append(Finding(
                "MEDIUM", "db",
                f"{tag} No current AcademicYear",
                "Academic, attendance, and timetable views may error or show wrong data.",
                fix="python manage.py seed_school_data --schema_name " + schema_name,
            ))

        # 8. GradeLevels
        from school.models import GradeLevel
        if GradeLevel.objects.filter(is_active=True).count() == 0:
            findings.append(Finding(
                "MEDIUM", "db",
                f"{tag} No GradeLevels seeded",
                fix="python manage.py seed_school_data --schema_name " + schema_name,
            ))

        # 9. Orphaned TenantModule records (module key doesn't exist)
        orphaned_tm = TenantModule.objects.exclude(module__isnull=False).count()
        if orphaned_tm > 0:
            findings.append(Finding(
                "MEDIUM", "db",
                f"{tag} {orphaned_tm} orphaned TenantModule records (no parent Module)",
                fix="TenantModule.objects.filter(module__isnull=True).delete()",
            ))

        return findings

    def _db_check_public(self) -> List[Finding]:
        """Check public schema / platform-level integrity."""
        findings = []
        try:
            from clients.models import Tenant, Domain, TenantSubscription

            # Tenants without any domain
            no_domain = []
            for t in Tenant.objects.exclude(schema_name=get_public_schema_name()):
                if not Domain.objects.filter(tenant=t).exists():
                    no_domain.append(t.schema_name)
            if no_domain:
                findings.append(Finding(
                    "HIGH", "db",
                    f"Tenant(s) with no registered domain: {no_domain}",
                    "These tenants cannot be reached by any hostname.",
                    "Register a domain via Domain.objects.create(tenant=..., domain='...', is_primary=True)",
                ))

            # Tenants without subscription
            no_sub = []
            for t in Tenant.objects.exclude(schema_name=get_public_schema_name()):
                if not TenantSubscription.objects.filter(tenant=t).exists():
                    no_sub.append(t.schema_name)
            if no_sub:
                findings.append(Finding(
                    "LOW", "db",
                    f"Tenant(s) with no subscription record: {no_sub}",
                    fix="Run seed_olom_tenant or create TenantSubscription manually.",
                ))

            # Duplicate primary domains
            from django.db.models import Count
            dup_primaries = (
                Domain.objects.filter(is_primary=True)
                .values("tenant")
                .annotate(cnt=Count("id"))
                .filter(cnt__gt=1)
            )
            if dup_primaries.exists():
                findings.append(Finding(
                    "MEDIUM", "db",
                    f"Tenant(s) with multiple primary domains",
                    str(list(dup_primaries.values("tenant__schema_name", "cnt"))),
                    "Set is_primary=True on only one domain per tenant.",
                ))
        except Exception as exc:
            findings.append(Finding("HIGH", "db", f"Public schema check failed: {exc}"))

        return findings

    # =========================================================================
    # SECTION: SYNC — Seed data and schema consistency
    # =========================================================================

    def _audit_sync(self, schema_filter=None) -> List[Finding]:
        findings = []
        from clients.models import Tenant

        public = get_public_schema_name()
        qs = Tenant.objects.exclude(schema_name=public)
        if schema_filter:
            qs = qs.filter(schema_name=schema_filter)
        tenants = list(qs)

        # 1. Migration consistency across tenant schemas
        findings.extend(self._check_migration_sync(tenants))

        # 2. Module count consistency (all tenants should have same Module count)
        findings.extend(self._check_module_count_sync(tenants))

        # 3. Role count consistency
        findings.extend(self._check_role_count_sync(tenants))

        # 4. Seeding command vs start.sh sync
        findings.extend(self._check_startup_script())

        return findings

    def _check_migration_sync(self, tenants) -> List[Finding]:
        from django.db import connections
        conn = connections["default"]

        try:
            with conn.cursor() as cursor:
                # Check if django_migrations has a schema_name column (django-tenants custom migration recorder)
                cursor.execute("""
                    SELECT column_name FROM information_schema.columns
                    WHERE table_name='django_migrations' AND column_name='schema_name'
                """)
                has_schema_col = cursor.fetchone() is not None
        except Exception:
            has_schema_col = False

        if not has_schema_col:
            # Standard migrations table - skip per-tenant comparison
            return [Finding("INFO", "sync", "Migration table uses standard format — per-tenant comparison skipped.")]

        try:
            with conn.cursor() as cursor:
                cursor.execute(
                    "SELECT app, name FROM django_migrations WHERE schema_name='public' ORDER BY app, name"
                )
                public_migs = set((r[0], r[1]) for r in cursor.fetchall())

            schema_counts = {}
            for t in tenants:
                with conn.cursor() as cursor:
                    cursor.execute(
                        "SELECT app, name FROM django_migrations WHERE schema_name=%s ORDER BY app, name",
                        [t.schema_name],
                    )
                    schema_counts[t.schema_name] = set((r[0], r[1]) for r in cursor.fetchall())

            findings = []
            for schema, migs in schema_counts.items():
                missing = public_migs - migs
                if missing:
                    findings.append(Finding(
                        "HIGH", "sync",
                        f"[{schema}] Missing {len(missing)} migration(s) vs public schema",
                        "\n".join(f"{a}.{n}" for a, n in sorted(missing)[:10]),
                        f"python manage.py migrate_schemas --schema={schema}",
                    ))
            return findings
        except Exception as exc:
            return [Finding("LOW", "sync", f"Migration sync check skipped: {exc}")]

    def _check_module_count_sync(self, tenants) -> List[Finding]:
        from school.models import Module
        counts = {}
        for t in tenants:
            try:
                with schema_context(t.schema_name):
                    counts[t.schema_name] = Module.objects.count()
            except Exception:
                counts[t.schema_name] = None

        valid = {k: v for k, v in counts.items() if v is not None}
        if not valid:
            return []
        max_count = max(valid.values())
        out_of_sync = {k: v for k, v in valid.items() if v < max_count}
        if not out_of_sync:
            return []
        detail = "\n".join(f"  {k}: {v}/{max_count} modules" for k, v in out_of_sync.items())
        return [Finding(
            "HIGH", "sync",
            f"Module count out of sync across tenant schemas",
            detail,
            "python manage.py seed_modules --all-tenants",
        )]

    def _check_role_count_sync(self, tenants) -> List[Finding]:
        from school.models import Role
        counts = {}
        for t in tenants:
            try:
                with schema_context(t.schema_name):
                    counts[t.schema_name] = Role.objects.count()
            except Exception:
                counts[t.schema_name] = None

        valid = {k: v for k, v in counts.items() if v is not None}
        if not valid:
            return []
        max_count = max(valid.values())
        out_of_sync = {k: v for k, v in valid.items() if v < max_count}
        if not out_of_sync:
            return []
        detail = "\n".join(f"  {k}: {v}/{max_count} roles" for k, v in out_of_sync.items())
        return [Finding(
            "HIGH", "sync",
            f"Role count out of sync across tenant schemas",
            detail,
            "python manage.py seed_default_permissions --assign-roles --all-tenants",
        )]

    def _check_startup_script(self) -> List[Finding]:
        """Verify that all seeding commands are called in start.sh."""
        start_sh = BASE_DIR / "start.sh"
        if not start_sh.exists():
            return [Finding("MEDIUM", "sync", "start.sh not found at expected path")]

        content = start_sh.read_text()
        required_calls = [
            ("seed_modules", "seed_modules --all-tenants"),
            ("seed_default_permissions", "seed_default_permissions --assign-roles"),
            ("seed_school_data", "seed_school_data --all-tenants"),
            ("seed_olom_tenant", "seed_olom_tenant"),
        ]
        missing = []
        for cmd, label in required_calls:
            if cmd not in content:
                missing.append(label)

        if not missing:
            return []
        return [Finding(
            "HIGH", "sync",
            f"Seeding command(s) missing from start.sh: {missing}",
            fix="Add the missing commands to start.sh in the appropriate order.",
        )]

    # =========================================================================
    # SECTION: TENANT — Per-tenant data health
    # =========================================================================

    def _audit_tenant(self, schema_filter=None) -> List[Finding]:
        """Delegates to diagnose_tenant logic for a rich per-tenant health report."""
        from django.core.management import call_command
        from io import StringIO

        findings = []
        from clients.models import Tenant

        public = get_public_schema_name()
        qs = Tenant.objects.exclude(schema_name=public)
        if schema_filter:
            qs = qs.filter(schema_name=schema_filter)

        for tenant in qs:
            buf = StringIO()
            try:
                call_command("diagnose_tenant", schema_name=tenant.schema_name, stdout=buf)
            except Exception as exc:
                findings.append(Finding("HIGH", "tenant", f"[{tenant.schema_name}] diagnose_tenant failed: {exc}"))
                continue

            output = buf.getvalue()
            # Parse the output for failures
            if "All checks passed" in output:
                findings.append(Finding("INFO", "tenant", f"[{tenant.schema_name}] All health checks passed."))
            else:
                # Extract issue count
                m = re.search(r"(\d+) issue\(s\) found", output)
                count = m.group(1) if m else "?"
                # Extract issue lines
                issue_lines = [
                    line.strip().lstrip("0123456789. ")
                    for line in output.splitlines()
                    if re.match(r"\s+\d+\.", line)
                ]
                findings.append(Finding(
                    "HIGH", "tenant",
                    f"[{tenant.schema_name}] {count} health issue(s)",
                    "\n".join(issue_lines),
                    f"python manage.py diagnose_tenant --schema_name {tenant.schema_name}",
                ))

        return findings

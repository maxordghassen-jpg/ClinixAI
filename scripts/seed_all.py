#!/usr/bin/env python3
"""
Master seeder — orchestrates all ClinixAI seed scripts in the correct order.

Order:
  1. seed_availability  — weekly slot templates (prerequisite for everything)
  2. seed_patients      — patient profiles (prerequisite for appointments)
  3. seed_exceptions    — vacation/closure/override exceptions
  4. seed_appointments  — appointments from real free slots

Usage
-----
    python scripts/seed_all.py                         # full seed run
    python scripts/seed_all.py --dry-run               # preview only
    python scripts/seed_all.py --replace               # overwrite existing
    python scripts/seed_all.py --skip-availability     # skip step 1
    python scripts/seed_all.py --skip-patients         # skip step 2
    python scripts/seed_all.py --skip-exceptions       # skip step 3
    python scripts/seed_all.py --skip-appointments     # skip step 4
    python scripts/seed_all.py --only-appointments     # run step 4 only
    python scripts/seed_all.py --limit-patients 30     # cap patient count
    python scripts/seed_all.py --limit-appointments 100  # cap appointment count
    python scripts/seed_all.py --days 7                # seed 7 days of appointments
"""
from __future__ import annotations

import argparse
import sys
import time
from typing import Optional

if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
if hasattr(sys.stderr, "reconfigure"):
    sys.stderr.reconfigure(encoding="utf-8", errors="replace")


def _banner(title: str) -> None:
    line = "─" * (len(title) + 4)
    print(f"\n┌{line}┐")
    print(f"│  {title}  │")
    print(f"└{line}┘")


def _run_availability(dry_run: bool, replace: bool) -> bool:
    _banner("STEP 1 / 4 — seed_availability")
    try:
        from scripts.seed_availability import seed as seed_fn, DEFAULT_INTERVAL_MINUTES
        stats = seed_fn(
            interval=DEFAULT_INTERVAL_MINUTES,
            dry_run=dry_run,
            replace=replace,
        )
        stats.report()
        return stats.errors == 0
    except ImportError:
        # Fallback: run as module if direct import fails
        import subprocess
        cmd = [sys.executable, "scripts/seed_availability.py"]
        if dry_run:
            cmd.append("--dry-run")
        if replace:
            cmd.append("--replace")
        result = subprocess.run(cmd)
        return result.returncode == 0


def _run_patients(
    dry_run: bool,
    replace: bool,
    count: Optional[int],
) -> bool:
    _banner("STEP 2 / 4 — seed_patients")
    try:
        from scripts.seed_patients import seed as seed_fn, DEFAULT_COUNT
        stats = seed_fn(
            count=count if count is not None else DEFAULT_COUNT,
            dry_run=dry_run,
            replace=replace,
        )
        stats.report()
        return stats.errors == 0
    except ImportError:
        import subprocess
        cmd = [sys.executable, "scripts/seed_patients.py"]
        if dry_run:
            cmd.append("--dry-run")
        if replace:
            cmd.append("--replace")
        if count:
            cmd.extend(["--count", str(count)])
        result = subprocess.run(cmd)
        return result.returncode == 0


def _run_exceptions(
    dry_run: bool,
    replace: bool,
    limit: Optional[int],
) -> bool:
    _banner("STEP 3 / 4 — seed_exceptions")
    try:
        from scripts.seed_exceptions import seed as seed_fn
        stats = seed_fn(
            dry_run=dry_run,
            replace=replace,
            limit=limit,
        )
        stats.report()
        return stats.errors == 0
    except ImportError:
        import subprocess
        cmd = [sys.executable, "scripts/seed_exceptions.py"]
        if dry_run:
            cmd.append("--dry-run")
        if replace:
            cmd.append("--replace")
        if limit:
            cmd.extend(["--limit", str(limit)])
        result = subprocess.run(cmd)
        return result.returncode == 0


def _run_appointments(
    dry_run: bool,
    replace: bool,
    days: int,
    limit: Optional[int],
) -> bool:
    _banner("STEP 4 / 4 — seed_appointments")
    try:
        from scripts.seed_appointments import seed as seed_fn
        stats = seed_fn(
            days=days,
            dry_run=dry_run,
            replace=replace,
            limit=limit,
        )
        stats.report()
        return stats.errors == 0
    except ImportError:
        import subprocess
        cmd = [sys.executable, "scripts/seed_appointments.py", "--days", str(days)]
        if dry_run:
            cmd.append("--dry-run")
        if replace:
            cmd.append("--replace")
        if limit:
            cmd.extend(["--limit", str(limit)])
        result = subprocess.run(cmd)
        return result.returncode == 0


# ── Main ──────────────────────────────────────────────────────────────────────

def main() -> None:
    p = argparse.ArgumentParser(
        prog="seed_all",
        description="Master seeder — runs all ClinixAI seed scripts in order.",
        formatter_class=argparse.RawDescriptionHelpFormatter,
    )
    p.add_argument("--dry-run",              action="store_true",
                   help="Preview only — no writes to MongoDB.")
    p.add_argument("--replace",              action="store_true",
                   help="Overwrite existing records instead of skipping.")
    p.add_argument("--skip-availability",    action="store_true",
                   help="Skip seed_availability (step 1).")
    p.add_argument("--skip-patients",        action="store_true",
                   help="Skip seed_patients (step 2).")
    p.add_argument("--skip-exceptions",      action="store_true",
                   help="Skip seed_exceptions (step 3).")
    p.add_argument("--skip-appointments",    action="store_true",
                   help="Skip seed_appointments (step 4).")
    p.add_argument("--only-appointments",    action="store_true",
                   help="Run only step 4 (seed_appointments).")
    p.add_argument("--limit-patients",       type=int, metavar="N",
                   help="Generate at most N patients.")
    p.add_argument("--limit-appointments",   type=int, metavar="N",
                   help="Insert at most N appointments.")
    p.add_argument("--days",                 type=int, default=14, metavar="N",
                   help="Days ahead to seed appointments (default: 14).")

    args = p.parse_args()

    # --only-appointments implies skip everything except step 4
    if args.only_appointments:
        args.skip_availability = True
        args.skip_patients     = True
        args.skip_exceptions   = True

    wall_start = time.monotonic()
    failures: list[str] = []

    print("╔══════════════════════════════════════╗")
    print("║       ClinixAI — Full Seed Run        ║")
    print("╚══════════════════════════════════════╝")
    if args.dry_run:
        print("  MODE: DRY RUN — nothing will be written\n")

    if not args.skip_availability:
        ok = _run_availability(dry_run=args.dry_run, replace=args.replace)
        if not ok:
            failures.append("seed_availability")
    else:
        print("\n[SKIP] seed_availability")

    if not args.skip_patients:
        ok = _run_patients(
            dry_run=args.dry_run,
            replace=args.replace,
            count=args.limit_patients,
        )
        if not ok:
            failures.append("seed_patients")
    else:
        print("\n[SKIP] seed_patients")

    if not args.skip_exceptions:
        ok = _run_exceptions(
            dry_run=args.dry_run,
            replace=args.replace,
            limit=None,
        )
        if not ok:
            failures.append("seed_exceptions")
    else:
        print("\n[SKIP] seed_exceptions")

    if not args.skip_appointments:
        ok = _run_appointments(
            dry_run=args.dry_run,
            replace=args.replace,
            days=args.days,
            limit=args.limit_appointments,
        )
        if not ok:
            failures.append("seed_appointments")
    else:
        print("\n[SKIP] seed_appointments")

    elapsed = time.monotonic() - wall_start

    print("\n╔══════════════════════════════════════╗")
    print("║            SEED ALL — DONE            ║")
    print("╚══════════════════════════════════════╝")
    print(f"  Elapsed : {elapsed:.1f}s")
    if failures:
        print(f"  FAILED  : {', '.join(failures)}")
        sys.exit(1)
    else:
        print("  Status  : ALL OK")
        if args.dry_run:
            print("  NOTE    : dry-run — nothing was written")
        sys.exit(0)


if __name__ == "__main__":
    main()

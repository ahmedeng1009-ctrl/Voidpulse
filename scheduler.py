"""
VoidPulse Scheduler
Sets up a Windows Task Scheduler job to run the pipeline automatically every day.
Also supports a Python-based loop mode if you prefer to keep a terminal open.

Usage:
    python scheduler.py install --time 09:00     # install Windows daily task at 9 AM
    python scheduler.py uninstall                 # remove the scheduled task
    python scheduler.py status                    # check if task is installed
    python scheduler.py run-loop --time 09:00    # Python loop mode (terminal stays open)
    python scheduler.py run-now                   # run pipeline immediately
"""

import argparse
import subprocess
import sys
from datetime import datetime, time as dtime
from pathlib import Path

TASK_NAME   = "VoidPulse_DailyUpload"
PYTHON_EXE  = sys.executable
PIPELINE    = str(Path(__file__).parent / "run_pipeline.py")

# ── Windows Task Scheduler ────────────────────────────────────────────────────

def install_task(run_time: str = "09:00") -> bool:
    """
    Register a daily Windows Task Scheduler entry.
    Runs even if the user is not logged in (requires elevated privileges).
    """
    project_dir = str(Path(PIPELINE).parent)
    cmd = [
        "schtasks", "/create",
        "/tn",  TASK_NAME,
        "/tr",  f'"{PYTHON_EXE}" "{PIPELINE}" --smart',
        "/sc",  "daily",
        "/st",  run_time,
        "/sd",  datetime.now().strftime("%m/%d/%Y"),
        "/ru",  "SYSTEM",
        "/rl",  "HIGHEST",
        "/f",
    ]

    print(f"Installing Windows Task Scheduler job '{TASK_NAME}'...")
    print(f"  Python  : {PYTHON_EXE}")
    print(f"  Script  : {PIPELINE}")
    print(f"  Time    : {run_time} daily\n")

    try:
        result = subprocess.run(cmd, capture_output=True, text=True)
        if result.returncode == 0:
            print(f"  [OK] Task installed successfully!")
            print(f"  Run 'python scheduler.py status' to verify.")
            return True
        else:
            print(f"  [FAIL] {result.stderr.strip()}")
            print("\n  Note: Run this command as Administrator for SYSTEM account tasks.")
            print("  Alternative: use --ru '' (your current user account) instead.")

            # Retry with current user
            cmd_user = [
                "schtasks", "/create",
                "/tn",  TASK_NAME,
                "/tr",  f'"{PYTHON_EXE}" "{PIPELINE}" --smart',
                "/sc",  "daily",
                "/st",  run_time,
                "/sd",  datetime.now().strftime("%m/%d/%Y"),
                "/f",
            ]
            print("\n  Retrying with current user account...")
            result2 = subprocess.run(cmd_user, capture_output=True, text=True)
            if result2.returncode == 0:
                print(f"  [OK] Task installed (current user)!")
                return True
            else:
                print(f"  [FAIL] {result2.stderr.strip()}")
                return False

    except FileNotFoundError:
        print("  [FAIL] schtasks not found — are you on Windows?")
        return False


def uninstall_task() -> bool:
    cmd = ["schtasks", "/delete", "/tn", TASK_NAME, "/f"]
    print(f"Removing task '{TASK_NAME}'...")
    try:
        result = subprocess.run(cmd, capture_output=True, text=True)
        if result.returncode == 0:
            print("  [OK] Task removed.")
            return True
        else:
            print(f"  [FAIL] {result.stderr.strip()}")
            return False
    except FileNotFoundError:
        print("  [FAIL] schtasks not found.")
        return False


def task_status():
    cmd = ["schtasks", "/query", "/tn", TASK_NAME, "/fo", "LIST"]
    try:
        result = subprocess.run(cmd, capture_output=True, text=True)
        if result.returncode == 0:
            print(f"Task '{TASK_NAME}' is INSTALLED:\n")
            print(result.stdout)
        else:
            print(f"Task '{TASK_NAME}' is NOT installed.")
    except FileNotFoundError:
        print("  schtasks not found.")


# ── Python loop mode ──────────────────────────────────────────────────────────

def run_pipeline_now():
    import subprocess
    print(f"\n{'='*55}")
    print(f"  Running pipeline: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    print(f"{'='*55}\n")
    result = subprocess.run([PYTHON_EXE, PIPELINE], text=True)
    return result.returncode == 0


def run_loop(run_time_str: str = "09:00"):
    """
    Keep running in a terminal and execute the pipeline daily at the given time.
    Useful if you don't want to use Windows Task Scheduler.
    """
    try:
        import schedule
        import time as _time
    except ImportError:
        print("  'schedule' not installed. Run: pip install schedule")
        sys.exit(1)

    h, m = (int(x) for x in run_time_str.split(":"))
    run_at = f"{h:02d}:{m:02d}"

    print(f"\nVoidPulse Scheduler Loop")
    print(f"  Scheduled daily at: {run_at}")
    print(f"  Press Ctrl+C to stop.\n")

    schedule.every().day.at(run_at).do(run_pipeline_now)

    while True:
        schedule.run_pending()
        next_run = schedule.next_run()
        remaining = next_run - datetime.now() if next_run else None
        if remaining:
            h_left = int(remaining.total_seconds() // 3600)
            m_left = int((remaining.total_seconds() % 3600) // 60)
            print(f"\r  Next run in {h_left}h {m_left}m  [{datetime.now().strftime('%H:%M:%S')}]",
                  end="", flush=True)
        import time as _time
        _time.sleep(30)


# ── Entry point ───────────────────────────────────────────────────────────────

def main():
    parser = argparse.ArgumentParser(description="VoidPulse Scheduler")
    sub = parser.add_subparsers(dest="command")

    p_install = sub.add_parser("install",   help="Install Windows daily task")
    p_install.add_argument("--time", default="02:00",
        help="Run time HH:MM Iraq time (default 02:00 = 23:00 UK = 18:00 US Eastern — peak Shorts audience)")

    sub.add_parser("uninstall", help="Remove Windows daily task")
    sub.add_parser("status",    help="Show task status")

    p_loop = sub.add_parser("run-loop", help="Python loop mode (keep terminal open)")
    p_loop.add_argument("--time", default="02:00",
        help="Run time HH:MM Iraq time (default 02:00 = 23:00 UK = 18:00 US Eastern — peak Shorts audience)")

    sub.add_parser("run-now", help="Run pipeline immediately")

    args = parser.parse_args()

    if args.command == "install":
        install_task(args.time)

    elif args.command == "uninstall":
        uninstall_task()

    elif args.command == "status":
        task_status()

    elif args.command == "run-loop":
        run_loop(args.time)

    elif args.command == "run-now":
        ok = run_pipeline_now()
        sys.exit(0 if ok else 1)

    else:
        parser.print_help()
        print("\nExamples:")
        print("  python scheduler.py install --time 10:00   # run daily at 10 AM")
        print("  python scheduler.py status")
        print("  python scheduler.py run-now")
        print("  python scheduler.py run-loop --time 20:00  # keep terminal open")


if __name__ == "__main__":
    main()

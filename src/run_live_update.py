import subprocess
import sys
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parent.parent
SCRIPTS = [
    PROJECT_ROOT / "src" / "live_ou25_v1.py",
    PROJECT_ROOT / "src" / "forward_test_log.py",
]


def main():
    for script in SCRIPTS:
        print("\n" + "=" * 80)
        print("Kör:", script.name)
        print("=" * 80)

        result = subprocess.run(
            [sys.executable, str(script)],
            cwd=str(PROJECT_ROOT),
        )

        if result.returncode != 0:
            raise SystemExit(result.returncode)


if __name__ == "__main__":
    main()

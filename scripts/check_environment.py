"""Read-only environment check; shared with website discovery."""
from pathlib import Path
import sys
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
from app.environment import main, probe, report

if __name__ == '__main__':
    raise SystemExit(main())

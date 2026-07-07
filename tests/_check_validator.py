import os, sys
from pathlib import Path
env_file = Path(__file__).parent.parent / ".env"
with open(env_file) as f:
    for line in f:
        line = line.strip()
        if line and '=' in line and not line.startswith('#'):
            k, _, v = line.partition('=')
            os.environ[k.strip()] = v.strip().strip('"').strip("'")

sys.path.insert(0, str(Path(__file__).parent.parent))
sys.path.insert(0, str(Path(__file__).parent.parent / "src"))

from src.api.auth_routes import LoginRequest

# Test validators
for u, p in [('admin','wrong'), ('ghost_xyz','abcdef'), ('ghost_user_xyz','abcdef')]:
    try:
        req = LoginRequest(username=u, password=p)
        print(f'{u}/{p}: OK - {req}')
    except Exception as e:
        print(f'{u}/{p}: {type(e).__name__}: {e}')

# Test feature flags
from src.services.feature_flags import DEFAULT_FLAGS, load_flags
print(f"\nDefault flags: {list(DEFAULT_FLAGS.keys())}")
print(f"Loaded flags: {list(load_flags().keys())}")

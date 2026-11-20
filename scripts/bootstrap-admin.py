import os
import subprocess
from pathlib import Path

root = Path(__file__).resolve().parents[1]
env = os.environ.copy()
for line in (root/'.env').read_text(encoding='utf-8').splitlines():
    if line and not line.startswith('#') and '=' in line:
        key,value = line.split('=',1)
        if key in ('ADMIN_EMAIL','ADMIN_PASSWORD'):
            env[key] = value
subprocess.run(['docker','compose','run','--rm','--no-deps','-e','ADMIN_EMAIL','-e','ADMIN_PASSWORD',
                'worker','python','-m','app.core.bootstrap'],env=env,cwd=root,check=True)

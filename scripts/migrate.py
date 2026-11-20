"""Apply additive migrations to an existing database without deleting volumes."""
import subprocess
from pathlib import Path

root = Path(__file__).resolve().parents[1]
for migration in sorted((root/'migrations').glob('*.sql')):
    subprocess.run(['docker','compose','exec','-T','postgres','psql',
                    '-U','postgres','-d','rag','-v','ON_ERROR_STOP=1'],
                   input=migration.read_bytes(),cwd=root,check=True)
    print('Applied:', migration.name)

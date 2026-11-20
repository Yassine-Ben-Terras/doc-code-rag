"""Isolated real-Postgres suite; requires Docker and backend test dependencies."""
import os
import subprocess
import sys
from pathlib import Path

root = Path(__file__).resolve().parents[1]
env = os.environ.copy()
values = dict(line.split('=',1) for line in (root/'.env').read_text(encoding='utf-8').splitlines() if line and not line.startswith('#') and '=' in line)
env.update(PGHOST='127.0.0.1',PGPORT='55432',PGDATABASE='rag',PGUSER='api_role',PGPASSWORD=values['API_DB_PASSWORD'],
           TEST_ADMIN_PASSWORD=values['POSTGRES_PASSWORD'],TEST_WORKER_PASSWORD=values['WORKER_DB_PASSWORD'],
           JWT_SECRET=values['JWT_SECRET'],RUN_DB_TESTS='1')
command = ['docker','compose','-p','documentation-rag-test','-f','docker-compose.yml','-f','docker-compose.test.yml']
test_temp=(root/'data'/'pytest-integration').resolve()
if not test_temp.is_relative_to(root.resolve()):
    raise RuntimeError('Temporary test directory must stay inside the project')
try:
    subprocess.run(command+['up','-d','--wait','postgres'],cwd=root,check=True)
    if '--docker' in sys.argv:
        args = [arg for arg in sys.argv[1:] if arg != '--docker']
        result = subprocess.run(command+['run','--rm','--no-deps',
            '-e','RUN_DB_TESTS','-e','TEST_ADMIN_PASSWORD','-e','TEST_WORKER_PASSWORD',
            '-e','PYTEST_DISABLE_PLUGIN_AUTOLOAD=1', '-e','PYTHONPATH=/workspace/backend',
            '-v',str(root)+':/workspace:ro','--entrypoint','python','api',
            '-m','pytest','-q','-c','/workspace/pytest.ini','-p','no:cacheprovider',
            '--basetemp','/tmp/pytest-integration','/workspace/backend/tests',*args],cwd=root,env=env)
    else:
        result = subprocess.run([sys.executable,'-m','pytest','-q','--basetemp',str(test_temp),*sys.argv[1:]],cwd=root,env=env)
    sys.exit(result.returncode)
finally:
    # Only the explicitly named disposable test project's database and volume.
    subprocess.run(command+['down','-v'],cwd=root,check=False)

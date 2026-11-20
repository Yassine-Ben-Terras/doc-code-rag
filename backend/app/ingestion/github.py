import os
import re
import subprocess
from pathlib import Path
from urllib.parse import urlsplit

CODE_EXTENSIONS = {'.py','.js','.ts','.tsx','.jsx','.go','.java','.rs','.c','.h','.cpp','.cs','.sql','.sh','.yaml','.yml','.toml','.json'}
DOC_EXTENSIONS = {'.md', '.txt', '.pdf', '.docx'}
EXCLUDED = {'.git', 'node_modules', '.venv', 'venv', 'vendor', 'dist', 'build', '__pycache__', '.ssh', '.aws'}

def validate_url(url):
    parsed = urlsplit(url)
    if (parsed.scheme != 'https' or parsed.netloc != 'github.com' or parsed.query or parsed.fragment
            or not re.fullmatch(r'/[A-Za-z0-9_.-]+/[A-Za-z0-9_.-]+(?:\.git)?/?', parsed.path)):
        raise ValueError('Utiliser https://github.com/proprietaire/depot')
    if any(part in ('.','..') for part in parsed.path.split('/')):
        raise ValueError('Chemin GitHub invalide')
    return url.rstrip('/')

def clone_repository(url, destination):
    url = validate_url(url)
    env = os.environ.copy()
    env.update(GIT_TERMINAL_PROMPT='0', GIT_CONFIG_NOSYSTEM='1', GIT_CONFIG_GLOBAL=os.devnull)
    # Token never occurs in process arguments or repository URL/config.
    helper = Path(destination).parent / 'askpass.py'
    helper.write_text('#!/usr/bin/env python3\nimport os,sys\nprint("x-access-token" if "username" in sys.argv[1].lower() else os.environ.get("GITHUB_TOKEN", ""))\n', encoding='utf-8')
    helper.chmod(0o700)
    env['GIT_ASKPASS'] = str(helper)
    try:
        subprocess.run(['git', '-c', 'credential.helper=', '-c', 'http.followRedirects=false',
                        '-c', 'protocol.file.allow=never', 'clone', '--depth', '1', '--single-branch',
                        '--no-tags', '--', url, str(destination)], env=env, check=True,
                       stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL, timeout=180)
    except (subprocess.SubprocessError, OSError):
        raise ValueError('Clonage impossible : vérifier URL, accès et taille du dépôt') from None
    finally:
        helper.unlink(missing_ok=True)

def repository_files(root):
    root = Path(root).resolve()
    total = 0
    count = 0
    for directory, dirs, files in os.walk(root, followlinks=False):
        dirs[:] = sorted(d for d in dirs if d not in EXCLUDED and not d.startswith('.') and not (Path(directory)/d).is_symlink())
        for name in sorted(files):
            path = Path(directory) / name
            if path.is_symlink() or name.startswith('.') or name.lower() in {'credentials.json','secrets.json','package-lock.json','poetry.lock'}:
                continue
            if path.suffix.lower() not in CODE_EXTENSIONS | DOC_EXTENSIONS or path.stat().st_size > 200 * 1024:
                continue
            total += path.stat().st_size
            count += 1
            if total > 20 * 1024 * 1024 or count > 2000:
                raise ValueError('Dépôt trop volumineux pour cette version')
            yield path

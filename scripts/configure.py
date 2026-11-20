"""Generate secrets, preserve existing credentials, upgrade external-LLM settings."""
import base64
from pathlib import Path
import secrets

root = Path(__file__).resolve().parents[1]
text = (root/'.env.example').read_text(encoding='utf-8')
encryption_key = base64.urlsafe_b64encode(secrets.token_bytes(32)).decode()
text = text.replace('replace-with-generated-fernet-key', encryption_key)
for key in ('POSTGRES_PASSWORD','API_DB_PASSWORD','WORKER_DB_PASSWORD','JWT_SECRET','ADMIN_PASSWORD'):
    text = '\n'.join(f'{key}={secrets.token_urlsafe(36)}' if line.startswith(key+'=') else line for line in text.split('\n'))
try:
    with (root/'.env').open('x',encoding='utf-8') as output:
        output.write(text)
    print('.env créé avec des secrets aléatoires. Consultez-le localement pour le compte administrateur.')
except FileExistsError:
    path = root/'.env'
    existing = path.read_text(encoding='utf-8')
    lines = [line for line in existing.splitlines() if not line.startswith(('OLLAMA_MODEL=', 'LLM_URL='))]
    if not any(line.startswith('LLM_ENCRYPTION_KEY=') for line in lines):
        lines.append('LLM_ENCRYPTION_KEY='+encryption_key)
    updated = '\n'.join(lines)+'\n'
    if updated != existing:
        path.write_text(updated, encoding='utf-8')
    print('.env prêt : identifiants existants et clé de chiffrement conservés.')

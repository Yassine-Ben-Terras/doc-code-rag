"""Run explicitly as worker_role to create the initial administrator once."""
import os
from app.api.auth import hasher
from app.core.db import transaction

def main():
    email = os.environ['ADMIN_EMAIL'].strip().lower()
    password = os.environ['ADMIN_PASSWORD']
    if len(password) < 12 or password.startswith('replace-'):
        raise SystemExit('Choisir un mot de passe administrateur de 12 caractères minimum')
    with transaction() as db:
        db.execute("SELECT pg_advisory_xact_lock(187642)")
        if db.execute("SELECT 1 FROM users u JOIN roles r ON r.id=u.role_id WHERE r.name='admin'").fetchone():
            print('Administrateur déjà initialisé ; aucun changement.')
            return
        db.execute("INSERT INTO users(email,password_hash,role_id) SELECT %s,%s,id FROM roles WHERE name='admin'", (email,hasher.hash(password)))
    print('Administrateur créé.')

if __name__ == '__main__':
    main()

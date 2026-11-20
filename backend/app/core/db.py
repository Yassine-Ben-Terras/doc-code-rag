from contextlib import contextmanager
import psycopg
from psycopg.rows import dict_row

@contextmanager
def transaction(user_id=None):
    # libpq environment variables; never interpolate credentials into a DSN.
    with psycopg.connect('', row_factory=dict_row, connect_timeout=10) as conn:
        with conn.transaction():
            conn.execute("SELECT set_config('app.user_id', %s, true)", (str(user_id) if user_id else '',))
            yield conn

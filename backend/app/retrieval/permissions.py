from fastapi import HTTPException

def allowed_collections(db, user):
    return [r['collection_id'] for r in db.execute(
        'SELECT cp.collection_id FROM collection_permissions cp JOIN users u ON u.role_id=cp.role_id WHERE u.id=%s',
        (user['id'],)).fetchall()]

def require_collection(db, user, collection_id, write=False, lock=False):
    # Lock permission rows during mutations / generation so a revocation serializes with ongoing work.
    row = db.execute('''SELECT cp.can_write FROM collection_permissions cp
        JOIN users u ON u.role_id=cp.role_id WHERE u.id=%s AND cp.collection_id=%s'''
        + (' FOR SHARE OF cp' if lock else ''), (user['id'], collection_id)).fetchone()
    if not row or (write and not row['can_write']):
        raise HTTPException(404, 'Collection ou document inaccessible')
    return row

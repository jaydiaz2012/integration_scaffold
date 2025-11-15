import os
import hmac
import hashlib
from dotenv import load_dotenv
from sqlalchemy.exc import IntegrityError
from models import IdempotencyKey

load_dotenv()

def get_env(key, default=None):
    return os.getenv(key, default)

def verify_signature(secret, payload_bytes, signature_header):
    # Placeholder: platform-specific verification should be used (HMAC SHA256 etc.)
    if not secret or not signature_header:
        return False
    computed = hmac.new(secret.encode(), payload_bytes, hashlib.sha256).hexdigest()
    return hmac.compare_digest(computed, signature_header)

def register_idempotency(session, key):
    if not key:
        return True
    existing = session.query(IdempotencyKey).filter_by(key=key).first()
    if existing:
        return False
    new = IdempotencyKey(key=key)
    session.add(new)
    try:
        session.commit()
        return True
    except IntegrityError:
        session.rollback()
        return False

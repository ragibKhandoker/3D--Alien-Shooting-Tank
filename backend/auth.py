"""Password hashing + signed login tokens (sent as 'Authorization: Bearer <token>')."""
from functools import wraps

from flask import g, jsonify, request
from itsdangerous import BadSignature, SignatureExpired, URLSafeTimedSerializer
from werkzeug.security import check_password_hash, generate_password_hash

import config
import database

TOKEN_MAX_AGE = 7 * 24 * 3600  # 7 days

_serializer = URLSafeTimedSerializer(config.SECRET_KEY, salt="tank-auth")

hash_password = generate_password_hash
verify_password = check_password_hash


def create_token(user_id: int) -> str:
    return _serializer.dumps({"uid": user_id})


def user_from_token(token: str):
    try:
        data = _serializer.loads(token, max_age=TOKEN_MAX_AGE)
    except (BadSignature, SignatureExpired):
        return None
    return database.get_user(data["uid"])


def login_required(view):
    @wraps(view)
    def wrapper(*args, **kwargs):
        header = request.headers.get("Authorization", "")
        token = header[7:] if header.startswith("Bearer ") else ""
        user = user_from_token(token) if token else None
        if not user:
            return jsonify({"error": "Please log in first"}), 401
        g.user = user
        return view(*args, **kwargs)
    return wrapper

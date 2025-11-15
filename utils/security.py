from passlib.context import CryptContext 
from datetime import datetime,timedelta,timezone 
import os 
import jwt
from sqlalchemy.util import deprecated 
import bcrypt



JWT_SECRET = os.environ["JWT_SECRET"]
JWT_ALG = "HS256"
JWT_EXP_MINUTES = int(os.environ.get("JWT_EXP_MINUTES")) 

def hash_password(raw:str) -> str: 
    salt = bcrypt.gensalt(rounds=12)
    return bcrypt.hashpw(raw.encode('utf-8'), salt).decode('utf-8')


def verify_password(raw:str, hashed:str) -> bool:
    return bcrypt.checkpw(raw.encode('utf-8'), hashed.encode('utf-8'))

def issue_token(user_id:str,email:str) -> str: 
    now = datetime.now(tz=timezone.utc) 
    payload = {"sub": user_id, "email": email, "iat": now, "exp": now + timedelta(minutes=JWT_EXP_MINUTES)}
    return jwt.encode(payload, JWT_SECRET, algorithm=JWT_ALG)
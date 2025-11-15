from uuid import UUID
from databases.table_details import User 
from sqlalchemy.orm import Session 



def get_user_by_identifier(identifier: str, db: Session) -> User:
    try:
        user_id = UUID(identifier)
        user = db.query(User).filter(User.id == user_id).first()
    except ValueError:
        email_normalized = identifier.strip().lower()
        user = db.query(User).filter(User.email == email_normalized).first()
    
    return user
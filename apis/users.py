from fastapi import APIRouter,Depends,HTTPException, status 
from sqlalchemy.orm import Session 
from databases.database_connection import get_db 
from databases.table_details import User 
from schemas.schemas import UserCreate,UserRead,LoginRequest,LoginResponse, UserUpdate
from utils.security import hash_password,verify_password,issue_token 
from uuid import UUID
from utils.identifier import get_user_by_identifier


router = APIRouter(prefix="/users",tags=["users"])


@router.post("/register",response_model=UserRead,status_code=status.HTTP_201_CREATED)
def register(payload:UserCreate,db:Session = Depends(get_db)):
    email_normalized = payload.email.strip().lower()
    if db.query(User).filter(User.email == email_normalized).first():
        raise HTTPException(status_code=409, detail="Email already registered")

    new_user = User(
        email=email_normalized,
        name=payload.name.strip(),
        password_hash=hash_password(payload.password),
        role = payload.role,
        company_id = payload.company_id,
        department = payload.department,
        job_title=payload.job_title,
        avatar_url=payload.avatar_url,
        career_level=payload.career_level,
        industry=payload.industry,
        pronouns=payload.pronouns
    )

    db.add(new_user)
    db.commit()
    db.refresh(new_user)
    return new_user


@router.post("/login",response_model=LoginResponse)
def login(payload: LoginRequest, db: Session = Depends(get_db)):
    email_normalized = payload.email.strip().lower()
    user = db.query(User).filter(User.email==email_normalized).first()
    if user is None or not verify_password(payload.password,user.password_hash):
        raise HTTPException(status_code=401,detail="Invalid credentials")

    token = issue_token(str(user.id), user.email)
    return LoginResponse(access_token=token,user=user)


@router.get("/list_user",response_model=list[UserRead])
def list_users(db: Session = Depends(get_db)):
    return db.query(User).order_by(User.created_at.desc()).all()

@router.get("/show_user/{identifier}",response_model=UserRead)
def get_user(identifier:str, db: Session = Depends(get_db)):
    user = get_user_by_identifier(identifier,db)
    if user is None:
        raise HTTPException(status_code=404, detail="User not found")
    return user 


@router.put("/update_user/{identifier}",response_model=UserRead)
def update_user(identifier:str, payload:UserUpdate,db:Session=Depends(get_db)):
    user = get_user_by_identifier(identifier,db)

    if user is None: 
        raise HTTPException(status_code=404, detail="User Not Found")

    if payload.email is not None: 
        email_normalized = payload.email.strip().lower()
        existing_user = db.query(User).filter(User.email==email_normalized, User.id != user.id).first()
        if existing_user: 
            raise HTTPException(status_code = 409, detail="Email already registered")

        user.email=email_normalized

    if payload.name is not None:
        user.name = payload.name.strip() 

    if payload.password is not None:
        user.password_hash = hash_password(payload.password)

    if payload.role is not None:
        user.role = payload.role

    if payload.company_id is not None:
        user.company_id = payload.company_id

    if payload.department is not None: 
        user.department = payload.department

    if payload.job_title is not None:
        user.job_title = payload.job_title

    if payload.avatar_url is not None:
        user.avatar_url = payload.avatar_url

    if payload.career_level is not None:
        user.career_level = payload.career_level

    if payload.industry is not None:
        user.industry = payload.industry

    if payload.pronouns is not None:
        user.pronouns = payload.pronouns

    db.commit()
    db.refresh(user)
    return user 


@router.delete("/delete_user/{identifier}",status_code=status.HTTP_200_OK)
def delete_user(identifier: str, db: Session = Depends(get_db)):
    user = get_user_by_identifier(identifier,db)
    if user is None: 
        raise HTTPException(status_code=404,detail="User not found")

    db.delete(user)
    db.commit()

    return "Deletion Success"


        





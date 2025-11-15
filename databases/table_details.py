from enum import unique
import sqlalchemy as sa 
from sqlalchemy.dialects import postgresql as pg 
from sqlalchemy.orm import declarative_base 

Base = declarative_base()

class User(Base): 
    __tablename__ = "users"
    __table_args__ = (
        sa.CheckConstraint(
            "role IN ('free','team_member','manager','admin')",
            name="ck_users_role",
        ),
        sa.Index("idx_users_email","email"),
        sa.Index("idx_users_company_id","company_id"),
        sa.Index("idx_users_role","role"),
        sa.Index("idx_users_created_at","created_at"),
    )

    id = sa.Column(
        pg.UUID(as_uuid=True),
        primary_key=True,
        server_default=sa.text("gen_random_uuid()"),
    )

    email = sa.Column(sa.String(255),nullable=False, unique=True) 
    name = sa.Column(sa.String(255),nullable=False)
    password_hash = sa.Column(sa.String(255),nullable=False)
    role = sa.Column(sa.String(50),nullable=False,server_default='free')
    company_id = sa.Column(
        pg.UUID(as_uuid=True),
        nullable = True,
    )
    email_verified = sa.Column(sa.Boolean, server_default=sa.text("FALSE")) 
    email_verified_at = sa.Column(sa.TIMESTAMP(timezone=True))
    avatar_url = sa.Column(sa.String(500))
    department = sa.Column(sa.String(500))
    job_title = sa.Column(sa.String(255))
    created_at = sa.Column(
        sa.TIMESTAMP(timezone=True),
        nullable=False,
        server_default=sa.text("CURRENT_TIMESTAMP"),
    )
    updated_at = sa.Column(
        sa.TIMESTAMP(timezone=True),
        nullable=False,
        server_default=sa.text("CURRENT_TIMESTAMP"),
        onupdate=sa.text("CURRENT_TIMESTAMP"),
    )

    last_login_at = sa.Column(sa.TIMESTAMP(timezone=True))
    deleted_at = sa.Column(sa.TIMESTAMP(timezone=True))
    


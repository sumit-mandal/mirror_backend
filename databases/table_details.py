from enum import unique
from locale import currency
import sqlalchemy as sa 
from sqlalchemy.dialects import postgresql as pg 
from sqlalchemy.orm import declarative_base, relationship 

Base = declarative_base()

class Company(Base):

    __tablename__ = "companies"
    __table_args__ = (
        sa.Index("idx_companies_slug","slug"),
        sa.Index("idx_companies_stripe_customer_id","stripe_customer_id")
    )

    id = sa.Column(
        pg.UUID(as_uuid=True),
        primary_key=True,
        server_default=sa.text("gen_random_uuid()"),
    )

    name = sa.Column(sa.String(255), nullable=False)
    slug = sa.Column(sa.String(100),unique=True)
    industry = sa.Column(sa.String(100))
    size = sa.Column(sa.String(50))
    billing_email = sa.Column(sa.String(255), unique=True,nullable=False)
    stripe_customer_id = sa.Column(sa.String(255), unique=True)
    logo_url = sa.Column(sa.String(500))
    website = sa.Column(sa.String(500))
    address_line1 = sa.Column(sa.String(255))
    address_line2 = sa.Column(sa.String(255))
    city = sa.Column(sa.String(100))
    state = sa.Column(sa.String(100))
    postal_code = sa.Column(sa.String(20))
    country = sa.Column(sa.String(100))

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

    deleted_at = sa.Column(sa.TIMESTAMP(timezone=True))

    print("COmpany details done")

    users = relationship("User", back_populates="company")

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
        sa.ForeignKey("companies.id",ondelete="SET NULL"),
        nullable = True,
    )
    email_verified = sa.Column(sa.Boolean, server_default=sa.text("FALSE")) 
    email_verified_at = sa.Column(sa.TIMESTAMP(timezone=True))
    avatar_url = sa.Column(sa.String(500))
    department = sa.Column(sa.String(500))
    job_title = sa.Column(sa.String(255))
    career_level = sa.Column(sa.String(100))
    industry = sa.Column(sa.String(100))
    pronouns = sa.Column(sa.String(50))
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

    company = relationship("Company",back_populates="users")
    

class PaymentTransaction(Base):
    __tablename__ = "payment_transactions"
    __table_args__ = (
        sa.Index("idx_transactions_company_id","company_id"),
        sa.Index("idx_transactions_user_id","user_id"),
        sa.Index("idx_transactions_status","status"),
        sa.Index("idx_transactions_stripe_intent","stripe_payment_intent_id"),
        sa.Index("idx_transactions_created_at","created_at"),
    )

    id = sa.Column(pg.UUID(as_uuid=True), primary_key=True, server_default=sa.text("gen_random_uuid()"))
    company_id = sa.Column(pg.UUID(as_uuid=True), sa.ForeignKey("companies.id",ondelete="SET NULL"), nullable=True)
    user_id = sa.Column(pg.UUID(as_uuid=True),sa.ForeignKey("users.id",ondelete="SET NULL"), nullable=True)

    transaction_type = sa.Column(sa.String(50), nullable=False) 
    amount = sa.Column(sa.Numeric(10,2), nullable=False)
    currency = sa.Column(sa.String(3), server_default="USD")
    status = sa.Column(sa.String(50),nullable=False)

    stripe_payment_intent_id = sa.Column(sa.String(255), unique=True)
    stripe_charge_id = sa.Column(sa.String(255)) 
    stripe_invoice_id = sa.Column(sa.String(255)) 
    stripe_customer_id = sa.Column(sa.String(255)) 

    license_pack_id = sa.Column(
        pg.UUID(as_uuid=True),
        sa.ForeignKey("license_packs.id", ondelete="SET NULL"),
        nullable=True,
    )

    product_description = sa.Column(sa.Text)

    initiated_at = sa.Column(sa.TIMESTAMP(timezone=True), nullable=False, server_default=sa.text("CURRENT_TIMESTAMP"))

    completed_at = sa.Column(sa.TIMESTAMP(timezone=True)) 
    failed_at = sa.Column(sa.TIMESTAMP(timezone=True)) 
    refunded_at = sa.Column(sa.TIMESTAMP(timezone=True)) 

     # Error Handling
    failure_reason = sa.Column(sa.Text)
    refund_reason = sa.Column(sa.Text)
    refund_amount = sa.Column(sa.Numeric(10, 2))

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


class LicensePack(Base):
    __tablename__ = "license_packs"
    __table_args__ = (
        sa.CheckConstraint(
            "used_licenses >= 0 AND used_licenses <= total_licenses",
            name="chk_licenses_valid",
        ),
        sa.Index("idx_license_packs_company_id", "company_id"),
        sa.Index("idx_license_packs_status", "status"),
        sa.Index("idx_license_packs_expiration", "expiration_date"),
    )

    id = sa.Column(
        pg.UUID(as_uuid=True),
        primary_key=True,
        server_default=sa.text("gen_random_uuid()"),
    )

    company_id = sa.Column(
        pg.UUID(as_uuid=True),
        sa.ForeignKey("companies.id", ondelete="CASCADE"),
        nullable=False,
    )

    pack_type = sa.Column(sa.String(50), nullable=False)
    total_licenses = sa.Column(sa.Integer, nullable=False)
    used_licenses = sa.Column(sa.Integer, nullable=False, server_default="0")
    available_licenses = sa.Column(
        sa.Integer,
        sa.Computed("total_licenses - used_licenses", persisted=True)
    )
    price_paid = sa.Column(sa.Numeric(10, 2), nullable=False)
    currency = sa.Column(sa.String(3), server_default="USD")
    purchase_date = sa.Column(
        sa.TIMESTAMP(timezone=True),
        nullable=False,
        server_default=sa.text("CURRENT_TIMESTAMP"),
    )
    expiration_date = sa.Column(sa.TIMESTAMP(timezone=True))
    stripe_payment_id = sa.Column(sa.String(255))
    stripe_invoice_id = sa.Column(sa.String(255))
    status = sa.Column(sa.String(50), nullable=False, server_default="active")

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

class PackType(Base):
    __tablename__ = "pack_types"
    __table_args__ = (
        sa.Index("idx_pack_types_pack_type", "pack_type"),
        sa.Index("idx_pack_types_is_active", "is_active"),
    )

    id = sa.Column(
        pg.UUID(as_uuid=True),
        primary_key=True,
        server_default=sa.text("gen_random_uuid()"),
    )

    pack_type = sa.Column(sa.String(50), nullable=False, unique=True)  # e.g., "5-pack", "10-pack"
    total_licenses = sa.Column(sa.Integer, nullable=False)
    is_active = sa.Column(sa.Boolean, nullable=False, server_default=sa.text("TRUE"))

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


class Credit(Base):
    __tablename__ = "credits"
    __table_args__ = (
        sa.Index("idx_credits_code", "code"),
        sa.Index("idx_credits_status", "status"),
        sa.Index("idx_credits_company_id", "company_id"),
        sa.Index("idx_credits_created_by", "created_by_user_id"),
    )

    id = sa.Column(
        pg.UUID(as_uuid=True),
        primary_key=True,
        server_default=sa.text("gen_random_uuid()"),
    )

    code = sa.Column(sa.String(50), nullable=False, unique=True)

    company_id = sa.Column(
        pg.UUID(as_uuid=True),
        sa.ForeignKey("companies.id", ondelete="CASCADE"),
        nullable=False,
    )

    created_by_user_id = sa.Column(
        pg.UUID(as_uuid=True),
        sa.ForeignKey("users.id", ondelete="SET NULL"),
        nullable=True,
    )

    uses_total = sa.Column(sa.Integer, nullable=False, server_default="1")
    uses_remaining = sa.Column(sa.Integer, nullable=False, server_default="1") 
    claimed_by_user_id = sa.Column(
        pg.UUID(as_uuid=True),
        sa.ForeignKey("users.id", ondelete="SET NULL"),
        nullable=True,
    )

    claimed_at = sa.Column(sa.TIMESTAMP(timezone=True))
    expires_at = sa.Column(sa.TIMESTAMP(timezone=True))
    status = sa.Column(sa.String(50), nullable=False, server_default="active")

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


    # Relationships
    company = relationship("Company")
    created_by = relationship("User", foreign_keys=[created_by_user_id])
    claimed_by = relationship("User", foreign_keys=[claimed_by_user_id])
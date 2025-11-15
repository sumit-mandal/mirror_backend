# MirrorMinds Compass - Database Specification

**Document Version**: 1.0  
**Date**: November 13, 2025  
**Target Database**: PostgreSQL 14+  
**ORM**: Prisma 

---

## Executive Summary

This document provides the complete database schema required for the MirrorMinds Compass leadership assessment platform. The application is built with Next.js 15 and currently uses mock data. This schema will enable:

- Multi-tenant team management
- License-based access control
- User authentication and role management
- Assessment tracking and results storage
- Social features (connections, sharing)
- Payment and billing history

---

## System Requirements

### Technology Stack
- **Database**: PostgreSQL 14 or higher
- **Connection Pooling**: PgBouncer or AWS RDS Proxy (recommended for production)
- **Backup Strategy**: Daily automated backups with 30-day retention
- **Hosting Options**: 
  - AWS RDS PostgreSQL
  - Supabase (includes auth built-in)
  - Neon (serverless PostgreSQL)
  - Railway

### Performance Requirements
- **Expected Load**: 
  - Initial: 100-500 users
  - Growth: 5,000+ users within 6 months
- **Query Performance**: < 100ms for dashboard queries
- **Concurrent Connections**: Support 50+ simultaneous users
- **Storage**: Estimated 100MB per 1,000 assessments

---

## Database Schema

### 1. Users Table

**Purpose**: Core user authentication and profile information

```sql
CREATE TABLE users (
  id                  UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  email               VARCHAR(255) NOT NULL UNIQUE,
  name                VARCHAR(255) NOT NULL,
  password_hash       VARCHAR(255) NOT NULL, -- bcrypt hash
  role                VARCHAR(50) NOT NULL DEFAULT 'free',
  company_id          UUID REFERENCES companies(id) ON DELETE SET NULL,
  email_verified      BOOLEAN DEFAULT FALSE,
  email_verified_at   TIMESTAMP,
  avatar_url          VARCHAR(500),
  department          VARCHAR(255),
  job_title           VARCHAR(255),
  created_at          TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,
  updated_at          TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,
  last_login_at       TIMESTAMP,
  deleted_at          TIMESTAMP -- Soft delete support
);

-- Indexes
CREATE INDEX idx_users_email ON users(email);
CREATE INDEX idx_users_company_id ON users(company_id);
CREATE INDEX idx_users_role ON users(role);
CREATE INDEX idx_users_created_at ON users(created_at);
```

**Role Values** (ENUM or CHECK constraint):
- `'free'` - Individual freemium user
- `'team_member'` - Part of a paid team (invited)
- `'manager'` - Can purchase licenses and invite team members
- `'admin'` - Platform administrator

**Notes**:
- `password_hash` should be bcrypt with salt rounds 10-12
- `email` must be lowercase and trimmed
- `updated_at` should auto-update on any row change (use trigger)

---

### 2. Companies Table

**Purpose**: Organizations/teams that purchase licenses

```sql
CREATE TABLE companies (
  id                  UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  name                VARCHAR(255) NOT NULL,
  slug                VARCHAR(255) UNIQUE, -- For vanity URLs
  industry            VARCHAR(100),
  size                VARCHAR(50), -- 'small', 'medium', 'large', 'enterprise'
  billing_email       VARCHAR(255),
  stripe_customer_id  VARCHAR(255) UNIQUE,
  logo_url            VARCHAR(500),
  website             VARCHAR(500),
  address_line1       VARCHAR(255),
  address_line2       VARCHAR(255),
  city                VARCHAR(100),
  state               VARCHAR(100),
  postal_code         VARCHAR(20),
  country             VARCHAR(2), -- ISO country code
  created_at          TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,
  updated_at          TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,
  deleted_at          TIMESTAMP
);

-- Indexes
CREATE INDEX idx_companies_slug ON companies(slug);
CREATE INDEX idx_companies_stripe_customer_id ON companies(stripe_customer_id);
```

**Notes**:
- `slug` generation: lowercase company name with hyphens
- Multiple managers per company supported (via users.company_id)

---

### 3. License Packs Table

**Purpose**: Track purchased license bundles

```sql
CREATE TABLE license_packs (
  id                  UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  company_id          UUID NOT NULL REFERENCES companies(id) ON DELETE CASCADE,
  pack_type           VARCHAR(50) NOT NULL, -- '5-pack', '10-pack', '25-pack', '50-pack', '100-pack'
  total_licenses      INTEGER NOT NULL,
  used_licenses       INTEGER NOT NULL DEFAULT 0,
  available_licenses  INTEGER GENERATED ALWAYS AS (total_licenses - used_licenses) STORED,
  price_paid          DECIMAL(10, 2) NOT NULL, -- Amount in USD
  currency            VARCHAR(3) DEFAULT 'USD',
  purchase_date       TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,
  expiration_date     TIMESTAMP, -- NULL = never expires
  stripe_payment_id   VARCHAR(255),
  stripe_invoice_id   VARCHAR(255),
  status              VARCHAR(50) NOT NULL DEFAULT 'active', -- 'active', 'expired', 'cancelled'
  created_at          TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,
  updated_at          TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP
);

-- Indexes
CREATE INDEX idx_license_packs_company_id ON license_packs(company_id);
CREATE INDEX idx_license_packs_status ON license_packs(status);
CREATE INDEX idx_license_packs_expiration ON license_packs(expiration_date);

-- Constraint: used_licenses cannot exceed total_licenses
ALTER TABLE license_packs ADD CONSTRAINT chk_licenses_valid 
  CHECK (used_licenses >= 0 AND used_licenses <= total_licenses);
```

**Pack Types & Pricing** (reference only, store in app config):
- `5-pack`: $99 ($19.80 per license)
- `10-pack`: $179 ($17.90 per license)
- `25-pack`: $399 ($15.96 per license)
- `50-pack`: $699 ($13.98 per license)
- `100-pack`: $1,199 ($11.99 per license)

**Notes**:
- `available_licenses` is computed field (PostgreSQL GENERATED column)
- When user accepts invitation, increment `used_licenses`
- Support multiple active packs per company (FIFO consumption)

---

### 4. Invitations Table

**Purpose**: Track team member invitations sent by managers

```sql
CREATE TABLE invitations (
  id                  UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  company_id          UUID NOT NULL REFERENCES companies(id) ON DELETE CASCADE,
  inviter_id          UUID NOT NULL REFERENCES users(id) ON DELETE CASCADE,
  invitee_id          UUID REFERENCES users(id) ON DELETE SET NULL, -- Set after registration
  email               VARCHAR(255) NOT NULL,
  name                VARCHAR(255) NOT NULL,
  token               VARCHAR(255) NOT NULL UNIQUE, -- Secure random token
  status              VARCHAR(50) NOT NULL DEFAULT 'pending',
  role_granted        VARCHAR(50) DEFAULT 'team_member',
  sent_at             TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,
  expires_at          TIMESTAMP NOT NULL, -- Typically 7 days from sent_at
  accepted_at         TIMESTAMP,
  email_sent          BOOLEAN DEFAULT FALSE,
  reminder_sent_at    TIMESTAMP,
  created_at          TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,
  updated_at          TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP
);

-- Indexes
CREATE INDEX idx_invitations_token ON invitations(token);
CREATE INDEX idx_invitations_email ON invitations(email);
CREATE INDEX idx_invitations_company_id ON invitations(company_id);
CREATE INDEX idx_invitations_status ON invitations(status);
CREATE INDEX idx_invitations_expires_at ON invitations(expires_at);

-- Unique constraint: one pending invitation per email per company
CREATE UNIQUE INDEX idx_invitations_unique_pending 
  ON invitations(company_id, email) 
  WHERE status = 'pending';
```

**Status Values**:
- `'pending'` - Invitation sent, awaiting acceptance
- `'accepted'` - User registered and joined team
- `'expired'` - Token expired (past expires_at)
- `'cancelled'` - Manager cancelled invitation

**Token Generation**:
- Use cryptographically secure random string (e.g., 64 characters)
- Example: `crypto.randomBytes(32).toString('hex')`

**Notes**:
- Email should be lowercase and trimmed
- When invitation accepted:
  - Set `status = 'accepted'`
  - Set `accepted_at = CURRENT_TIMESTAMP`
  - Set `invitee_id = new_user.id`
  - Increment `license_packs.used_licenses`

---

### 5. Assessments Table

**Purpose**: Track assessment sessions

```sql
CREATE TABLE assessments (
  id                  UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  user_id             UUID NOT NULL REFERENCES users(id) ON DELETE CASCADE,
  session_id          VARCHAR(255) NOT NULL UNIQUE, -- From AWS Lambda API
  assessment_type     VARCHAR(50) NOT NULL, -- 'lite', 'comprehensive'
  status              VARCHAR(50) NOT NULL DEFAULT 'in_progress',
  persona             VARCHAR(50), -- 'mentor', 'coach', etc.
  candidate_persona   VARCHAR(50), -- 'professional', 'student'
  max_questions       INTEGER DEFAULT 20,
  questions_answered  INTEGER DEFAULT 0,
  progress_percentage INTEGER DEFAULT 0,
  started_at          TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,
  completed_at        TIMESTAMP,
  last_activity_at    TIMESTAMP,
  duration_minutes    INTEGER, -- Calculated on completion
  created_at          TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,
  updated_at          TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP
);

-- Indexes
CREATE INDEX idx_assessments_user_id ON assessments(user_id);
CREATE INDEX idx_assessments_session_id ON assessments(session_id);
CREATE INDEX idx_assessments_status ON assessments(status);
CREATE INDEX idx_assessments_type ON assessments(assessment_type);
CREATE INDEX idx_assessments_completed_at ON assessments(completed_at);
```

**Status Values**:
- `'in_progress'` - User is actively taking assessment
- `'completed'` - Assessment finished successfully
- `'abandoned'` - User left without completing
- `'expired'` - Session timed out (inactive > 7 days)

**Assessment Types**:
- `'lite'` - Free 6-question assessment (3 skills)
- `'comprehensive'` - Full 20-84 question assessment (all 7 COGs)

**Notes**:
- `session_id` maps to AWS Lambda interviewer API session (e.g., 'session_1730795234567')
  - **CRITICAL**: This is the same session_id currently stored in `sessionStorage.getItem('sessionId')`
  - Frontend stores this in browser: `sessionStorage.setItem('sessionId', session_id)`
  - On assessment completion, this session_id must be linked to the logged-in user's UUID
- `user_id` links the session to the authenticated user from `users` table
- `duration_minutes` = difference between `completed_at` and `started_at`

**Frontend Integration Example**:
```javascript
// When starting assessment (app/leader/assessment/page.tsx)
const response = await interviewerService.startInterview({...});
const sessionId = response.session_id;

// Store in sessionStorage (current behavior)
sessionStorage.setItem('sessionId', sessionId);

// NEW: Also store in database
await fetch('/api/assessments/start', {
  method: 'POST',
  body: JSON.stringify({
    session_id: sessionId,
    user_id: currentUser.id, // From NextAuth session
    assessment_type: 'comprehensive',
    persona: 'mentor',
    candidate_persona: 'professional',
    max_questions: 20
  })
});
```

---

### 6. Assessment Results Table

**Purpose**: Store assessment outcomes and AI-generated reports

```sql
CREATE TABLE assessment_results (
  id                    UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  assessment_id         UUID NOT NULL UNIQUE REFERENCES assessments(id) ON DELETE CASCADE,
  overall_score         DECIMAL(4, 2), -- 0.00 to 10.00
  
  -- Persona Analysis (from AI)
  primary_persona_code  VARCHAR(10),
  primary_persona_name  VARCHAR(255),
  primary_persona_score DECIMAL(4, 2),
  primary_description   TEXT,
  
  -- JSON Storage for Full Results
  skill_scores          JSONB, -- { "Security": 7.5, "Leadership": 8.2, ... }
  domain_scores         JSONB, -- { "Cognitive Security": 7.0, ... }
  ranked_personas       JSONB, -- Full persona ranking array
  secondary_personas    JSONB, -- Secondary persona details
  
  -- Summary Fields
  strengths             TEXT[], -- Array of strength descriptions
  areas_for_improvement TEXT[], -- Array of improvement areas
  recommendations       TEXT[], -- Array of actionable recommendations
  overall_analysis      TEXT, -- AI-generated comprehensive analysis
  
  -- Metadata
  completion_reason     VARCHAR(100), -- 'max_questions', 'early_finish', etc.
  raw_api_response      JSONB, -- Full API response for debugging
  
  created_at            TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,
  updated_at            TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP
);

-- Indexes
CREATE INDEX idx_results_assessment_id ON assessment_results(assessment_id);
CREATE INDEX idx_results_overall_score ON assessment_results(overall_score);
CREATE INDEX idx_results_primary_persona ON assessment_results(primary_persona_code);

-- GIN index for JSONB columns (for efficient querying)
CREATE INDEX idx_results_skill_scores ON assessment_results USING GIN (skill_scores);
CREATE INDEX idx_results_domain_scores ON assessment_results USING GIN (domain_scores);
```

**JSONB Structure Examples**:

```json
// skill_scores
{
  "Security": 7.5,
  "Stability": 7.0,
  "Confidence": 6.0,
  "Leadership": 6.3,
  "Expression": 5.5
}

// ranked_personas
[
  {
    "persona_code": "S-S",
    "persona_name": "The Stabilizer (S–S)",
    "score": 7.0,
    "rank": 1,
    "category": "Primary",
    "trait_1": { "name": "Security", "score": 7.0 },
    "trait_2": { "name": "Stability", "score": 7.0 },
    "description": "For you, being 'The Stabilizer' means..."
  }
]
```

**Notes**:
- JSONB allows flexible storage while maintaining queryability
- One result per assessment (enforced by UNIQUE constraint)
- **CRITICAL MAPPING**: When assessment completes, frontend has results in sessionStorage:
  ```javascript
  // Current frontend behavior (app/leader/assessment/page.tsx)
  sessionStorage.setItem('assessmentResults', JSON.stringify(results));
  sessionStorage.setItem('sessionId', sessionId);
  
  // NEW: Backend must retrieve these and persist
  const sessionId = sessionStorage.getItem('sessionId');
  const results = JSON.parse(sessionStorage.getItem('assessmentResults'));
  
  // Then save to database via API:
  await fetch('/api/assessments/complete', {
    method: 'POST',
    body: JSON.stringify({
      session_id: sessionId,
      results: results // Contains all the JSONB data
    })
  });
  ```
- The `raw_api_response` JSONB field should store the complete response from AWS Lambda's persona-trait endpoint

---

### 7. Connections Table

**Purpose**: User networking system (like LinkedIn connections)

```sql
CREATE TABLE connections (
  id                  UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  requester_id        UUID NOT NULL REFERENCES users(id) ON DELETE CASCADE,
  requested_id        UUID NOT NULL REFERENCES users(id) ON DELETE CASCADE,
  status              VARCHAR(50) NOT NULL DEFAULT 'pending',
  message             TEXT, -- Optional message with request
  requested_at        TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,
  responded_at        TIMESTAMP,
  created_at          TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,
  updated_at          TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,
  
  -- Prevent self-connections and duplicate requests
  CONSTRAINT chk_no_self_connection CHECK (requester_id != requested_id),
  CONSTRAINT uq_connection_pair UNIQUE (requester_id, requested_id)
);

-- Indexes
CREATE INDEX idx_connections_requester ON connections(requester_id);
CREATE INDEX idx_connections_requested ON connections(requested_id);
CREATE INDEX idx_connections_status ON connections(status);

-- Composite index for mutual connection queries
CREATE INDEX idx_connections_mutual ON connections(requester_id, requested_id, status);
```

**Status Values**:
- `'pending'` - Request sent, awaiting response
- `'accepted'` - Connection established
- `'rejected'` - Request declined
- `'blocked'` - User blocked the requester

**Notes**:
- Bidirectional relationship: if A→B is 'accepted', both can see each other
- Need application logic to prevent duplicate reverse requests (B→A when A→B exists)

---

### 8. Shared Results Table

**Purpose**: Publicly shareable assessment snapshots

```sql
CREATE TABLE shared_results (
  id                  UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  assessment_result_id UUID NOT NULL REFERENCES assessment_results(id) ON DELETE CASCADE,
  user_id             UUID NOT NULL REFERENCES users(id) ON DELETE CASCADE,
  share_token         VARCHAR(255) NOT NULL UNIQUE,
  visibility          VARCHAR(50) NOT NULL DEFAULT 'public',
  
  -- What to share (privacy controls)
  show_full_name      BOOLEAN DEFAULT TRUE,
  show_email          BOOLEAN DEFAULT FALSE,
  show_scores         BOOLEAN DEFAULT TRUE,
  show_analysis       BOOLEAN DEFAULT FALSE, -- Full analysis text
  show_recommendations BOOLEAN DEFAULT FALSE,
  
  -- Tracking
  view_count          INTEGER DEFAULT 0,
  last_viewed_at      TIMESTAMP,
  
  -- Expiration
  expires_at          TIMESTAMP, -- NULL = never expires
  is_active           BOOLEAN DEFAULT TRUE,
  
  created_at          TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,
  updated_at          TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP
);

-- Indexes
CREATE INDEX idx_shared_results_token ON shared_results(share_token);
CREATE INDEX idx_shared_results_user_id ON shared_results(user_id);
CREATE INDEX idx_shared_results_active ON shared_results(is_active);
```

**Share Token**:
- Format: Short, URL-friendly string (e.g., 12-16 characters)
- Example: `a7B9k2Qx4mP1`
- Public URL: `https://app.com/share/a7B9k2Qx4mP1`

**Visibility Options**:
- `'public'` - Anyone with link can view
- `'connections_only'` - Only accepted connections can view
- `'private'` - Deactivated share

---

### 9. Compatibility Reports Table

**Purpose**: Store AI-generated compatibility analyses between two users

```sql
CREATE TABLE compatibility_reports (
  id                    UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  user_a_id             UUID NOT NULL REFERENCES users(id) ON DELETE CASCADE,
  user_b_id             UUID NOT NULL REFERENCES users(id) ON DELETE CASCADE,
  assessment_result_a_id UUID NOT NULL REFERENCES assessment_results(id) ON DELETE CASCADE,
  assessment_result_b_id UUID NOT NULL REFERENCES assessment_results(id) ON DELETE CASCADE,
  
  -- Compatibility Analysis
  compatibility_score   DECIMAL(4, 2), -- 0.00 to 10.00
  complementary_strengths TEXT[],
  potential_conflicts   TEXT[],
  collaboration_tips    TEXT[],
  communication_style_diff TEXT,
  
  -- Full Report
  full_analysis         TEXT,
  ai_generated_insights JSONB,
  
  -- Metadata
  generated_at          TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,
  generated_by_user_id  UUID REFERENCES users(id), -- Who requested the report
  is_mutual             BOOLEAN DEFAULT FALSE, -- Both users agreed to share
  
  created_at            TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,
  updated_at            TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,
  
  -- Ensure ordered pair (prevent duplicates)
  CONSTRAINT chk_user_order CHECK (user_a_id < user_b_id),
  CONSTRAINT uq_compatibility_pair UNIQUE (user_a_id, user_b_id)
);

-- Indexes
CREATE INDEX idx_compatibility_user_a ON compatibility_reports(user_a_id);
CREATE INDEX idx_compatibility_user_b ON compatibility_reports(user_b_id);
CREATE INDEX idx_compatibility_score ON compatibility_reports(compatibility_score);
```

**Notes**:
- Both users must have completed 'comprehensive' assessment
- `chk_user_order` ensures user_a_id < user_b_id to prevent duplicate (A,B) and (B,A)
- Reports should be regenerated if either user takes new assessment

---

### 10. Payment Transactions Table

**Purpose**: Audit trail for all monetary transactions

```sql
CREATE TABLE payment_transactions (
  id                  UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  company_id          UUID REFERENCES companies(id) ON DELETE SET NULL,
  user_id             UUID REFERENCES users(id) ON DELETE SET NULL, -- For individual purchases
  
  -- Transaction Details
  transaction_type    VARCHAR(50) NOT NULL, -- 'license_pack', 'individual_assessment'
  amount              DECIMAL(10, 2) NOT NULL,
  currency            VARCHAR(3) DEFAULT 'USD',
  status              VARCHAR(50) NOT NULL DEFAULT 'pending',
  
  -- Stripe Integration
  stripe_payment_intent_id VARCHAR(255) UNIQUE,
  stripe_charge_id    VARCHAR(255),
  stripe_invoice_id   VARCHAR(255),
  stripe_customer_id  VARCHAR(255),
  
  -- What Was Purchased
  license_pack_id     UUID REFERENCES license_packs(id),
  product_description TEXT,
  
  -- Timestamps
  initiated_at        TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,
  completed_at        TIMESTAMP,
  failed_at           TIMESTAMP,
  refunded_at         TIMESTAMP,
  
  -- Error Handling
  failure_reason      TEXT,
  refund_reason       TEXT,
  refund_amount       DECIMAL(10, 2),
  
  created_at          TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,
  updated_at          TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP
);

-- Indexes
CREATE INDEX idx_transactions_company_id ON payment_transactions(company_id);
CREATE INDEX idx_transactions_user_id ON payment_transactions(user_id);
CREATE INDEX idx_transactions_status ON payment_transactions(status);
CREATE INDEX idx_transactions_stripe_intent ON payment_transactions(stripe_payment_intent_id);
CREATE INDEX idx_transactions_created_at ON payment_transactions(created_at);
```

**Transaction Status**:
- `'pending'` - Payment initiated
- `'processing'` - Stripe processing
- `'succeeded'` - Payment successful
- `'failed'` - Payment failed
- `'refunded'` - Full or partial refund issued

---

### 11. Audit Logs Table

**Purpose**: Track important system events and user actions

```sql
CREATE TABLE audit_logs (
  id                  UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  user_id             UUID REFERENCES users(id) ON DELETE SET NULL,
  company_id          UUID REFERENCES companies(id) ON DELETE SET NULL,
  
  -- Event Information
  event_type          VARCHAR(100) NOT NULL,
  event_category      VARCHAR(50), -- 'auth', 'assessment', 'admin', 'payment'
  description         TEXT,
  
  -- Context
  ip_address          INET,
  user_agent          TEXT,
  
  -- Data
  metadata            JSONB, -- Flexible data storage
  
  -- Timestamp
  created_at          TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP
);

-- Indexes
CREATE INDEX idx_audit_logs_user_id ON audit_logs(user_id);
CREATE INDEX idx_audit_logs_company_id ON audit_logs(company_id);
CREATE INDEX idx_audit_logs_event_type ON audit_logs(event_type);
CREATE INDEX idx_audit_logs_created_at ON audit_logs(created_at);

-- Partitioning recommendation: Partition by created_at monthly
```

**Event Types** (examples):
- `'user.registered'`
- `'user.login'`
- `'invitation.sent'`
- `'invitation.accepted'`
- `'assessment.started'`
- `'assessment.completed'`
- `'license.purchased'`
- `'connection.requested'`
- `'result.shared'`

---

### 12. Sessions Table (for NextAuth)

**Purpose**: Manage user session tokens

```sql
CREATE TABLE sessions (
  id                  UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  user_id             UUID NOT NULL REFERENCES users(id) ON DELETE CASCADE,
  session_token       VARCHAR(255) NOT NULL UNIQUE,
  expires             TIMESTAMP NOT NULL,
  created_at          TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP
);

-- Indexes
CREATE INDEX idx_sessions_user_id ON sessions(user_id);
CREATE INDEX idx_sessions_token ON sessions(session_token);
CREATE INDEX idx_sessions_expires ON sessions(expires);
```

**Notes**:
- Required for NextAuth database sessions
- Clean up expired sessions regularly (cron job)

---

### 13. Verification Tokens Table (for NextAuth)

**Purpose**: Email verification and password reset tokens

```sql
CREATE TABLE verification_tokens (
  identifier          VARCHAR(255) NOT NULL, -- email address
  token               VARCHAR(255) NOT NULL UNIQUE,
  expires             TIMESTAMP NOT NULL,
  created_at          TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,
  
  PRIMARY KEY (identifier, token)
);

-- Indexes
CREATE INDEX idx_verification_tokens_token ON verification_tokens(token);
CREATE INDEX idx_verification_tokens_expires ON verification_tokens(expires);
```

---

## Database Functions & Triggers

### Auto-Update `updated_at` Timestamp

```sql
-- Function to update updated_at column
CREATE OR REPLACE FUNCTION update_updated_at_column()
RETURNS TRIGGER AS $$
BEGIN
   NEW.updated_at = CURRENT_TIMESTAMP;
   RETURN NEW;
END;
$$ LANGUAGE plpgsql;

-- Apply to all tables with updated_at
CREATE TRIGGER update_users_updated_at BEFORE UPDATE ON users
  FOR EACH ROW EXECUTE FUNCTION update_updated_at_column();

CREATE TRIGGER update_companies_updated_at BEFORE UPDATE ON companies
  FOR EACH ROW EXECUTE FUNCTION update_updated_at_column();

CREATE TRIGGER update_license_packs_updated_at BEFORE UPDATE ON license_packs
  FOR EACH ROW EXECUTE FUNCTION update_updated_at_column();

-- Repeat for all tables with updated_at column
```

### License Consumption Helper

```sql
-- Function to consume a license from available pool
CREATE OR REPLACE FUNCTION consume_license(
  p_company_id UUID
) RETURNS UUID AS $$
DECLARE
  v_license_pack_id UUID;
BEGIN
  -- Find first active pack with available licenses
  SELECT id INTO v_license_pack_id
  FROM license_packs
  WHERE company_id = p_company_id
    AND status = 'active'
    AND available_licenses > 0
    AND (expiration_date IS NULL OR expiration_date > CURRENT_TIMESTAMP)
  ORDER BY purchase_date ASC -- FIFO
  LIMIT 1
  FOR UPDATE; -- Lock the row
  
  IF v_license_pack_id IS NULL THEN
    RAISE EXCEPTION 'No available licenses for company %', p_company_id;
  END IF;
  
  -- Increment used_licenses
  UPDATE license_packs
  SET used_licenses = used_licenses + 1
  WHERE id = v_license_pack_id;
  
  RETURN v_license_pack_id;
END;
$$ LANGUAGE plpgsql;
```

### Auto-Expire Invitations

```sql
-- Function to auto-expire old invitations
CREATE OR REPLACE FUNCTION expire_old_invitations()
RETURNS INTEGER AS $$
DECLARE
  v_expired_count INTEGER;
BEGIN
  UPDATE invitations
  SET status = 'expired'
  WHERE status = 'pending'
    AND expires_at < CURRENT_TIMESTAMP;
  
  GET DIAGNOSTICS v_expired_count = ROW_COUNT;
  RETURN v_expired_count;
END;
$$ LANGUAGE plpgsql;

-- Run via cron job daily
```

---

## Indexes Summary

**Critical Indexes** (must have):
- All foreign keys should be indexed
- `users.email` (unique, frequent lookups)
- `assessments.session_id` (API calls)
- `invitations.token` (registration flow)
- `shared_results.share_token` (public access)

**Performance Indexes**:
- Composite index on `(user_id, status)` for dashboards
- JSONB GIN indexes for skill/domain score queries
- Timestamp indexes for date range queries

---

## Data Relationships Diagram

```
companies (1) ──< (N) users
companies (1) ──< (N) license_packs
companies (1) ──< (N) invitations

users (1) ──< (N) assessments
users (1) ──< (N) invitations (as inviter)
users (1) ──< (1) invitations (as invitee)

assessments (1) ──< (1) assessment_results

users (N) ──< (N) connections

assessment_results (1) ──< (N) shared_results
assessment_results (2) ──< (1) compatibility_reports

companies/users ──< (N) payment_transactions
```

---

## Migration Strategy

### Phase 1: Core Tables (Week 1)
1. `users`
2. `companies`
3. `sessions`
4. `verification_tokens`
5. `audit_logs`

**Goal**: Enable authentication and basic user management

### Phase 2: Business Logic (Week 2)
1. `license_packs`
2. `invitations`
3. `payment_transactions`

**Goal**: Enable paid features and team management

### Phase 3: Assessment Storage (Week 2-3)
1. `assessments`
2. `assessment_results`

**Goal**: Persist assessment data

### Phase 4: Social Features (Week 3-4)
1. `connections`
2. `shared_results`
3. `compatibility_reports`

**Goal**: Enable networking and sharing

---

## Sample Queries

### Get Available Licenses for Company

```sql
SELECT 
  SUM(available_licenses) as total_available,
  COUNT(*) as active_packs
FROM license_packs
WHERE company_id = $1
  AND status = 'active'
  AND (expiration_date IS NULL OR expiration_date > CURRENT_TIMESTAMP);
```

### Get Manager's Team Dashboard

```sql
SELECT 
  u.id,
  u.name,
  u.email,
  i.sent_at as invited_at,
  a.completed_at,
  CASE 
    WHEN a.completed_at IS NOT NULL THEN 'completed'
    WHEN u.id IS NOT NULL THEN 'registered'
    ELSE 'pending'
  END as status
FROM invitations i
LEFT JOIN users u ON i.invitee_id = u.id
LEFT JOIN assessments a ON u.id = a.user_id AND a.status = 'completed'
WHERE i.company_id = $1
  AND i.status IN ('pending', 'accepted')
ORDER BY i.sent_at DESC;
```

### Get User's Assessment History

```sql
SELECT 
  a.id,
  a.session_id, -- AWS Lambda session ID
  a.assessment_type,
  a.started_at,
  a.completed_at,
  a.status,
  a.questions_answered,
  ar.overall_score,
  ar.primary_persona_name
FROM assessments a
LEFT JOIN assessment_results ar ON a.id = ar.assessment_id
WHERE a.user_id = $1
ORDER BY a.started_at DESC;
```

### Retrieve Assessment by Session ID (for frontend)

```sql
-- When user navigates to report page with sessionStorage data
SELECT 
  a.id as assessment_id,
  a.user_id,
  a.session_id,
  a.completed_at,
  ar.*
FROM assessments a
JOIN assessment_results ar ON a.id = ar.assessment_id
WHERE a.session_id = $1; -- session_id from sessionStorage
```

### Find Mutual Connections

```sql
-- Users who are mutually connected
SELECT DISTINCT
  CASE 
    WHEN c.requester_id = $1 THEN c.requested_id
    ELSE c.requester_id
  END as connection_user_id,
  u.name,
  u.email,
  u.avatar_url
FROM connections c
JOIN users u ON (
  (c.requester_id = $1 AND u.id = c.requested_id) OR
  (c.requested_id = $1 AND u.id = c.requester_id)
)
WHERE c.status = 'accepted'
  AND (c.requester_id = $1 OR c.requested_id = $1);
```

---

## Security Considerations

### Row-Level Security (RLS)

Consider implementing RLS policies for multi-tenant isolation:

```sql
-- Example: Users can only see their own company's data
ALTER TABLE users ENABLE ROW LEVEL SECURITY;

CREATE POLICY user_company_isolation ON users
  FOR ALL
  TO authenticated_user
  USING (
    company_id = current_setting('app.current_company_id')::UUID
    OR id = current_setting('app.current_user_id')::UUID
  );
```

### Encryption

- **At Rest**: Enable PostgreSQL encryption (AWS RDS encryption, etc.)
- **In Transit**: Enforce SSL/TLS connections
- **Application Level**: Encrypt sensitive JSONB fields if needed

### Sensitive Data

Fields requiring extra protection:
- `users.password_hash` (already bcrypt)
- `payment_transactions.*` (PCI compliance if storing card data)
- `audit_logs.ip_address` (GDPR considerations)

**Recommendation**: Store payment card data in Stripe only, not in your database.

---

## Backup & Recovery

### Backup Schedule
- **Frequency**: Daily automated backups
- **Retention**: 30 days
- **Testing**: Monthly restore tests

### Point-in-Time Recovery
- Enable WAL archiving
- Maintain 7-day PITR window

### Critical Tables Priority
1. `assessment_results` (user data loss = critical)
2. `users` (authentication)
3. `license_packs` (financial)
4. `payment_transactions` (audit trail)

---

## Performance Optimization

### Connection Pooling

```javascript
// Recommended pool settings for Next.js API routes
const pool = new Pool({
  max: 20,              // Maximum connections
  idleTimeoutMillis: 30000,
  connectionTimeoutMillis: 2000,
});
```

### Query Optimization

- Use prepared statements for repeated queries
- Implement pagination for large result sets
- Add `EXPLAIN ANALYZE` for slow queries
- Monitor with `pg_stat_statements`

### Caching Strategy

- Cache user profile data (5 min TTL)
- Cache assessment results (immutable after creation)
- Cache company license counts (1 min TTL)

---

## Monitoring & Alerts

### Key Metrics to Track

1. **Connection Pool**:
   - Active connections
   - Idle connections
   - Wait time

2. **Query Performance**:
   - Slow queries (> 1000ms)
   - Most frequent queries
   - Table scan frequency

3. **Storage**:
   - Database size growth
   - Table bloat
   - Index usage

### Recommended Tools

- **AWS RDS**: CloudWatch metrics + Performance Insights
- **Self-hosted**: pg_stat_statements + pgAdmin
- **APM**: Datadog, New Relic, or Sentry

---

## Environment Variables

Required database connection variables:

```env
# Database Connection
DATABASE_URL="postgresql://username:password@host:port/database?schema=public"

# Connection Pool (optional)
DATABASE_POOL_MIN=2
DATABASE_POOL_MAX=20

# SSL Configuration
DATABASE_SSL_ENABLED=true
DATABASE_SSL_REJECT_UNAUTHORIZED=true
```

---

## Initial Seed Data

### Admin User

```sql
-- Create default admin (password: changeme123)
INSERT INTO users (id, email, name, password_hash, role, email_verified)
VALUES (
  gen_random_uuid(),
  'admin@mirrormindscompass.com',
  'System Admin',
  '$2b$10$rQW.eBqLZZV7VjOAGVDWXOD3RmNVUxPvXQR0LYLu7vYKiQqKTvMGC', -- bcrypt('changeme123')
  'admin',
  true
);
```

### Sample Company (for testing)

```sql
INSERT INTO companies (id, name, slug)
VALUES (
  gen_random_uuid(),
  'Demo Company',
  'demo-company'
);
```

---

## Support & Maintenance

### Regular Maintenance Tasks

**Weekly**:
- Vacuum analyze on large tables
- Check for long-running queries
- Review slow query log

**Monthly**:
- Full database vacuum
- Index rebuild if needed
- Audit table sizes

**Quarterly**:
- Update PostgreSQL minor version
- Review and optimize indexes
- Analyze query patterns for new indexes

---

## Questions for Backend Team

1. **Hosting Platform**: AWS RDS, Supabase, Neon, or self-hosted?
2. **Backup Strategy**: Automated backups configured?
3. **Migration Tool**: Using Prisma Migrate, Flyway, or custom SQL scripts?
4. **Connection Pooling**: PgBouncer or application-level?
5. **SSL/TLS**: Certificate configuration for encrypted connections?
6. **Monitoring**: Which tools will be used for DB monitoring?
7. **Disaster Recovery**: RTO/RPO requirements?

---

## Critical Frontend-Backend Session Mapping

### Current Frontend Flow (SessionStorage)

**Location**: `app/leader/assessment/page.tsx`

```javascript
// STEP 1: Start assessment (already working)
const startResponse = await interviewerService.startInterview({
  persona: 'mentor',
  candidate_persona: 'professional',
  max_questions: 20
});

const sessionId = startResponse.session_id; // e.g., "session_1730795234567"
sessionStorage.setItem('sessionId', sessionId);

// STEP 2: During assessment - questions answered
// (progress tracked by AWS Lambda, not stored locally)

// STEP 3: Complete assessment
if (submitResponse.interview_complete) {
  // Store results in sessionStorage
  sessionStorage.setItem('assessmentResults', JSON.stringify({
    summary: submitResponse.summary,
    final_results: submitResponse.final_results,
    interview_complete: true,
    completion_reason: submitResponse.completion_reason
  }));
  
  // Navigate to report
  router.push('/leader/report');
}
```

**Location**: `app/leader/report/page.tsx`

```javascript
// STEP 4: Display report
const resultsStr = sessionStorage.getItem('assessmentResults');
const storedSessionId = sessionStorage.getItem('sessionId');

const results = JSON.parse(resultsStr);

// STEP 5: Fetch persona traits (already working)
const traits = await interviewerService.getPersonaTraits(storedSessionId);
// Calls: GET https://...amazonaws.com/dev/api/interviewer/persona-trait/{sessionId}
```

### Required Backend API Endpoints

#### 1. POST `/api/assessments/start`
**Purpose**: Create database record when assessment begins

```javascript
// Request Body
{
  "session_id": "session_1730795234567",
  "assessment_type": "comprehensive",
  "persona": "mentor",
  "candidate_persona": "professional",
  "max_questions": 20
}

// Response
{
  "success": true,
  "assessment_id": "uuid-here",
  "session_id": "session_1730795234567"
}
```

**SQL Operation**:
```sql
INSERT INTO assessments (
  user_id,
  session_id,
  assessment_type,
  persona,
  candidate_persona,
  max_questions,
  status
) VALUES (
  $user_id_from_session, -- NextAuth current user
  $session_id,
  $assessment_type,
  $persona,
  $candidate_persona,
  $max_questions,
  'in_progress'
);
```

#### 2. POST `/api/assessments/complete`
**Purpose**: Save results when assessment finishes

```javascript
// Request Body
{
  "session_id": "session_1730795234567",
  "results": {
    "summary": {
      "overall_score": 7.0,
      "strengths": [...],
      "areas_for_improvement": [...],
      "recommendations": [...],
      "analysis": "..."
    },
    "final_results": {
      "skill_scores": {...},
      "domain_scores": {...},
      "hierarchical_results": {...}
    },
    "completion_reason": "max_questions"
  },
  "persona_traits": {
    "primary_trait": {...},
    "secondary_traits": [...],
    "ranked_personas": [...],
    "domain_scores": {...}
  }
}

// Response
{
  "success": true,
  "assessment_id": "uuid-here",
  "result_id": "uuid-here"
}
```

**SQL Operations**:
```sql
-- 1. Update assessment status
UPDATE assessments
SET 
  status = 'completed',
  completed_at = CURRENT_TIMESTAMP,
  duration_minutes = EXTRACT(EPOCH FROM (CURRENT_TIMESTAMP - started_at)) / 60
WHERE session_id = $session_id;

-- 2. Insert results
INSERT INTO assessment_results (
  assessment_id,
  overall_score,
  primary_persona_code,
  primary_persona_name,
  primary_persona_score,
  primary_description,
  skill_scores,
  domain_scores,
  ranked_personas,
  secondary_personas,
  strengths,
  areas_for_improvement,
  recommendations,
  overall_analysis,
  completion_reason,
  raw_api_response
) VALUES (
  (SELECT id FROM assessments WHERE session_id = $session_id),
  $overall_score,
  $persona_traits.primary_trait.persona_code,
  $persona_traits.primary_trait.persona_name,
  $persona_traits.primary_trait.score,
  $persona_traits.primary_trait.description,
  $results.final_results.skill_scores::jsonb,
  $persona_traits.domain_scores::jsonb,
  $persona_traits.ranked_personas::jsonb,
  $persona_traits.secondary_traits::jsonb,
  $results.summary.strengths,
  $results.summary.areas_for_improvement,
  $results.summary.recommendations,
  $results.summary.analysis,
  $results.completion_reason,
  jsonb_build_object('results', $results, 'persona_traits', $persona_traits)
);
```

#### 3. GET `/api/assessments/results/:sessionId`
**Purpose**: Retrieve saved results (instead of sessionStorage)

```javascript
// Response
{
  "success": true,
  "assessment": {
    "id": "uuid",
    "session_id": "session_1730795234567",
    "assessment_type": "comprehensive",
    "completed_at": "2025-11-13T10:30:00Z",
    "duration_minutes": 45
  },
  "results": {
    "overall_score": 7.0,
    "primary_persona": {
      "code": "S-S",
      "name": "The Stabilizer (S–S)",
      "score": 7.0,
      "description": "..."
    },
    "skill_scores": {...},
    "domain_scores": {...},
    "strengths": [...],
    "areas_for_improvement": [...],
    "recommendations": [...],
    "overall_analysis": "...",
    "ranked_personas": [...],
    "secondary_personas": [...]
  }
}
```

### Session ID Mapping Table

| Frontend Storage | Database Field | Purpose |
|-----------------|----------------|---------|
| `sessionStorage.getItem('sessionId')` | `assessments.session_id` | Link browser session to DB record |
| `sessionStorage.getItem('assessmentResults')` | `assessment_results.*` | Persist ephemeral data |
| NextAuth `session.user.id` | `assessments.user_id` | Ownership tracking |
| AWS Lambda response | `assessment_results.raw_api_response` | Complete audit trail |

### Migration Path for Existing Sessions

**Problem**: Current users have data in sessionStorage only

**Solution**: Hybrid approach during transition

```javascript
// app/leader/report/page.tsx (UPDATED)
const loadResults = async () => {
  const sessionId = sessionStorage.getItem('sessionId');
  
  if (!sessionId) {
    router.push('/leader/dashboard');
    return;
  }
  
  try {
    // NEW: Try database first
    const response = await fetch(`/api/assessments/results/${sessionId}`);
    if (response.ok) {
      const data = await response.json();
      setResults(data.results);
      setPersonaTraits(data.results); // Already includes persona data
      return;
    }
  } catch (error) {
    console.log('Results not in database, falling back to sessionStorage');
  }
  
  // FALLBACK: Use sessionStorage (existing behavior)
  const resultsStr = sessionStorage.getItem('assessmentResults');
  if (resultsStr) {
    const parsedResults = JSON.parse(resultsStr);
    setResults(parsedResults);
    
    // Fetch persona traits from API
    const traits = await interviewerService.getPersonaTraits(sessionId);
    setPersonaTraits(traits);
  }
};
```

end
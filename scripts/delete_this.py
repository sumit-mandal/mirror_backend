#!/usr/bin/env python3
"""
PostgreSQL storage for interview sessions/responses linked to existing users.
"""
import os
from contextlib import contextmanager
from datetime import datetime
from typing import Dict, List, Any, Optional

import sqlalchemy as sa
from sqlalchemy.dialects import postgresql as pg
from sqlalchemy.orm import declarative_base, relationship, sessionmaker, Session
from dotenv import load_dotenv

load_dotenv()

DATABASE_URL = (
    "postgresql+psycopg2://{user}:{password}@{host}:{port}/{db}".format(
        user=os.environ["DB_USER"],
        password=os.environ["DB_PASSWORD"],
        host=os.environ["DB_HOST"],
        port=os.environ.get("DB_PORT", 5432),
        db=os.environ["DB_NAME"],
    )
)

engine = sa.create_engine(DATABASE_URL, pool_pre_ping=True, echo=False)
SessionLocal = sessionmaker(bind=engine, expire_on_commit=False)
Base = declarative_base()


class InterviewSession(Base):
    __tablename__ = "interview_sessions"

    session_id = sa.Column(
        pg.UUID(as_uuid=True),
        primary_key=True,
        server_default=sa.text("gen_random_uuid()"),
    )
    user_id = sa.Column(
        pg.UUID(as_uuid=True),
        sa.ForeignKey("users.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    start_time = sa.Column(sa.TIMESTAMP(timezone=True), server_default=sa.func.now())
    end_time = sa.Column(sa.TIMESTAMP(timezone=True))
    max_questions = sa.Column(sa.Integer)
    total_questions = sa.Column(sa.Integer)
    progress_percentage = sa.Column(sa.Float)
    covered_skills = sa.Column(sa.Integer)
    total_skills = sa.Column(sa.Integer)
    completion_reason = sa.Column(sa.String(255))
    overall_score = sa.Column(sa.Float)
    status = sa.Column(sa.String(50), nullable=False, server_default="in_progress")

    responses = relationship(
        "InterviewResponse", back_populates="session", cascade="all, delete-orphan"
    )
    final_result = relationship(
        "FinalResult",
        back_populates="session",
        uselist=False,
        cascade="all, delete-orphan",
    )


class InterviewResponse(Base):
    __tablename__ = "interview_responses"

    id = sa.Column(sa.Integer, primary_key=True, autoincrement=True)
    session_id = sa.Column(
        pg.UUID(as_uuid=True),
        sa.ForeignKey("interview_sessions.session_id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    question_number = sa.Column(sa.Integer, nullable=False)
    question_text = sa.Column(sa.Text, nullable=False)
    user_response = sa.Column(sa.Text, nullable=False)
    question_type = sa.Column(sa.String(100))
    target_skills = sa.Column(pg.ARRAY(sa.String))
    timestamp = sa.Column(sa.TIMESTAMP(timezone=True), server_default=sa.func.now())

    session = relationship("InterviewSession", back_populates="responses")
    evaluations = relationship(
        "SkillEvaluation", back_populates="response", cascade="all, delete-orphan"
    )


class SkillEvaluation(Base):
    __tablename__ = "skill_evaluations"

    id = sa.Column(sa.Integer, primary_key=True, autoincrement=True)
    session_id = sa.Column(
        pg.UUID(as_uuid=True),
        sa.ForeignKey("interview_sessions.session_id", ondelete="CASCADE"),
        nullable=False,
    )
    response_id = sa.Column(
        sa.Integer,
        sa.ForeignKey("interview_responses.id", ondelete="CASCADE"),
        nullable=False,
    )
    skill_name = sa.Column(sa.String(255), nullable=False)
    score = sa.Column(sa.Float)
    confidence_level = sa.Column(sa.Float)
    reasoning = sa.Column(sa.Text)
    timestamp = sa.Column(sa.TIMESTAMP(timezone=True), server_default=sa.func.now())

    response = relationship("InterviewResponse", back_populates="evaluations")


class FinalResult(Base):
    __tablename__ = "final_results"

    session_id = sa.Column(
        pg.UUID(as_uuid=True),
        sa.ForeignKey("interview_sessions.session_id", ondelete="CASCADE"),
        primary_key=True,
    )
    overall_score = sa.Column(sa.Float)
    domain_scores = sa.Column(pg.JSONB, default=dict)
    skill_scores = sa.Column(pg.JSONB, default=dict)
    hierarchical_results = sa.Column(pg.JSONB, default=dict)
    summary = sa.Column(pg.JSONB, default=dict)
    created_at = sa.Column(sa.TIMESTAMP(timezone=True), server_default=sa.func.now())

    session = relationship("InterviewSession", back_populates="final_result")


@contextmanager
def get_db_session() -> Session:
    session = SessionLocal()
    try:
        yield session
        session.commit()
    except Exception:
        session.rollback()
        raise
    finally:
        session.close()


class InterviewDatabase:
    """PostgreSQL-backed storage for interview data"""

    def save_session_start(self, session_id: str, user_id: str, max_questions: int):
        with get_db_session() as db:
            db.merge(
                InterviewSession(
                    session_id=session_id,
                    user_id=user_id,
                    max_questions=max_questions,
                )
            )

    def save_response(
        self,
        session_id: str,
        question_number: int,
        question_text: str,
        user_response: str,
        question_type: str,
        target_skills: List[str],
    ) -> int:
        with get_db_session() as db:
            session_obj = (
                db.query(InterviewSession).filter_by(session_id=session_id).one()
            )
            response = InterviewResponse(
                session=session_obj,
                question_number=question_number,
                question_text=question_text,
                user_response=user_response,
                question_type=question_type,
                target_skills=target_skills,
            )
            db.add(response)
            session_obj.total_questions = question_number
            db.flush()
            return response.id

    def save_evaluation(
        self, session_id: str, response_id: int, evaluation: Dict[str, Any]
    ):
        with get_db_session() as db:
            entries = [
                SkillEvaluation(
                    session_id=session_id,
                    response_id=response_id,
                    skill_name=skill,
                    score=score,
                    confidence_level=evaluation.get("confidence_level", 0.0),
                    reasoning=evaluation.get("reasoning", ""),
                )
                for skill, score in evaluation.get("skill_scores", {}).items()
            ]
            db.add_all(entries)

    def save_session_completion(
        self, session_id: str, final_results: Dict[str, Any], completion_reason: str
    ):
        with get_db_session() as db:
            session_obj = (
                db.query(InterviewSession).filter_by(session_id=session_id).one()
            )
            session_obj.end_time = datetime.utcnow()
            session_obj.progress_percentage = final_results.get("interview_progress")
            session_obj.covered_skills = final_results.get("covered_skills")
            session_obj.total_skills = final_results.get("total_skills")
            session_obj.completion_reason = completion_reason
            session_obj.overall_score = final_results.get("overall_score")
            session_obj.status = "completed"

            db.merge(
                FinalResult(
                    session_id=session_id,
                    overall_score=final_results.get("overall_score"),
                    domain_scores=final_results.get("domain_scores", {}),
                    skill_scores=final_results.get("skill_scores", {}),
                    hierarchical_results=final_results.get("hierarchical_results", {}),
                    summary=final_results.get("summary", {}),
                )
            )

    def get_session_data(self, session_id: str) -> Optional[Dict[str, Any]]:
        with get_db_session() as db:
            session_obj = (
                db.query(InterviewSession)
                .filter_by(session_id=session_id)
                .options(
                    sa.orm.selectinload(InterviewSession.responses).selectinload(
                        InterviewResponse.evaluations
                    ),
                    sa.orm.selectinload(InterviewSession.final_result),
                )
                .first()
            )
            if not session_obj:
                return None

            data = {
                "session": {
                    "session_id": session_obj.session_id,
                    "user_id": str(session_obj.user_id),
                    "start_time": session_obj.start_time,
                    "end_time": session_obj.end_time,
                    "max_questions": session_obj.max_questions,
                    "total_questions": session_obj.total_questions,
                    "progress_percentage": session_obj.progress_percentage,
                    "covered_skills": session_obj.covered_skills,
                    "total_skills": session_obj.total_skills,
                    "completion_reason": session_obj.completion_reason,
                    "overall_score": session_obj.overall_score,
                    "status": session_obj.status,
                },
                "responses": [],
                "final_results": {},
            }

            for response in sorted(
                session_obj.responses, key=lambda r: r.question_number
            ):
                data["responses"].append(
                    {
                        "id": response.id,
                        "question_number": response.question_number,
                        "question_text": response.question_text,
                        "user_response": response.user_response,
                        "question_type": response.question_type,
                        "target_skills": response.target_skills,
                        "timestamp": response.timestamp,
                        "evaluations": [
                            {
                                "skill_name": ev.skill_name,
                                "score": ev.score,
                                "confidence_level": ev.confidence_level,
                                "reasoning": ev.reasoning,
                                "timestamp": ev.timestamp,
                            }
                            for ev in sorted(
                                response.evaluations, key=lambda e: e.skill_name
                            )
                        ],
                    }
                )

            if session_obj.final_result:
                fr = session_obj.final_result
                data["final_results"] = {
                    "session_id": session_id,
                    "overall_score": fr.overall_score,
                    "domain_scores": fr.domain_scores,
                    "skill_scores": fr.skill_scores,
                    "hierarchical_results": fr.hierarchical_results,
                    "summary": fr.summary,
                    "created_at": fr.created_at,
                }

            return data

    def get_all_sessions(self):
        with get_db_session() as db:
            rows = (
                db.query(InterviewSession)
                .order_by(InterviewSession.start_time.desc())
                .all()
            )
            return [
                {
                    "session_id": row.session_id,
                    "user_id": str(row.user_id),
                    "start_time": row.start_time,
                    "end_time": row.end_time,
                    "status": row.status,
                    "overall_score": row.overall_score,
                }
                for row in rows
            ]

    def get_session_statistics(self) -> Dict[str, Any]:
        with get_db_session() as db:
            total = db.query(sa.func.count(InterviewSession.session_id)).scalar() or 0
            completed = (
                db.query(sa.func.count(InterviewSession.session_id))
                .filter(InterviewSession.status == "completed")
                .scalar()
                or 0
            )
            avg_score = (
                db.query(sa.func.avg(FinalResult.overall_score))
                .filter(FinalResult.overall_score.isnot(None))
                .scalar()
                or 0.0
            )
            avg_questions = (
                db.query(sa.func.avg(InterviewSession.total_questions))
                .filter(InterviewSession.status == "completed")
                .scalar()
                or 0.0
            )

            return {
                "total_sessions": total,
                "completed_sessions": completed,
                "average_score": round(avg_score, 2),
                "average_questions": round(avg_questions, 1),
                "completion_rate": round((completed / total * 100) if total else 0, 1),
            }
from __future__ import annotations

from datetime import datetime, timezone
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from api.deps import get_db
from api.enums import PermissionCode, QuestionStatus
from api.models import AnswerVote, Product, ProductAnswer, ProductQuestion, QuestionReport, QuestionVote, User
from api.permissions import require_permission
from api.schemas import (
    ProductAnswerCreate,
    ProductAnswerResponse,
    ProductAnswerUpdate,
    ProductQuestionCreate,
    ProductQuestionListResponse,
    ProductQuestionResponse,
    ProductQuestionUpdate,
    QuestionModerationRequest,
    QuestionReportCreate,
)
from api.services.notification_service import notification_service

router = APIRouter(tags=["Product Questions & Answers"])


def _commit(db: Session, conflict: str = "The requested Q&A action already exists") -> None:
    try:
        db.commit()
    except IntegrityError as exc:
        db.rollback()
        raise HTTPException(status_code=409, detail=conflict) from exc


def _question_or_404(db: Session, question_id: UUID) -> ProductQuestion:
    row = db.query(ProductQuestion).filter(ProductQuestion.id == question_id).first()
    if row is None:
        raise HTTPException(status_code=404, detail="Question not found")
    return row


def _answer_or_404(db: Session, answer_id: UUID) -> ProductAnswer:
    row = db.query(ProductAnswer).filter(ProductAnswer.id == answer_id).first()
    if row is None:
        raise HTTPException(status_code=404, detail="Answer not found")
    return row


@router.post("/products/{product_id}/questions", response_model=ProductQuestionResponse, status_code=status.HTTP_201_CREATED)
def create_question(
    product_id: UUID,
    payload: ProductQuestionCreate,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_permission(PermissionCode.product_questions_create.value)),
):
    product = db.query(Product).filter(Product.id == product_id, Product.is_active.is_(True)).first()
    if product is None:
        raise HTTPException(status_code=404, detail="Product not found")
    question = ProductQuestion(product_id=product.id, customer_id=current_user.id, question=payload.question)
    db.add(question)
    db.flush()
    if product.seller and product.seller.user_id:
        notification_service.notify(
            db=db,
            user_id=product.seller.user_id,
            event="system_alert",
            title="New product question",
            message=f'A customer asked a question about "{product.name}".',
            data={"question_id": str(question.id), "product_id": str(product.id)},
            action_url=f"/seller/questions/{question.id}",
            commit=False,
        )
    _commit(db)
    db.refresh(question)
    return ProductQuestionResponse.model_validate(question)


@router.get("/products/{product_id}/questions", response_model=ProductQuestionListResponse)
def list_product_questions(
    product_id: UUID,
    page: int = Query(default=1, ge=1),
    page_size: int = Query(default=20, ge=1, le=100),
    db: Session = Depends(get_db),
):
    query = db.query(ProductQuestion).filter(
        ProductQuestion.product_id == product_id,
        ProductQuestion.status == QuestionStatus.published,
    )
    total = query.count()
    rows = query.order_by(ProductQuestion.created_at.desc()).offset((page - 1) * page_size).limit(page_size).all()
    return ProductQuestionListResponse(total=total, page=page, page_size=page_size, results=rows)


@router.patch("/questions/{question_id}", response_model=ProductQuestionResponse)
def update_question(
    question_id: UUID,
    payload: ProductQuestionUpdate,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_permission(PermissionCode.product_questions_update.value)),
):
    question = _question_or_404(db, question_id)
    if question.customer_id != current_user.id:
        raise HTTPException(status_code=403, detail="You may only update your own question")
    question.question = payload.question
    question.status = QuestionStatus.published
    _commit(db)
    db.refresh(question)
    return ProductQuestionResponse.model_validate(question)


@router.delete("/questions/{question_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_question(
    question_id: UUID,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_permission(PermissionCode.product_questions_delete.value)),
):
    question = _question_or_404(db, question_id)
    if question.customer_id != current_user.id:
        raise HTTPException(status_code=403, detail="You may only delete your own question")
    db.delete(question)
    _commit(db)


@router.post("/questions/{question_id}/answers", response_model=ProductAnswerResponse, status_code=status.HTTP_201_CREATED)
def create_answer(
    question_id: UUID,
    payload: ProductAnswerCreate,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_permission(PermissionCode.product_answers_create.value)),
):
    question = _question_or_404(db, question_id)
    is_seller = bool(current_user.seller_profile and current_user.seller_profile.id == question.product.seller_id)
    answer = ProductAnswer(
        question_id=question.id,
        user_id=current_user.id,
        answer=payload.answer,
        is_seller_answer=is_seller,
        is_official=is_seller,
    )
    db.add(answer)
    question.answer_count += 1
    db.flush()
    notification_service.notify(
        db=db,
        user_id=question.customer_id,
        event="system_alert",
        title="Your product question was answered",
        message="A new answer was posted to your product question.",
        data={"question_id": str(question.id), "answer_id": str(answer.id)},
        action_url=f"/questions/{question.id}",
        commit=False,
    )
    _commit(db)
    db.refresh(answer)
    return ProductAnswerResponse.model_validate(answer)


@router.patch("/answers/{answer_id}", response_model=ProductAnswerResponse)
def update_answer(
    answer_id: UUID,
    payload: ProductAnswerUpdate,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_permission(PermissionCode.product_answers_update.value)),
):
    answer = _answer_or_404(db, answer_id)
    if answer.user_id != current_user.id:
        raise HTTPException(status_code=403, detail="You may only update your own answer")
    answer.answer = payload.answer
    _commit(db)
    db.refresh(answer)
    return ProductAnswerResponse.model_validate(answer)


@router.delete("/answers/{answer_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_answer(
    answer_id: UUID,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_permission(PermissionCode.product_answers_update.value)),
):
    answer = _answer_or_404(db, answer_id)
    if answer.user_id != current_user.id:
        raise HTTPException(status_code=403, detail="You may only delete your own answer")
    answer.question.answer_count = max(0, answer.question.answer_count - 1)
    db.delete(answer)
    _commit(db)


@router.post("/questions/{question_id}/helpful", response_model=ProductQuestionResponse)
def vote_question_helpful(
    question_id: UUID,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_permission(PermissionCode.product_questions_read.value)),
):
    question = _question_or_404(db, question_id)
    db.add(QuestionVote(question_id=question.id, user_id=current_user.id))
    question.helpful_count += 1
    _commit(db, "You already marked this question as helpful")
    db.refresh(question)
    return ProductQuestionResponse.model_validate(question)


@router.post("/answers/{answer_id}/helpful", response_model=ProductAnswerResponse)
def vote_answer_helpful(
    answer_id: UUID,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_permission(PermissionCode.product_questions_read.value)),
):
    answer = _answer_or_404(db, answer_id)
    db.add(AnswerVote(answer_id=answer.id, user_id=current_user.id))
    answer.helpful_count += 1
    _commit(db, "You already marked this answer as helpful")
    db.refresh(answer)
    return ProductAnswerResponse.model_validate(answer)


@router.post("/questions/{question_id}/report", status_code=status.HTTP_201_CREATED)
def report_question(
    question_id: UUID,
    payload: QuestionReportCreate,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_permission(PermissionCode.product_questions_read.value)),
):
    question = _question_or_404(db, question_id)
    report = QuestionReport(question_id=question.id, reported_by_id=current_user.id, reason=payload.reason, details=payload.details)
    db.add(report)
    _commit(db, "You already reported this question")
    return {"message": "Question reported successfully", "report_id": str(report.id)}


@router.get("/seller/questions", response_model=ProductQuestionListResponse)
def seller_questions(
    unanswered_only: bool = False,
    page: int = Query(default=1, ge=1),
    page_size: int = Query(default=20, ge=1, le=100),
    db: Session = Depends(get_db),
    current_user: User = Depends(require_permission(PermissionCode.seller_questions_read.value)),
):
    if current_user.seller_profile is None:
        raise HTTPException(status_code=403, detail="Seller profile required")
    query = db.query(ProductQuestion).join(Product).filter(Product.seller_id == current_user.seller_profile.id)
    if unanswered_only:
        query = query.filter(ProductQuestion.answer_count == 0)
    total = query.count()
    rows = query.order_by(ProductQuestion.created_at.desc()).offset((page - 1) * page_size).limit(page_size).all()
    return ProductQuestionListResponse(total=total, page=page, page_size=page_size, results=rows)


@router.post("/seller/questions/{question_id}/answer", response_model=ProductAnswerResponse, status_code=status.HTTP_201_CREATED)
def seller_answer_question(
    question_id: UUID,
    payload: ProductAnswerCreate,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_permission(PermissionCode.seller_questions_answer.value)),
):
    question = _question_or_404(db, question_id)
    if current_user.seller_profile is None or question.product.seller_id != current_user.seller_profile.id:
        raise HTTPException(status_code=403, detail="This question does not belong to your product")
    answer = ProductAnswer(question_id=question.id, user_id=current_user.id, answer=payload.answer, is_seller_answer=True, is_official=True)
    db.add(answer)
    question.answer_count += 1
    db.flush()
    notification_service.notify(
        db=db, user_id=question.customer_id, event="system_alert", title="Seller answered your question",
        message="The seller posted an official answer to your product question.",
        data={"question_id": str(question.id), "answer_id": str(answer.id)}, commit=False,
    )
    _commit(db)
    db.refresh(answer)
    return ProductAnswerResponse.model_validate(answer)


@router.get("/admin/questions", response_model=ProductQuestionListResponse)
def admin_questions(
    question_status: QuestionStatus | None = None,
    page: int = Query(default=1, ge=1),
    page_size: int = Query(default=20, ge=1, le=100),
    db: Session = Depends(get_db),
    _: User = Depends(require_permission(PermissionCode.product_questions_moderate.value)),
):
    query = db.query(ProductQuestion)
    if question_status is not None:
        query = query.filter(ProductQuestion.status == question_status)
    total = query.count()
    rows = query.order_by(ProductQuestion.created_at.desc()).offset((page - 1) * page_size).limit(page_size).all()
    return ProductQuestionListResponse(total=total, page=page, page_size=page_size, results=rows)


@router.patch("/admin/questions/{question_id}/moderate", response_model=ProductQuestionResponse)
def moderate_question(
    question_id: UUID,
    payload: QuestionModerationRequest,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_permission(PermissionCode.product_questions_moderate.value)),
):
    question = _question_or_404(db, question_id)
    question.status = payload.status
    question.moderation_note = payload.note
    question.moderated_by_id = current_user.id
    question.moderated_at = datetime.now(timezone.utc)
    _commit(db)
    db.refresh(question)
    return ProductQuestionResponse.model_validate(question)

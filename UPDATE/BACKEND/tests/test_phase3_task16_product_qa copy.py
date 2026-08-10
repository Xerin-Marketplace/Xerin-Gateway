from pathlib import Path

from api.enums import PermissionCode, QuestionReportReason, QuestionStatus
from api.main import api
from api.models import AnswerVote, ProductAnswer, ProductQuestion, QuestionReport, QuestionVote
from api.schemas import ProductAnswerCreate, ProductQuestionCreate


def test_task16_models_exist():
    assert ProductQuestion.__tablename__ == "product_questions"
    assert ProductAnswer.__tablename__ == "product_answers"
    assert QuestionVote.__tablename__ == "question_votes"
    assert AnswerVote.__tablename__ == "answer_votes"
    assert QuestionReport.__tablename__ == "question_reports"


def test_task16_enums_and_permissions_exist():
    assert QuestionStatus.published.value == "published"
    assert QuestionReportReason.spam.value == "spam"
    assert PermissionCode.product_questions_create.value == "product_questions:create"
    assert PermissionCode.seller_questions_answer.value == "seller_questions:answer"
    assert PermissionCode.product_questions_moderate.value == "product_questions:moderate"


def test_task16_schema_validation():
    assert ProductQuestionCreate(question="Is this compatible?").question == "Is this compatible?"
    assert ProductAnswerCreate(answer="Yes, it is compatible.").answer.startswith("Yes")


def test_task16_routes_registered():
    paths = api.openapi()["paths"]
    expected = {
        "/api/v1/products/{product_id}/questions",
        "/api/v1/questions/{question_id}",
        "/api/v1/questions/{question_id}/answers",
        "/api/v1/answers/{answer_id}",
        "/api/v1/questions/{question_id}/helpful",
        "/api/v1/answers/{answer_id}/helpful",
        "/api/v1/questions/{question_id}/report",
        "/api/v1/seller/questions",
        "/api/v1/seller/questions/{question_id}/answer",
        "/api/v1/admin/questions",
        "/api/v1/admin/questions/{question_id}/moderate",
    }
    assert expected.issubset(paths)


def test_task16_migration_chain():
    text = Path("alembic/versions/p3_product_qa.py").read_text()
    assert 'revision = "p3_product_qa"' in text
    assert 'down_revision = "p3_notifications"' in text
    for table in ("product_questions", "product_answers", "question_votes", "answer_votes", "question_reports"):
        assert table in text

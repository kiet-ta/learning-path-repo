"""
Unit Tests - Domain Entities
Tests for Repository, LearningPath, ProgressRecord, Skill, and Topic entities.

Follows the gen-test.md workflow:
  1 happy path
  3 sad/error paths
  boundary cases (edge inputs)
  mock only external I/O — domain entities have zero external deps
"""
import pytest
from uuid import uuid4
from datetime import datetime

from domain.entities.skill import Skill, SkillType, SkillLevel
from domain.entities.topic import Topic
from domain.entities.repository import Repository
from domain.entities.learning_path import LearningPath, PathStatus
from domain.entities.progress_record import ProgressRecord, ProgressStatus
from domain.exceptions.domain_exceptions import (
    ValidationError,
    BusinessRuleViolation,
    CircularDependencyError,
)


# ===========================================================================
# Helpers / Factories
# ===========================================================================

def make_skill(skill_type=SkillType.BACKEND, level=SkillLevel.INTERMEDIATE) -> Skill:
    return Skill(skill_type=skill_type, skill_level=level)


def make_topic(name="Django", category="framework") -> Topic:
    return Topic(name=name, description="A web framework", category=category)


def make_repository(
    name="my-repo",
    path="/repos/my-repo",
    language="python",
    skill: Skill | None = None,
) -> Repository:
    repo = Repository(name=name, path=path, primary_language=language)
    if skill:
        repo.set_primary_skill(skill)
    return repo


def make_learning_path(learner_id="learner-1", name="My Path") -> LearningPath:
    return LearningPath(name=name, description="Test path", learner_id=learner_id)


# ===========================================================================
# Skill tests
# ===========================================================================

class TestSkill:
    def test_skill_creation_happy_path(self):
        skill = make_skill()
        assert skill.skill_type == SkillType.BACKEND
        assert skill.skill_level == SkillLevel.INTERMEDIATE

    def test_skill_level_ordering(self):
        assert SkillLevel.BASIC < SkillLevel.INTERMEDIATE
        assert SkillLevel.INTERMEDIATE < SkillLevel.ADVANCED
        assert SkillLevel.ADVANCED < SkillLevel.EXPERT

    def test_skill_level_can_progress(self):
        assert SkillLevel.BASIC.can_progress_to(SkillLevel.EXPERT)
        assert not SkillLevel.EXPERT.can_progress_to(SkillLevel.BASIC)

    def test_skill_get_next_level(self):
        assert SkillLevel.BASIC.get_next_level() == SkillLevel.INTERMEDIATE
        assert SkillLevel.EXPERT.get_next_level() is None

    def test_compatible_types(self):
        compat = SkillType.get_compatible_types(SkillType.BACKEND)
        assert SkillType.FRONTEND in compat
        assert SkillType.DATA_SCIENCE in compat


# ===========================================================================
# Topic tests
# ===========================================================================

class TestTopic:
    def test_topic_creation_happy_path(self):
        topic = make_topic()
        assert topic.name == "Django"
        assert topic.category == "framework"

    def test_topic_name_empty_raises(self):
        with pytest.raises(ValidationError, match="name"):
            Topic(name="", description="desc", category="framework")

    def test_topic_name_too_long_raises(self):
        with pytest.raises(ValidationError, match="name"):
            Topic(name="x" * 101, description="desc", category="framework")

    def test_topic_invalid_category_raises(self):
        with pytest.raises(ValidationError, match="category"):
            Topic(name="Redis", description="cache", category="unknown_cat")

    def test_topic_boundary_name_exactly_100_chars(self):
        """Name of exactly 100 characters is valid."""
        topic = Topic(name="A" * 100, description="desc", category="tool")
        assert len(topic.name) == 100

    def test_topic_add_keyword(self):
        topic = make_topic()
        topic.add_keyword("web")
        assert "web" in topic.keywords

    def test_topic_add_empty_keyword_raises(self):
        topic = make_topic()
        with pytest.raises(ValidationError):
            topic.add_keyword("")


# ===========================================================================
# Repository tests
# ===========================================================================

class TestRepository:
    def test_repository_creation_happy_path(self):
        repo = make_repository()
        assert repo.name == "my-repo"
        assert repo.primary_language == "python"
        assert repo.content_hash is not None

    def test_repository_empty_name_raises(self):
        with pytest.raises(ValidationError, match="name"):
            Repository(name="", path="/p", primary_language="python")

    def test_repository_unsupported_language_raises(self):
        with pytest.raises(ValidationError, match="primary_language"):
            Repository(name="r", path="/p", primary_language="brainfuck")

    def test_repository_empty_path_raises(self):
        with pytest.raises(ValidationError, match="path"):
            Repository(name="r", path="", primary_language="python")

    def test_repository_add_topic(self):
        repo = make_repository()
        topic = make_topic()
        repo.add_topic(topic)
        assert topic in repo.topics

    def test_repository_duplicate_topic_is_idempotent(self):
        repo = make_repository()
        topic = make_topic()
        repo.add_topic(topic)
        repo.add_topic(topic)
        assert len(repo.topics) == 1

    def test_repository_set_primary_skill(self):
        repo = make_repository()
        skill = make_skill()
        repo.set_primary_skill(skill)
        assert repo.primary_skill == skill

    def test_repository_incompatible_skill_raises(self):
        """JavaScript repo cannot have DATA_SCIENCE primary skill."""
        repo = make_repository(language="javascript")
        skill = make_skill(skill_type=SkillType.DATA_SCIENCE)
        with pytest.raises((ValidationError, BusinessRuleViolation)):
            repo.set_primary_skill(skill)

    def test_repository_name_exactly_255_chars(self):
        """Boundary: 255-char name is valid."""
        repo = Repository(name="A" * 255, path="/p", primary_language="python")
        assert len(repo.name) == 255

    def test_repository_name_256_chars_raises(self):
        with pytest.raises(ValidationError, match="name"):
            Repository(name="A" * 256, path="/p", primary_language="python")


# ===========================================================================
# LearningPath tests
# ===========================================================================

class TestLearningPath:
    def test_learning_path_creation_happy_path(self):
        lp = make_learning_path()
        assert lp.status == PathStatus.DRAFT
        assert lp.nodes == []

    def test_learning_path_empty_name_raises(self):
        with pytest.raises(ValidationError, match="name"):
            LearningPath(name="", description="desc", learner_id="learner-1")

    def test_learning_path_empty_learner_id_raises(self):
        with pytest.raises(ValidationError, match="learner_id"):
            LearningPath(name="Path", description="desc", learner_id="")

    def test_learning_path_invalid_max_parallel_raises(self):
        with pytest.raises(ValidationError, match="max_parallel_nodes"):
            LearningPath(
                name="Path", description="desc", learner_id="l1",
                max_parallel_nodes=0,
            )

    def test_add_repository_creates_node(self):
        lp = make_learning_path()
        repo = make_repository()
        node = lp.add_repository(repo)
        assert node is not None
        assert len(lp.nodes) == 1

    def test_add_duplicate_repository_raises(self):
        lp = make_learning_path()
        repo = make_repository()
        lp.add_repository(repo)
        with pytest.raises(BusinessRuleViolation):
            lp.add_repository(repo)

    def test_total_metrics_recalculated(self):
        lp = make_learning_path()
        r1 = make_repository(name="r1", path="/repos/r1")
        r2 = make_repository(name="r2", path="/repos/r2")
        lp.add_repository(r1)
        lp.add_repository(r2)
        assert lp.total_repositories == 2


# ===========================================================================
# ProgressRecord tests
# ===========================================================================

class TestProgressRecord:
    def _make_record(self) -> ProgressRecord:
        return ProgressRecord(
            repository_id=uuid4(),
            learner_id="learner-1",
        )

    def test_progress_record_initial_state(self):
        record = self._make_record()
        assert record.status == ProgressStatus.NOT_STARTED
        assert record.progress_percentage == 0.0

    def test_start_learning_transitions_status(self):
        record = self._make_record()
        record.start_learning()
        assert record.status == ProgressStatus.IN_PROGRESS
        assert record.started_at is not None

    def test_complete_learning_sets_completed_at(self):
        record = self._make_record()
        record.start_learning()
        record.complete_learning()
        assert record.status == ProgressStatus.COMPLETED
        assert record.completed_at is not None
        assert record.progress_percentage == 100.0

    def test_complete_without_start_raises(self):
        record = self._make_record()
        with pytest.raises(BusinessRuleViolation):
            record.complete_learning()

    def test_difficulty_rating_boundary_valid(self):
        record = self._make_record()
        record.set_difficulty_rating(1)
        assert record.difficulty_rating == 1
        record.set_difficulty_rating(5)
        assert record.difficulty_rating == 5

    def test_difficulty_rating_out_of_range_raises(self):
        record = self._make_record()
        with pytest.raises(ValidationError):
            record.set_difficulty_rating(6)
        with pytest.raises(ValidationError):
            record.set_difficulty_rating(0)

    def test_add_time_accumulates(self):
        record = self._make_record()
        record.start_learning()
        # update_progress accumulates time_spent_minutes
        record.update_progress(20.0, time_spent_minutes=30)
        record.update_progress(40.0, time_spent_minutes=45)
        assert record.total_time_spent_minutes == 75

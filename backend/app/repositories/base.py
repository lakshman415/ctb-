"""
Generic repository base class.

Provides common CRUD operations that all repositories inherit.
Services interact with repositories — never with raw SQLAlchemy sessions directly.
This makes testing easy: mock the repository, not the ORM.
"""

from typing import Generic, TypeVar

from sqlalchemy.orm import Session

from app.core.database import Base

ModelType = TypeVar("ModelType", bound=Base)


class BaseRepository(Generic[ModelType]):
    """
    Generic repository providing basic CRUD.

    Subclasses specify the model class and add domain-specific queries.
    """

    def __init__(self, model: type[ModelType], db: Session):
        """
        Args:
            model: The SQLAlchemy model class this repository manages.
            db: Active database session.
        """
        self._model = model
        self._db = db

    def get_by_id(self, record_id: int) -> ModelType | None:
        """Fetch a single record by primary key."""
        return self._db.get(self._model, record_id)

    def get_all(self, skip: int = 0, limit: int = 100) -> list[ModelType]:
        """Fetch multiple records with pagination."""
        return (
            self._db.query(self._model)
            .offset(skip)
            .limit(limit)
            .all()
        )

    def create(self, obj: ModelType) -> ModelType:
        """Insert a new record and return it with generated fields."""
        self._db.add(obj)
        self._db.commit()
        self._db.refresh(obj)
        return obj

    def create_many(self, objects: list[ModelType]) -> list[ModelType]:
        """Bulk insert multiple records."""
        self._db.add_all(objects)
        self._db.commit()
        for obj in objects:
            self._db.refresh(obj)
        return objects

    def delete(self, record_id: int) -> bool:
        """Delete a record by primary key. Returns True if found and deleted."""
        obj = self.get_by_id(record_id)
        if obj:
            self._db.delete(obj)
            self._db.commit()
            return True
        return False

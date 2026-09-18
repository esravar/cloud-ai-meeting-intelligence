"""Small PostgreSQL + SQLAlchemy CRUD example.

Run from the project root:

    python examples/postgresql_sqlalchemy_demo.py

This example uses a separate `learning_notes` table and does not modify the
meeting intelligence tables.
"""

import os

from dotenv import load_dotenv
from sqlalchemy import String, create_engine, select
from sqlalchemy.orm import DeclarativeBase, Mapped, Session, mapped_column

load_dotenv()

# The URL format is:
# postgresql+psycopg://USERNAME:PASSWORD@HOST:PORT/DATABASE
DATABASE_URL = os.getenv(
    "DATABASE_URL",
    "postgresql+psycopg://meeting:meeting@localhost:5432/meeting_intelligence",
)


# All SQLAlchemy ORM models inherit from this base class.
class Base(DeclarativeBase):
    pass


# This Python class represents the PostgreSQL `learning_notes` table.
class Note(Base):
    __tablename__ = "learning_notes"

    id: Mapped[int] = mapped_column(primary_key=True)
    title: Mapped[str] = mapped_column(String(100), nullable=False)
    content: Mapped[str] = mapped_column(String(500), nullable=False)

    def __repr__(self) -> str:
        return f"Note(id={self.id}, title={self.title!r}, content={self.content!r})"


def main() -> None:
    # Engine manages the PostgreSQL connection pool. It does not connect until
    # a database operation actually needs a connection.
    engine = create_engine(DATABASE_URL, echo=True)

    # Creates the table only when it does not already exist.
    Base.metadata.create_all(engine)

    # `with` guarantees that the session is closed at the end.
    with Session(engine) as session:
        try:
            # INSERT: Creating a Python object does not write anything yet.
            note = Note(
                title="SQLAlchemy learning",
                content="A row is persisted when session.commit() succeeds.",
            )
            session.add(note)
            session.commit()

            # PostgreSQL generated the primary key during INSERT.
            session.refresh(note)
            print(f"\nCreated: {note}")

            # SELECT: SQLAlchemy turns this expression into a parameterized
            # SELECT query.
            statement = select(Note).where(Note.title == "SQLAlchemy learning")
            saved_note = session.scalar(statement)
            print(f"Selected: {saved_note}")

            if saved_note is None:
                raise RuntimeError("The inserted note could not be found.")

            # UPDATE: SQLAlchemy notices the changed attribute and generates an
            # UPDATE statement on commit.
            saved_note.content = "SQLAlchemy tracks object changes."
            session.commit()
            print(f"Updated: {saved_note}")

            # DELETE: The DELETE is finalized by commit.
            session.delete(saved_note)
            session.commit()
            print("Deleted the demo row.")

        except Exception:
            # If INSERT/UPDATE/DELETE fails, return the transaction to a clean
            # state before re-raising the error.
            session.rollback()
            raise


if __name__ == "__main__":
    main()

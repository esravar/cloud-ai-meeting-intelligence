# PostgreSQL + SQLAlchemy Learning Example

The demo uses the project's local PostgreSQL connection and creates a separate
table named `learning_notes`.

From the project root:

```bash
python examples/postgresql_sqlalchemy_demo.py
```

Set a different connection explicitly when needed:

```bash
DATABASE_URL="postgresql+psycopg://meeting:meeting@localhost:5432/meeting_intelligence" \
python examples/postgresql_sqlalchemy_demo.py
```

The script demonstrates:

1. Defining an ORM model.
2. Creating a PostgreSQL table.
3. Inserting and committing a row.
4. Selecting with a parameterized query.
5. Updating an ORM object.
6. Deleting a row.
7. Rolling back when an operation fails.
8. Closing the session automatically.

`echo=True` is intentionally enabled so the generated SQL appears in the
terminal.

"""Administrative SQL console."""

from sqlalchemy import text
from sqlmodel import Session

from core.database import engine

__all__ = [
    "execute_raw_sql",
]


def execute_raw_sql(query: str) -> dict:
    """
    Executes raw SQL query.
    Returns a dict with success status, headers/rows (for SELECT), or rowcount (for INSERT/UPDATE).
    """
    with Session(engine) as session:
        try:
            # Execute raw query
            result = session.execute(text(query))
            session.commit()

            # Check if it's a SELECT statement (returns rows)
            if result.returns_rows:
                headers = list(result.keys())
                # Convert all values to string for display safety
                rows = [list(map(str, row)) for row in result.all()]
                return {
                    "success": True,
                    "type": "select",
                    "headers": headers,
                    "rows": rows,
                }
            else:
                # INSERT / UPDATE / DELETE
                return {
                    "success": True,
                    "type": "modification",
                    "rows_affected": result.rowcount,
                }

        except Exception as e:
            return {"success": False, "error": str(e)}

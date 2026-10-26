"""Run a titled SQL query from supabase_queries.json against Supabase Postgres."""

import argparse
import json
import os
from pathlib import Path
from typing import Any

from dotenv import load_dotenv


QUERY_FILE = Path(__file__).with_name("supabase_queries.json")
ENV_FILE = Path(__file__).parent.parent / ".env"

# Load local credentials without overriding variables already set by the shell.
load_dotenv(ENV_FILE)

# Change this value when running the file without --title.
QUERY_TITLE = "add_projects_origin"


def load_queries(query_file: Path = QUERY_FILE) -> dict[str, dict[str, Any]]:
    """Load queries and index them by their unique title."""
    with query_file.open(encoding="utf-8") as file:
        document = json.load(file)

    queries = document.get("queries")
    if not isinstance(queries, list):
        raise ValueError("Query JSON must contain a 'queries' list.")

    by_title: dict[str, dict[str, Any]] = {}
    for query in queries:
        title = query.get("title")
        sql = query.get("sql")
        if not isinstance(title, str) or not title.strip():
            raise ValueError("Every query must have a non-empty string title.")
        if not isinstance(sql, str) or not sql.strip():
            raise ValueError(f"Query '{title}' must have non-empty SQL.")
        if title in by_title:
            raise ValueError(f"Duplicate query title: {title}")
        by_title[title] = query

    return by_title


def list_queries(queries: dict[str, dict[str, Any]]) -> None:
    """Print all available query titles and descriptions."""
    for title, query in queries.items():
        description = query.get("description", "")
        print(f"{title}: {description}")


def run_query(title: str, database_url: str) -> None:
    """Execute one titled query in a transaction."""
    queries = load_queries()
    if title not in queries:
        available = ", ".join(queries)
        raise KeyError(f"Unknown query title '{title}'. Available: {available}")

    try:
        import psycopg
    except ImportError as error:
        raise RuntimeError(
            "Install the PostgreSQL driver first: pip install 'psycopg[binary]'"
        ) from error

    with psycopg.connect(database_url) as connection:
        with connection.cursor() as cursor:
            # Some catalog entries intentionally contain multiple SQL statements.
            cursor.execute(queries[title]["sql"], prepare=False)

            if cursor.description:
                column_names = [column.name for column in cursor.description]
                print(" | ".join(column_names))
                print("-+-".join("-" * len(name) for name in column_names))
                for row in cursor.fetchall():
                    print(" | ".join(str(value) for value in row))

    print(f"Successfully ran query: {title}")


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Run a titled Supabase PostgreSQL query."
    )
    parser.add_argument(
        "--title",
        default=QUERY_TITLE,
        help=f"Query title from {QUERY_FILE.name} (default: {QUERY_TITLE}).",
    )
    parser.add_argument(
        "--list",
        action="store_true",
        help="List query titles without connecting to Supabase.",
    )
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    queries = load_queries()

    if args.list:
        list_queries(queries)
        return

    database_url = os.getenv("SUPABASE_DATABASE_URL")
    if not database_url:
        raise RuntimeError(
            "Set SUPABASE_DATABASE_URL to the Supabase Postgres connection string."
        )

    run_query(args.title, database_url)


if __name__ == "__main__":
    main()

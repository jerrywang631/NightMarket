"""Apply the Voucher Adventure session migration.

With DATABASE_URL set, the PostgreSQL migration is applied.  Otherwise the
local SQLite session database is created or upgraded.
"""

import argparse
import os

from voucher_adventure.repository import create_voucher_repository


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--sqlite-path",
        help="Optional SQLite path for local development and tests",
    )
    args = parser.parse_args()
    repository = create_voucher_repository(
        database_url=os.environ.get("DATABASE_URL"),
        sqlite_path=args.sqlite_path,
    )
    print("Voucher Adventure migration applied " f"using {repository.dialect}.")


if __name__ == "__main__":
    main()

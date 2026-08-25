"""Compare one branch's B-Connect stock with the main B-Connect database."""

from __future__ import annotations

import csv
import os
import sys
from contextlib import closing
from decimal import Decimal
from itertools import groupby
from operator import itemgetter
from pathlib import Path

import pyodbc


BRANCH_SERVER = os.getenv("BCONNECT_BRANCH_SERVER", "192.168.1.22")
MAIN_SERVER = os.getenv("BCONNECT_MAIN_SERVER", "192.168.3.0")
BRANCH_ID = int(os.getenv("BCONNECT_BRANCH_ID", "29"))
PORT = int(os.getenv("BCONNECT_PORT", "1433"))
DATABASE = os.getenv("BCONNECT_DATABASE", "genius")
USERNAME = os.getenv("BCONNECT_USER", "dev")
PASSWORD = os.getenv("BCONNECT_PASSWORD", "5LI53xqfPb")
CONNECTION_TIMEOUT = int(os.getenv("BCONNECT_CONNECTION_TIMEOUT", "10"))
QUERY_TIMEOUT = int(os.getenv("BCONNECT_QUERY_TIMEOUT", "60"))
OUTPUT_FILE = Path(
    os.getenv("BCONNECT_OUTPUT_FILE", f"stock_mismatch_branch_{BRANCH_ID}.csv")
)

ZERO = Decimal("0")

STOCK_QUERY = """
    SELECT
        itm_id,
        SUM(
            CASE
                WHEN itm_qty > 0 THEN CAST(itm_qty AS DECIMAL(38, 6))
                ELSE CAST(0 AS DECIMAL(38, 6))
            END
        ) AS stock_qty
    FROM dbo.Item_Class_Store WITH (NOLOCK)
    WHERE sto_id = ?
    GROUP BY itm_id
    HAVING SUM(
        CASE
            WHEN itm_qty > 0 THEN CAST(itm_qty AS DECIMAL(38, 6))
            ELSE CAST(0 AS DECIMAL(38, 6))
        END
    ) > 0
    ORDER BY itm_id
"""


def _get_sql_server_driver() -> str:
    drivers = pyodbc.drivers()
    preferred = (
        "ODBC Driver 18 for SQL Server",
        "ODBC Driver 17 for SQL Server",
        "ODBC Driver 13 for SQL Server",
        "ODBC Driver 11 for SQL Server",
        "SQL Server Native Client 11.0",
        "SQL Server",
    )
    for driver in preferred:
        if driver in drivers:
            return driver
    raise RuntimeError("No Microsoft SQL Server ODBC driver is installed.")


def _connection_string(server: str, driver: str) -> str:
    return (
        f"DRIVER={{{driver}}};"
        f"SERVER={server},{PORT};"
        f"DATABASE={DATABASE};"
        f"UID={USERNAME};"
        f"PWD={PASSWORD};"
        "Encrypt=no;"
        "TrustServerCertificate=yes;"
        f"Connection Timeout={CONNECTION_TIMEOUT};"
    )


def fetch_stock(server: str, driver: str) -> list[tuple[int, Decimal]]:
    """Return positive stock totals for the configured branch, ordered by item."""
    connection = pyodbc.connect(
        _connection_string(server, driver),
        autocommit=True,
        readonly=True,
    )
    with closing(connection):
        connection.timeout = QUERY_TIMEOUT
        cursor = connection.cursor()
        with closing(cursor):
            cursor.execute(STOCK_QUERY, BRANCH_ID)
            return [
                (int(row.itm_id), Decimal(row.stock_qty or ZERO))
                for row in cursor.fetchall()
            ]


def find_mismatches(
    branch_stock: list[tuple[int, Decimal]],
    main_stock: list[tuple[int, Decimal]],
):
    """Join both result sets by item, treating a missing side as zero stock."""
    combined = [
        (item_id, "branch", quantity) for item_id, quantity in branch_stock
    ]
    combined.extend(
        (item_id, "main", quantity) for item_id, quantity in main_stock
    )
    combined.sort(key=itemgetter(0))

    for item_id, rows in groupby(combined, key=itemgetter(0)):
        quantities = {"branch": ZERO, "main": ZERO}
        for _, source, quantity in rows:
            quantities[source] = quantity

        branch_quantity = quantities["branch"]
        main_quantity = quantities["main"]
        if branch_quantity != main_quantity:
            yield (
                item_id,
                branch_quantity,
                main_quantity,
                branch_quantity - main_quantity,
            )


def _format_quantity(quantity: Decimal) -> str:
    formatted = format(quantity, "f")
    return formatted.rstrip("0").rstrip(".") if "." in formatted else formatted


def write_mismatches(
    output_file: Path,
    branch_stock: list[tuple[int, Decimal]],
    main_stock: list[tuple[int, Decimal]],
) -> int:
    mismatch_count = 0
    with output_file.open("w", encoding="utf-8-sig", newline="") as csv_file:
        writer = csv.writer(csv_file, lineterminator="\n")
        writer.writerow(
            (
                "itm_id",
                "branch_stock_from_branch",
                "branch_stock_from_main",
                "diff",
            )
        )
        for mismatch in find_mismatches(branch_stock, main_stock):
            item_id, branch_quantity, main_quantity, difference = mismatch
            writer.writerow(
                (
                    item_id,
                    _format_quantity(branch_quantity),
                    _format_quantity(main_quantity),
                    _format_quantity(difference),
                )
            )
            mismatch_count += 1
    return mismatch_count


def main() -> int:
    try:
        driver = _get_sql_server_driver()
        branch_stock = fetch_stock(BRANCH_SERVER, driver)
        main_stock = fetch_stock(MAIN_SERVER, driver)
        mismatch_count = write_mismatches(OUTPUT_FILE, branch_stock, main_stock)
    except (OSError, pyodbc.Error, RuntimeError, ValueError) as error:
        print(f"Stock comparison failed: {error}", file=sys.stderr)
        return 1

    print(f"Wrote {mismatch_count} mismatches to {OUTPUT_FILE.resolve()}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

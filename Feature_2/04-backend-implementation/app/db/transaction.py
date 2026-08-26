import sqlite3
from collections.abc import Iterator
from contextlib import contextmanager
from typing import Literal

TransactionMode = Literal["DEFERRED", "IMMEDIATE", "EXCLUSIVE"]


@contextmanager
def transaction(
    connection: sqlite3.Connection,
    mode: TransactionMode = "IMMEDIATE",
) -> Iterator[sqlite3.Connection]:

    if connection.in_transaction:
        raise RuntimeError("Nested transactions are not supported")

    connection.execute(f"BEGIN {mode}")
    try:
        yield connection
    except BaseException:
        connection.rollback()
        raise
    else:
        connection.commit()

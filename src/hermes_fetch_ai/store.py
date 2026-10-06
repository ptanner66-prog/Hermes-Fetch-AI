"""The seller's durable state: used payments, paid credits, and owner controls.

One SQLite file in a directory only the owner can read. Unlike the in-memory
replay cache, it survives restarts, so a payment can never be used twice.
Every method runs on the event loop's thread and never awaits inside a
transaction; a check and its write happen in one ``BEGIN IMMEDIATE``.
"""

from __future__ import annotations

import contextlib
import os
import sqlite3
from collections.abc import Iterator
from dataclasses import dataclass
from pathlib import Path

SCHEMA_VERSION = 1
_SCHEMA = """
CREATE TABLE credits (
    reference TEXT PRIMARY KEY,
    kind TEXT NOT NULL,
    sender TEXT NOT NULL,
    subject TEXT NOT NULL,
    digest TEXT NOT NULL,
    amount_base TEXT NOT NULL,
    tx_hash TEXT NOT NULL UNIQUE,
    payer TEXT NOT NULL,
    status TEXT NOT NULL,
    attempts INTEGER NOT NULL DEFAULT 0,
    quoted_ms INTEGER NOT NULL,
    paid_ms INTEGER NOT NULL,
    updated_ms INTEGER NOT NULL
);
CREATE INDEX credits_by_status ON credits (status);
CREATE TABLE used_transactions (
    tx_hash TEXT PRIMARY KEY,
    reference TEXT NOT NULL,
    disposition TEXT NOT NULL,
    amount_base TEXT NOT NULL,
    payer TEXT NOT NULL,
    block_time_ms INTEGER,
    height INTEGER NOT NULL,
    recorded_ms INTEGER NOT NULL
);
CREATE TABLE runs (
    id INTEGER PRIMARY KEY,
    subject TEXT NOT NULL,
    sender TEXT NOT NULL,
    started_ms INTEGER NOT NULL
);
CREATE INDEX runs_by_subject ON runs (subject, started_ms);
CREATE TABLE banned (
    sender TEXT PRIMARY KEY,
    reason TEXT NOT NULL,
    banned_ms INTEGER NOT NULL
);
CREATE TABLE settings (
    key TEXT PRIMARY KEY,
    value TEXT NOT NULL
);
"""
# Credit states: paid -> running -> done; running -> paid (retry) -> failed;
# paid -> lapsed (redeem window passed); done/failed -> refunded (owner).
CREDIT_STATES = ("paid", "running", "done", "failed", "lapsed", "refunded")


def credit_problem(status: str) -> str:
    """Why a credit with ``status`` cannot be used, in the buyer's words."""
    return {
        "running": "this paid request is already running",
        "done": "this payment was already used for a completed request",
        "failed": "this request failed too many times; ask the seller for a refund",
        "lapsed": "this payment was not used within its redeem window",
        "refunded": "this payment was refunded",
    }.get(status, f"payment is {status}")


class PaymentAlreadyUsed(Exception):
    """This transaction already paid for something."""


class QuoteAlreadyPaid(Exception):
    """Another transaction already paid this quote; the new one is kept for a refund."""


class CreditUnavailable(Exception):
    """The credit exists but cannot be used now."""

    def __init__(self, reason: str) -> None:
        super().__init__(reason)
        self.reason = reason


@dataclass(frozen=True)
class Credit:
    reference: str
    kind: str
    sender: str
    subject: str
    digest: str
    amount_base: int
    tx_hash: str
    payer: str
    status: str
    attempts: int
    quoted_ms: int
    paid_ms: int
    updated_ms: int


@dataclass(frozen=True)
class UsedTransaction:
    tx_hash: str
    reference: str
    disposition: str
    amount_base: int
    payer: str
    block_time_ms: int | None
    height: int
    recorded_ms: int


def _credit(row: sqlite3.Row) -> Credit:
    return Credit(
        reference=row["reference"],
        kind=row["kind"],
        sender=row["sender"],
        subject=row["subject"],
        digest=row["digest"],
        amount_base=int(row["amount_base"]),
        tx_hash=row["tx_hash"],
        payer=row["payer"],
        status=row["status"],
        attempts=row["attempts"],
        quoted_ms=row["quoted_ms"],
        paid_ms=row["paid_ms"],
        updated_ms=row["updated_ms"],
    )


def _used_transaction(row: sqlite3.Row) -> UsedTransaction:
    return UsedTransaction(
        tx_hash=row["tx_hash"],
        reference=row["reference"],
        disposition=row["disposition"],
        amount_base=int(row["amount_base"]),
        payer=row["payer"],
        block_time_ms=row["block_time_ms"],
        height=row["height"],
        recorded_ms=row["recorded_ms"],
    )


class Store:
    def __init__(self, conn: sqlite3.Connection, path: Path) -> None:
        self._conn = conn
        self.path = path

    @classmethod
    def open(cls, path: Path) -> Store:
        """Open (or create) the store at ``path`` and recover interrupted runs."""
        path.parent.mkdir(parents=True, exist_ok=True)
        if os.name != "nt":
            # The database and its WAL files take their permissions from the
            # directory's protection, not the file mode.
            path.parent.chmod(0o700)
        conn = sqlite3.connect(path, isolation_level=None, check_same_thread=False)
        conn.row_factory = sqlite3.Row
        conn.execute("PRAGMA journal_mode=WAL")
        conn.execute("PRAGMA busy_timeout=5000")
        store = cls(conn, path)
        store._migrate()
        store.recover()
        return store

    def close(self) -> None:
        self._conn.close()

    def backup(self, destination: Path) -> None:
        """Copy the database to a new file, consistently, while the bridge may be running."""
        if destination.exists():
            raise FileExistsError(f"{destination} already exists; choose a new file name")
        target = sqlite3.connect(destination)
        try:
            self._conn.backup(target)
        finally:
            target.close()
        if os.name != "nt":
            destination.chmod(0o600)

    @contextlib.contextmanager
    def _transaction(self) -> Iterator[sqlite3.Connection]:
        self._conn.execute("BEGIN IMMEDIATE")
        try:
            yield self._conn
        except BaseException:
            self._conn.execute("ROLLBACK")
            raise
        self._conn.execute("COMMIT")

    def _migrate(self) -> None:
        version = self._conn.execute("PRAGMA user_version").fetchone()[0]
        if version == SCHEMA_VERSION:
            return
        if version != 0:
            raise RuntimeError(
                f"{self.path} was written by a newer hermes-fetch-ai (schema {version}); "
                "upgrade hermes-fetch-ai"
            )
        # executescript() would commit first, so run the statements one by one
        # inside a single transaction.
        with self._transaction() as conn:
            for statement in _SCHEMA.split(";"):
                if statement.strip():
                    conn.execute(statement)
            conn.execute(f"PRAGMA user_version = {SCHEMA_VERSION}")

    # -- payments -------------------------------------------------------

    def tx_used(self, tx_hash: str) -> bool:
        row = self._conn.execute(
            "SELECT 1 FROM used_transactions WHERE tx_hash = ?", (tx_hash,)
        ).fetchone()
        return row is not None

    def credit(self, reference: str) -> Credit | None:
        row = self._conn.execute(
            "SELECT * FROM credits WHERE reference = ?", (reference,)
        ).fetchone()
        return _credit(row) if row else None

    def record_payment(
        self,
        *,
        reference: str,
        kind: str,
        sender: str,
        subject: str,
        digest: str,
        amount_base: int,
        tx_hash: str,
        payer: str,
        block_time_ms: int | None,
        height: int,
        quoted_ms: int,
        now_ms: int,
    ) -> Credit:
        """Record ``tx_hash`` as the payment for ``reference`` and return the new credit."""
        with self._transaction() as conn:
            if conn.execute(
                "SELECT 1 FROM used_transactions WHERE tx_hash = ?", (tx_hash,)
            ).fetchone():
                raise PaymentAlreadyUsed(tx_hash)
            already_paid = conn.execute(
                "SELECT 1 FROM credits WHERE reference = ?", (reference,)
            ).fetchone()
            conn.execute(
                "INSERT INTO used_transactions VALUES (?, ?, ?, ?, ?, ?, ?, ?)",
                (
                    tx_hash,
                    reference,
                    "duplicate" if already_paid else "applied",
                    str(amount_base),
                    payer,
                    block_time_ms,
                    height,
                    now_ms,
                ),
            )
            if not already_paid:
                conn.execute(
                    "INSERT INTO credits (reference, kind, sender, subject, digest, amount_base,"
                    " tx_hash, payer, status, attempts, quoted_ms, paid_ms, updated_ms)"
                    " VALUES (?, ?, ?, ?, ?, ?, ?, ?, 'paid', 0, ?, ?, ?)",
                    (
                        reference,
                        kind,
                        sender,
                        subject,
                        digest,
                        str(amount_base),
                        tx_hash,
                        payer,
                        quoted_ms,
                        now_ms,
                        now_ms,
                    ),
                )
        if already_paid:
            raise QuoteAlreadyPaid(reference)
        credit = self.credit(reference)
        assert credit is not None
        return credit

    def begin_run(self, reference: str, *, max_attempts: int, now_ms: int) -> Credit:
        """Move a paid credit to running, or raise CreditUnavailable."""
        exhausted = False
        with self._transaction() as conn:
            row = conn.execute("SELECT * FROM credits WHERE reference = ?", (reference,)).fetchone()
            if row is None:
                raise CreditUnavailable("no payment is recorded for this quote")
            status, attempts = row["status"], row["attempts"]
            if status != "paid":
                raise CreditUnavailable(credit_problem(status))
            if attempts >= max_attempts:
                # Commit the failure before raising: raising inside the
                # transaction would roll it back.
                conn.execute(
                    "UPDATE credits SET status = 'failed', updated_ms = ? WHERE reference = ?",
                    (now_ms, reference),
                )
                exhausted = True
            else:
                conn.execute(
                    "UPDATE credits SET status = 'running', attempts = attempts + 1,"
                    " updated_ms = ? WHERE reference = ?",
                    (now_ms, reference),
                )
        if exhausted:
            raise CreditUnavailable(credit_problem("failed"))
        credit = self.credit(reference)
        assert credit is not None
        return credit

    def finish_run(self, reference: str, *, ok: bool, max_attempts: int, now_ms: int) -> Credit:
        """Close a run: done on success; otherwise paid again (retry) or failed."""
        with self._transaction() as conn:
            row = conn.execute(
                "SELECT status, attempts FROM credits WHERE reference = ?", (reference,)
            ).fetchone()
            if row is None or row["status"] != "running":
                raise CreditUnavailable("this request is not running")
            if ok:
                status = "done"
            else:
                status = "failed" if row["attempts"] >= max_attempts else "paid"
            conn.execute(
                "UPDATE credits SET status = ?, updated_ms = ? WHERE reference = ?",
                (status, now_ms, reference),
            )
        credit = self.credit(reference)
        assert credit is not None
        return credit

    def recover(self) -> int:
        """After a crash, let interrupted runs be retried; returns how many."""
        with self._transaction() as conn:
            cursor = conn.execute("UPDATE credits SET status = 'paid' WHERE status = 'running'")
        return cursor.rowcount

    def lapse(self, *, older_than_ms: int, now_ms: int) -> int:
        """Mark paid credits that were never used before ``older_than_ms`` as lapsed."""
        with self._transaction() as conn:
            cursor = conn.execute(
                "UPDATE credits SET status = 'lapsed', updated_ms = ?"
                " WHERE status = 'paid' AND paid_ms < ?",
                (now_ms, older_than_ms),
            )
        return cursor.rowcount

    def mark_refunded(self, reference: str, *, now_ms: int) -> Credit:
        with self._transaction() as conn:
            cursor = conn.execute(
                "UPDATE credits SET status = 'refunded', updated_ms = ?"
                " WHERE reference = ? AND status IN ('done', 'failed', 'lapsed', 'paid')",
                (now_ms, reference),
            )
            if cursor.rowcount != 1:
                raise CreditUnavailable("this payment cannot be marked refunded")
        credit = self.credit(reference)
        assert credit is not None
        return credit

    def credits(self, status: str | None = None, limit: int = 100) -> list[Credit]:
        if status is None:
            rows = self._conn.execute(
                "SELECT * FROM credits ORDER BY paid_ms DESC LIMIT ?", (limit,)
            ).fetchall()
        else:
            rows = self._conn.execute(
                "SELECT * FROM credits WHERE status = ? ORDER BY paid_ms DESC LIMIT ?",
                (status, limit),
            ).fetchall()
        return [_credit(row) for row in rows]

    def used_transaction(self, tx_hash: str) -> UsedTransaction | None:
        row = self._conn.execute(
            "SELECT * FROM used_transactions WHERE tx_hash = ?", (tx_hash,)
        ).fetchone()
        return _used_transaction(row) if row else None

    def extra_payments(self, limit: int = 100) -> list[UsedTransaction]:
        """Second payments for an already paid quote, newest first; each needs a refund."""
        rows = self._conn.execute(
            "SELECT * FROM used_transactions WHERE disposition = 'duplicate'"
            " ORDER BY recorded_ms DESC LIMIT ?",
            (limit,),
        ).fetchall()
        return [_used_transaction(row) for row in rows]

    # -- service runs -----------------------------------------------------

    def record_run(self, *, subject: str, sender: str, now_ms: int) -> None:
        with self._transaction() as conn:
            conn.execute(
                "INSERT INTO runs (subject, sender, started_ms) VALUES (?, ?, ?)",
                (subject, sender, now_ms),
            )
            # Keep a week of history; the daily cap only needs one day.
            conn.execute("DELETE FROM runs WHERE started_ms < ?", (now_ms - 7 * 86_400_000,))

    def runs_since(self, subject: str, since_ms: int) -> int:
        row = self._conn.execute(
            "SELECT COUNT(*) FROM runs WHERE subject = ? AND started_ms >= ?", (subject, since_ms)
        ).fetchone()
        return int(row[0])

    # -- owner controls -----------------------------------------------------

    def paused(self) -> bool:
        row = self._conn.execute("SELECT value FROM settings WHERE key = 'paused'").fetchone()
        return bool(row and row["value"] == "1")

    def set_paused(self, paused: bool) -> None:
        with self._transaction() as conn:
            conn.execute(
                "INSERT INTO settings (key, value) VALUES ('paused', ?)"
                " ON CONFLICT (key) DO UPDATE SET value = excluded.value",
                ("1" if paused else "0",),
            )

    def ban(self, sender: str, *, reason: str, now_ms: int) -> None:
        with self._transaction() as conn:
            conn.execute(
                "INSERT INTO banned (sender, reason, banned_ms) VALUES (?, ?, ?)"
                " ON CONFLICT (sender) DO UPDATE SET reason = excluded.reason",
                (sender, reason, now_ms),
            )

    def unban(self, sender: str) -> bool:
        with self._transaction() as conn:
            cursor = conn.execute("DELETE FROM banned WHERE sender = ?", (sender,))
        return cursor.rowcount == 1

    def is_banned(self, sender: str) -> bool:
        row = self._conn.execute("SELECT 1 FROM banned WHERE sender = ?", (sender,)).fetchone()
        return row is not None

    def banned(self) -> list[tuple[str, str]]:
        rows = self._conn.execute("SELECT sender, reason FROM banned ORDER BY banned_ms").fetchall()
        return [(row["sender"], row["reason"]) for row in rows]

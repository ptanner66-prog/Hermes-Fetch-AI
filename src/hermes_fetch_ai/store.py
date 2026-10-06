"""The bridge's durable state: what it sold, what it bought, and owner controls.

Selling: used payments, paid credits, service runs, bans, and pausing.
Buying: conversations with other agents, their replies, and purchases.

One SQLite file in a directory only the owner can read. Unlike the in-memory
replay cache, it survives restarts, so a payment can never be used twice.
Every method runs on the event loop's thread and never awaits inside a
transaction; a check and its write happen in one ``BEGIN IMMEDIATE``.
"""

from __future__ import annotations

import contextlib
import hmac
import os
import sqlite3
from collections.abc import Iterator, Sequence
from dataclasses import dataclass
from pathlib import Path

SCHEMA_VERSION = 2
_SCHEMA_V1 = """
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
_SCHEMA_V2 = """
CREATE TABLE conversations (
    peer TEXT NOT NULL,
    session TEXT NOT NULL,
    started_ms INTEGER NOT NULL,
    last_ms INTEGER NOT NULL,
    PRIMARY KEY (peer, session)
);
CREATE TABLE inbox (
    id INTEGER PRIMARY KEY,
    peer TEXT NOT NULL,
    session TEXT NOT NULL,
    kind TEXT NOT NULL,
    body TEXT NOT NULL,
    received_ms INTEGER NOT NULL
);
CREATE INDEX inbox_by_conversation ON inbox (peer, session, id);
CREATE TABLE purchases (
    id TEXT PRIMARY KEY,
    peer TEXT NOT NULL,
    session TEXT NOT NULL,
    reference TEXT,
    recipient TEXT NOT NULL,
    amount_base TEXT NOT NULL,
    description TEXT NOT NULL,
    deadline_ms INTEGER NOT NULL,
    status TEXT NOT NULL,
    nonce TEXT,
    tx_hash TEXT UNIQUE,
    quoted_ms INTEGER NOT NULL,
    spent_ms INTEGER,
    updated_ms INTEGER NOT NULL,
    note TEXT NOT NULL DEFAULT ''
);
CREATE INDEX purchases_by_status ON purchases (status, spent_ms);
"""
# Statement batches that upgrade the schema: the first creates version 1 from
# nothing, the second upgrades version 1 to 2.
_MIGRATIONS = (_SCHEMA_V1, _SCHEMA_V2)
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


_DAY_MS = 86_400_000
# Purchase states: quoted -> declined | expired | broadcasting;
# broadcasting -> paid | failed (nothing left the wallet) | needs_review
# (unknown: never retried on its own); paid -> committed -> completed | cancelled.
PURCHASE_STATES = (
    "quoted",
    "declined",
    "expired",
    "broadcasting",
    "paid",
    "failed",
    "needs_review",
    "committed",
    "completed",
    "cancelled",
)
# FET may have left the wallet in these states, so they count against the limits.
SPENDING_STATES = ("broadcasting", "paid", "needs_review", "committed", "completed", "cancelled")
# Replies kept for Hermes to read, across all conversations; older ones are dropped.
MAX_INBOX = 500


class PurchaseRefused(Exception):
    """A purchase cannot move on; ``reason`` says why, for the owner."""

    def __init__(self, reason: str) -> None:
        super().__init__(reason)
        self.reason = reason


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


@dataclass(frozen=True)
class Purchase:
    id: str
    peer: str
    session: str
    reference: str | None
    recipient: str
    amount_base: int
    description: str
    deadline_ms: int
    status: str
    nonce: str | None
    tx_hash: str | None
    quoted_ms: int
    spent_ms: int | None
    updated_ms: int
    note: str


@dataclass(frozen=True)
class InboxEntry:
    id: int
    peer: str
    session: str
    kind: str
    body: str
    received_ms: int


def _purchase(row: sqlite3.Row) -> Purchase:
    return Purchase(
        id=row["id"],
        peer=row["peer"],
        session=row["session"],
        reference=row["reference"],
        recipient=row["recipient"],
        amount_base=int(row["amount_base"]),
        description=row["description"],
        deadline_ms=row["deadline_ms"],
        status=row["status"],
        nonce=row["nonce"],
        tx_hash=row["tx_hash"],
        quoted_ms=row["quoted_ms"],
        spent_ms=row["spent_ms"],
        updated_ms=row["updated_ms"],
        note=row["note"],
    )


def _inbox_entry(row: sqlite3.Row) -> InboxEntry:
    return InboxEntry(
        id=row["id"],
        peer=row["peer"],
        session=row["session"],
        kind=row["kind"],
        body=row["body"],
        received_ms=row["received_ms"],
    )


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
        """Open (or create) the store at ``path``.

        Owner commands open it while the bridge runs, so this never touches
        runs in progress; ``serve`` calls ``recover`` when it starts.
        """
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
        if version > SCHEMA_VERSION:
            raise RuntimeError(
                f"{self.path} was written by a newer hermes-fetch-ai (schema {version}); "
                "upgrade hermes-fetch-ai"
            )
        # executescript() would commit first, so run the statements one by one
        # inside a single transaction.
        with self._transaction() as conn:
            for batch in _MIGRATIONS[version:]:
                for statement in batch.split(";"):
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
        """When the bridge starts: runs the last one left unfinished may be retried.

        Only the one bridge running with these records may call this (``serve``
        does, once it holds the records folder), never an owner command: it
        would make a run in progress look interrupted.
        """
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

    def unused_credit(self, *, sender: str, subject: str, digest: str) -> Credit | None:
        """The oldest paid, not yet used credit for this buyer and request, if any."""
        row = self._conn.execute(
            "SELECT * FROM credits WHERE sender = ? AND subject = ? AND digest = ?"
            " AND status = 'paid' ORDER BY paid_ms LIMIT 1",
            (sender, subject, digest),
        ).fetchone()
        return _credit(row) if row else None

    def earned_since(self, since_ms: int) -> tuple[int, int]:
        """Paid requests since ``since_ms``, and what they paid (refunds left out)."""
        row = self._conn.execute(
            "SELECT COUNT(*), COALESCE(SUM(CAST(amount_base AS INTEGER)), 0) FROM credits"
            " WHERE paid_ms >= ? AND status != 'refunded'",
            (since_ms,),
        ).fetchone()
        return int(row[0]), int(row[1])

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

    # -- buying -------------------------------------------------------------

    def open_conversation(self, peer: str, session: str, *, now_ms: int) -> None:
        with self._transaction() as conn:
            conn.execute(
                "INSERT INTO conversations (peer, session, started_ms, last_ms) VALUES (?, ?, ?, ?)"
                " ON CONFLICT (peer, session) DO UPDATE SET last_ms = excluded.last_ms",
                (peer, session, now_ms, now_ms),
            )

    def has_conversation(self, peer: str, session: str | None = None) -> bool:
        """True if this bridge started a conversation with ``peer`` (in ``session``)."""
        if session is None:
            row = self._conn.execute(
                "SELECT 1 FROM conversations WHERE peer = ?", (peer,)
            ).fetchone()
        else:
            row = self._conn.execute(
                "SELECT 1 FROM conversations WHERE peer = ? AND session = ?", (peer, session)
            ).fetchone()
        return row is not None

    def add_message(self, *, peer: str, session: str, kind: str, body: str, now_ms: int) -> int:
        """Keep a message from another agent for Hermes to read; returns its id."""
        with self._transaction() as conn:
            cursor = conn.execute(
                "INSERT INTO inbox (peer, session, kind, body, received_ms) VALUES (?, ?, ?, ?, ?)",
                (peer, session, kind, body, now_ms),
            )
            conn.execute(
                "DELETE FROM inbox WHERE id <= (SELECT MAX(id) FROM inbox) - ?", (MAX_INBOX,)
            )
            conn.execute(
                "UPDATE conversations SET last_ms = ? WHERE peer = ? AND session = ?",
                (now_ms, peer, session),
            )
        message_id = cursor.lastrowid
        assert message_id is not None
        return message_id

    def inbox(
        self,
        *,
        peer: str | None = None,
        session: str | None = None,
        after_id: int = 0,
        limit: int = 50,
    ) -> list[InboxEntry]:
        """Messages from other agents, oldest first."""
        query = "SELECT * FROM inbox WHERE id > ?"
        params: list[object] = [after_id]
        if peer is not None:
            query += " AND peer = ?"
            params.append(peer)
        if session is not None:
            query += " AND session = ?"
            params.append(session)
        query += " ORDER BY id LIMIT ?"
        params.append(limit)
        return [_inbox_entry(row) for row in self._conn.execute(query, params).fetchall()]

    def last_message_id(self) -> int:
        row = self._conn.execute("SELECT COALESCE(MAX(id), 0) FROM inbox").fetchone()
        return int(row[0])

    def add_quote(
        self,
        *,
        purchase_id: str,
        peer: str,
        session: str,
        reference: str | None,
        recipient: str,
        amount_base: int,
        description: str,
        deadline_ms: int,
        now_ms: int,
    ) -> Purchase:
        """Record a seller's payment request; nothing is paid until the owner approves."""
        with self._transaction() as conn:
            conn.execute(
                "INSERT INTO purchases (id, peer, session, reference, recipient, amount_base,"
                " description, deadline_ms, status, quoted_ms, updated_ms)"
                " VALUES (?, ?, ?, ?, ?, ?, ?, ?, 'quoted', ?, ?)",
                (
                    purchase_id,
                    peer,
                    session,
                    reference,
                    recipient,
                    str(amount_base),
                    description,
                    deadline_ms,
                    now_ms,
                    now_ms,
                ),
            )
        purchase = self.purchase(purchase_id)
        assert purchase is not None
        return purchase

    def purchase(self, purchase_id: str) -> Purchase | None:
        row = self._conn.execute("SELECT * FROM purchases WHERE id = ?", (purchase_id,)).fetchone()
        return _purchase(row) if row else None

    def purchase_by_tx(self, tx_hash: str) -> Purchase | None:
        row = self._conn.execute("SELECT * FROM purchases WHERE tx_hash = ?", (tx_hash,)).fetchone()
        return _purchase(row) if row else None

    def purchases(self, status: str | None = None, limit: int = 50) -> list[Purchase]:
        """Purchases, newest first."""
        if status is None:
            rows = self._conn.execute(
                "SELECT * FROM purchases ORDER BY quoted_ms DESC, id LIMIT ?", (limit,)
            ).fetchall()
        else:
            rows = self._conn.execute(
                "SELECT * FROM purchases WHERE status = ? ORDER BY quoted_ms DESC, id LIMIT ?",
                (status, limit),
            ).fetchall()
        return [_purchase(row) for row in rows]

    def open_quotes(self, peer: str, session: str) -> list[Purchase]:
        """Quotes from ``peer`` in ``session`` still waiting for the owner, newest first."""
        rows = self._conn.execute(
            "SELECT * FROM purchases WHERE peer = ? AND session = ? AND status = 'quoted'"
            " ORDER BY quoted_ms DESC, id",
            (peer, session),
        ).fetchall()
        return [_purchase(row) for row in rows]

    def spent_since(self, since_ms: int, peer: str | None = None) -> int:
        """atestfet that may have left the buying wallet since ``since_ms``."""
        placeholders = ", ".join("?" for _ in SPENDING_STATES)
        query = (
            f"SELECT amount_base FROM purchases WHERE status IN ({placeholders}) AND spent_ms >= ?"
        )
        params: list[object] = [*SPENDING_STATES, since_ms]
        if peer is not None:
            query += " AND peer = ?"
            params.append(peer)
        return sum(int(row[0]) for row in self._conn.execute(query, params).fetchall())

    def issue_nonce(self, purchase_id: str, nonce: str, *, now_ms: int) -> Purchase:
        """Attach a one-time code to a quote the owner is about to see."""
        with self._transaction() as conn:
            cursor = conn.execute(
                "UPDATE purchases SET nonce = ?, updated_ms = ? WHERE id = ? AND status = 'quoted'",
                (nonce, now_ms, purchase_id),
            )
            if cursor.rowcount != 1:
                raise PurchaseRefused(self._why_not_quoted(conn, purchase_id))
        purchase = self.purchase(purchase_id)
        assert purchase is not None
        return purchase

    @staticmethod
    def _why_not_quoted(conn: sqlite3.Connection, purchase_id: str) -> str:
        row = conn.execute("SELECT status FROM purchases WHERE id = ?", (purchase_id,)).fetchone()
        if row is None:
            return f"no payment request {purchase_id}"
        return f"payment request {purchase_id} is {row['status']}, not waiting for approval"

    def start_payment(
        self,
        purchase_id: str,
        *,
        nonce: str,
        expect_amount_base: int,
        expect_recipient: str,
        max_payment_base: int,
        max_per_day_base: int,
        max_per_seller_base: int,
        allowed_sellers: Sequence[str],
        now_ms: int,
    ) -> Purchase:
        """Check an approved payment against the quote and the limits, then mark it sending.

        Everything is decided in one transaction, so two payments racing each
        other cannot both slip under a limit.
        """
        expired = False
        with self._transaction() as conn:
            row = conn.execute("SELECT * FROM purchases WHERE id = ?", (purchase_id,)).fetchone()
            if row is None or row["status"] != "quoted":
                raise PurchaseRefused(self._why_not_quoted(conn, purchase_id))
            purchase = _purchase(row)
            if not purchase.nonce or not hmac.compare_digest(purchase.nonce, nonce):
                raise PurchaseRefused("this approval does not match the payment request shown")
            if purchase.amount_base != expect_amount_base:
                raise PurchaseRefused("the amount differs from the one approved")
            if purchase.recipient != expect_recipient:
                raise PurchaseRefused("the recipient differs from the one approved")
            if now_ms > purchase.deadline_ms:
                conn.execute(
                    "UPDATE purchases SET status = 'expired', nonce = NULL, updated_ms = ?"
                    " WHERE id = ?",
                    (now_ms, purchase_id),
                )
                expired = True
            else:
                problem = self._over_limit(
                    conn,
                    purchase,
                    max_payment_base=max_payment_base,
                    max_per_day_base=max_per_day_base,
                    max_per_seller_base=max_per_seller_base,
                    allowed_sellers=allowed_sellers,
                    now_ms=now_ms,
                )
                if problem:
                    raise PurchaseRefused(problem)
                conn.execute(
                    "UPDATE purchases SET status = 'broadcasting', nonce = NULL, spent_ms = ?,"
                    " updated_ms = ? WHERE id = ?",
                    (now_ms, now_ms, purchase_id),
                )
        if expired:
            raise PurchaseRefused("this payment request has expired; ask the seller again")
        started = self.purchase(purchase_id)
        assert started is not None
        return started

    @staticmethod
    def _over_limit(
        conn: sqlite3.Connection,
        purchase: Purchase,
        *,
        max_payment_base: int,
        max_per_day_base: int,
        max_per_seller_base: int,
        allowed_sellers: Sequence[str],
        now_ms: int,
    ) -> str | None:
        if allowed_sellers and purchase.peer not in allowed_sellers:
            return "this seller is not on the list of agents Hermes may pay"
        if purchase.amount_base > max_payment_base:
            return "the amount is more than the limit for one payment"
        placeholders = ", ".join("?" for _ in SPENDING_STATES)
        rows = conn.execute(
            f"SELECT peer, amount_base FROM purchases WHERE status IN ({placeholders})"
            " AND spent_ms >= ?",
            (*SPENDING_STATES, now_ms - _DAY_MS),
        ).fetchall()
        spent = sum(int(row["amount_base"]) for row in rows)
        if spent + purchase.amount_base > max_per_day_base:
            return "this payment would go over the daily limit"
        to_seller = sum(int(row["amount_base"]) for row in rows if row["peer"] == purchase.peer)
        if to_seller + purchase.amount_base > max_per_seller_base:
            return "this payment would go over the daily limit for this seller"
        return None

    def set_purchase_tx(self, purchase_id: str, tx_hash: str, *, now_ms: int) -> None:
        """Record the transaction hash before it is broadcast, so its fate can be looked up."""
        with self._transaction() as conn:
            cursor = conn.execute(
                "UPDATE purchases SET tx_hash = ?, updated_ms = ?"
                " WHERE id = ? AND status = 'broadcasting'",
                (tx_hash, now_ms, purchase_id),
            )
            if cursor.rowcount != 1:
                raise PurchaseRefused(f"payment {purchase_id} is not being sent")

    def move_purchase(
        self,
        purchase_id: str,
        *,
        from_states: Sequence[str],
        to: str,
        now_ms: int,
        note: str | None = None,
    ) -> Purchase:
        """Move a purchase from one of ``from_states`` to ``to``, or raise PurchaseRefused."""
        assert to in PURCHASE_STATES
        placeholders = ", ".join("?" for _ in from_states)
        with self._transaction() as conn:
            cursor = conn.execute(
                f"UPDATE purchases SET status = ?, nonce = NULL, updated_ms = ?,"
                f" note = COALESCE(?, note) WHERE id = ? AND status IN ({placeholders})",
                (to, now_ms, note, purchase_id, *from_states),
            )
            if cursor.rowcount != 1:
                row = conn.execute(
                    "SELECT status FROM purchases WHERE id = ?", (purchase_id,)
                ).fetchone()
                state = row["status"] if row else "unknown"
                raise PurchaseRefused(f"payment {purchase_id} is {state}")
        moved = self.purchase(purchase_id)
        assert moved is not None
        return moved

"""SQLite checkpoints, observations and idempotency results share one transaction."""

import contextlib
import hashlib
import json
import secrets
import sqlite3
from pathlib import Path

from xeno import MODEL_VERSION
from xeno.service.engine import DomainError, apply_action, new_state, observation, opaque
from xeno.service.schemas import ActionRequest, EpisodeConfig


def digest(value: str) -> str:
    return hashlib.sha256(value.encode()).hexdigest()


def encode(value) -> str:
    return json.dumps(value, sort_keys=True, separators=(",", ":"), allow_nan=False)


class Store:
    def __init__(self, path: str | Path):
        self.path = Path(path)
        self.path.parent.mkdir(parents=True, exist_ok=True)
        with self.connect() as db:
            db.executescript("""
                PRAGMA journal_mode=WAL;
                CREATE TABLE IF NOT EXISTS episodes (
                    id TEXT PRIMARY KEY, token_hash TEXT NOT NULL, state TEXT NOT NULL);
                CREATE TABLE IF NOT EXISTS events (
                    episode_id TEXT NOT NULL, sequence INTEGER NOT NULL,
                    request TEXT, observation TEXT NOT NULL,
                    PRIMARY KEY (episode_id, sequence));
                CREATE TABLE IF NOT EXISTS results (
                    episode_id TEXT NOT NULL, action_id TEXT NOT NULL,
                    request_hash TEXT NOT NULL, result TEXT NOT NULL,
                    PRIMARY KEY (episode_id, action_id));
            """)

    @contextlib.contextmanager
    def connect(self):
        db = sqlite3.connect(self.path, timeout=30)
        try:
            yield db
            db.commit()
        except BaseException:
            db.rollback()
            raise
        finally:
            db.close()

    def create(self, config: EpisodeConfig) -> dict:
        episode_id, token = opaque("episode"), secrets.token_urlsafe(32)
        state = new_state(config, episode_id)
        public = observation(state)
        with self.connect() as db:
            db.execute(
                "INSERT INTO episodes VALUES (?, ?, ?)", (episode_id, digest(token), encode(state))
            )
            db.execute("INSERT INTO events VALUES (?, 0, NULL, ?)", (episode_id, encode(public)))
        return {"episode_id": episode_id, "investigator_token": token, "observation": public}

    def state(self, episode_id: str, db=None) -> dict:
        if db is None:
            with self.connect() as connection:
                return self.state(episode_id, connection)
        row = db.execute("SELECT state FROM episodes WHERE id=?", (episode_id,)).fetchone()
        if row is None:
            raise DomainError("not_found", "Episode not found", 404)
        state = json.loads(row[0])
        if state["model_version"] != MODEL_VERSION:
            raise DomainError("model_mismatch", "Checkpoint uses an unsupported model version")
        return state

    def authorized(self, episode_id: str, token: str) -> bool:
        with self.connect() as db:
            row = db.execute("SELECT token_hash FROM episodes WHERE id=?", (episode_id,)).fetchone()
        return row is not None and secrets.compare_digest(row[0], digest(token))

    def action(self, episode_id: str, request: ActionRequest) -> dict:
        if request.episode_id != episode_id:
            raise DomainError("episode_mismatch", "Body and route episode identifiers differ", 422)
        payload = encode(request.model_dump())
        fingerprint = digest(payload)
        with self.connect() as db:
            db.execute("BEGIN IMMEDIATE")
            previous = db.execute(
                "SELECT request_hash, result FROM results WHERE episode_id=? AND action_id=?",
                (episode_id, request.action_id),
            ).fetchone()
            if previous:
                if previous[0] != fingerprint:
                    raise DomainError(
                        "idempotency_conflict", "Action ID was used for a different request"
                    )
                return json.loads(previous[1])
            state, result = apply_action(self.state(episode_id, db), request)
            db.execute("UPDATE episodes SET state=? WHERE id=?", (encode(state), episode_id))
            db.execute(
                "INSERT INTO events VALUES (?, ?, ?, ?)",
                (episode_id, state["revision"], payload, encode(result["observation"])),
            )
            db.execute(
                "INSERT INTO results VALUES (?, ?, ?, ?)",
                (episode_id, request.action_id, fingerprint, encode(result)),
            )
            return result

    def result(self, episode_id: str, action_id: str) -> dict:
        with self.connect() as db:
            row = db.execute(
                "SELECT result FROM results WHERE episode_id=? AND action_id=?",
                (episode_id, action_id),
            ).fetchone()
        if row is None:
            raise DomainError("job_not_found", "No committed action with this identifier", 404)
        return json.loads(row[0])

    def events(self, episode_id: str, after: int = -1) -> list[dict]:
        with self.connect() as db:
            rows = db.execute(
                "SELECT observation FROM events "
                "WHERE episode_id=? AND sequence>? ORDER BY sequence",
                (episode_id, after),
            ).fetchall()
        return [json.loads(row[0]) for row in rows]

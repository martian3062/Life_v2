# Protocol 1.0

HTTP and WebSocket payloads carry `schema_version: "1.0"`. `/health` also returns package and
model versions. Local service state persists in SQLite and resumes on restart. The server
accepts one writer at a time through `BEGIN IMMEDIATE`; no GPU or rendering tick owns time.

## Authentication

Use `Authorization: Bearer <credential>` on every protected request and WebSocket handshake.
The admin credential creates episodes and accesses private evaluation/checkpoints. Episode
creation returns a new investigator credential scoped to that episode. Its hash is stored in
SQLite. Neither investigator credentials nor the admin credential grant each other's role.
The private database and checkpoint files belong to the trusted runner.

## Routes

| Method and path | Role | Purpose |
| --- | --- | --- |
| `GET /health` | Public | Version handshake |
| `POST /v1/admin/episodes` | Admin | Validated private episode setup |
| `GET /v1/episodes/{id}/observation` | Investigator | Latest public committed snapshot |
| `GET /v1/episodes/{id}/actions` | Investigator | Action specification, costs and current budget |
| `POST /v1/episodes/{id}/actions` | Investigator | Atomic action |
| `GET /v1/episodes/{id}/jobs/{action_id}` | Investigator | Original result after a timeout |
| `POST /v1/episodes/{id}/conclusion` | Investigator | Same transaction protocol, conclusion parameters |
| `GET /v1/episodes/{id}/events?after=0` | Investigator | Public events strictly after a sequence |
| `WS /v1/episodes/{id}/stream?after=0` | Investigator | Stream committed events |
| `GET /v1/admin/episodes/{id}/evaluation` | Admin | Scores after conclusion only |
| `GET /v1/admin/episodes/{id}/checkpoint` | Admin | Full privileged state |

OpenAPI field validation is available from `/docs`. Unknown request fields and unsupported
conditions are rejected. Action-specific parameter validation also rejects extra fields.
Instrument metadata and all numerical action costs are available from the action catalogue.

## Requests and retries

An action body contains `episode_id`, `action_id`, `expected_state_revision`, `action_type` and
`parameters`. Action IDs are 1–100 alphanumeric, underscore or hyphen characters. A completed
response contains `status: completed`, the action/job ID, and the new observation.

Exact repeats of the original body return the saved result, even after a restart, a later
action or mission closure. A different body using the same ID returns 409
`idempotency_conflict`. A new action with a stale revision returns 409 `stale_revision`.
Query the original job ID after a network timeout. Do not issue a new sample action ID until
the original request's status is known.

Validation, costs, transfers, solver updates, resulting checkpoint, event and idempotency result
commit together. Invalid requests roll back all state and cost changes. Numerical failure
returns 422 `numerically_invalid` with the same rollback. Asynchronous execution, cancellation
and simulated instrument failures are deferred; synchronous actions finish at a decision boundary.

## Stream and replay

Event sequences start at 0 and increment with committed revisions. Each stream message is
`{"type":"observation","observation":{...}}`. A client detects gaps and resynchronizes with
HTTP events or `{"type":"resync","after":N}` on the socket. A ping produces an `ack` carrying
the latest sequence. Reconnects may replay already-seen events; deduplicate by episode/sequence.

Read-only GETs never advance time or reroll measurements. A submitted conclusion freezes the
report. Only duplicate requests may then return prior results; new mutations are rejected.
An exported `observations.jsonl` is recorded-observation replay. It is not a fresh simulation
or proof of bit-identical Unreal physics across platforms.

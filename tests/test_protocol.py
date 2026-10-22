import json
from concurrent.futures import ThreadPoolExecutor

import pytest
from fastapi.testclient import TestClient

from xeno.investigator.policies import EpisodeClient, run_policy
from xeno.service.app import create_app

ADMIN = "test-admin-credential-long-enough-for-local-tests"


@pytest.fixture
def setup(tmp_path):
    app = create_app(tmp_path / "test.sqlite3", ADMIN)
    with TestClient(app) as transport:
        created = transport.post(
            "/v1/admin/episodes", json={}, headers={"Authorization": f"Bearer {ADMIN}"}
        ).json()
        client = EpisodeClient(transport, created["episode_id"], created["investigator_token"])
        yield app, transport, client


def request(client, kind="observe_site", **params):
    return {
        "episode_id": client.episode_id,
        "action_id": "repeat-test",
        "expected_state_revision": client.obs["state_revision"],
        "action_type": kind,
        "parameters": params or {"site_id": client.obs["sites"][0]["site_id"]},
    }


def test_roles_and_observation_allowlist(setup):
    _app, transport, client = setup
    assert transport.get(client.base + "/observation").status_code == 401
    assert (
        transport.get(
            f"/v1/admin/episodes/{client.episode_id}/checkpoint", headers=client.headers
        ).status_code
        == 403
    )
    assert transport.post("/v1/admin/episodes", json={}, headers=client.headers).status_code == 403
    public = json.dumps(client.obs)
    for forbidden in ("rate_scale", "family", "seed", "grid", "amounts", "target", "kinetics"):
        assert f'"{forbidden}"' not in public
    assert client.get("/observation") == client.get("/observation")


def test_episode_scoped_credentials(setup):
    _app, transport, client = setup
    other = transport.post(
        "/v1/admin/episodes", json={}, headers={"Authorization": f"Bearer {ADMIN}"}
    ).json()
    assert (
        transport.get(
            f"/v1/episodes/{other['episode_id']}/observation", headers=client.headers
        ).status_code
        == 403
    )


def test_duplicate_requests_are_atomic_and_survive_restart(setup):
    app, transport, client = setup
    body = request(
        client, "collect_sample", site_id=client.obs["sites"][0]["site_id"], volume_m3=2e-7
    )
    with ThreadPoolExecutor(max_workers=2) as pool:
        results = list(
            pool.map(
                lambda _: transport.post(
                    client.base + "/actions", json=body, headers=client.headers
                ),
                range(2),
            )
        )
    assert [r.status_code for r in results] == [200, 200]
    assert results[0].json() == results[1].json()
    assert len(client.get("/observation")["samples"]) == 1
    with TestClient(create_app(app.state.store.path, ADMIN)) as restarted:
        result = restarted.post(client.base + "/actions", json=body, headers=client.headers)
        assert result.json() == results[0].json()
    body["parameters"]["volume_m3"] = 1e-7
    assert (
        transport.post(client.base + "/actions", json=body, headers=client.headers).status_code
        == 409
    )


def test_stale_revision_and_invalid_request_roll_back(setup):
    app, transport, client = setup
    body = request(client)
    client.act("observe_site", site_id=client.obs["sites"][0]["site_id"])
    before = app.state.store.state(client.episode_id)
    assert (
        transport.post(client.base + "/actions", json=body, headers=client.headers).status_code
        == 409
    )
    assert app.state.store.state(client.episode_id) == before
    body["expected_state_revision"] = client.obs["state_revision"]
    body["parameters"]["privileged"] = True
    assert (
        transport.post(client.base + "/actions", json=body, headers=client.headers).status_code
        == 422
    )


def test_collection_split_intervention_reconcile(setup):
    app, _transport, client = setup
    site = client.obs["sites"][0]["site_id"]
    sample = client.act("collect_sample", site_id=site, volume_m3=2e-7)
    state = app.state.store.state(client.episode_id)
    original = state["samples"][sample["sample_id"]]["amounts"]
    pair = client.act("split_sample", sample_id=sample["sample_id"])
    state = app.state.store.state(client.episode_id)
    for key in ("control_id", "treatment_id"):
        assert state["samples"][pair[key]]["amounts"] == [v / 2 for v in original]
    assert state["samples"][sample["sample_id"]]["volume_m3"] == 0
    client.act(
        "run_intervention",
        control_id=pair["control_id"],
        treatment_id=pair["treatment_id"],
        intervention="resource_pulse",
    )
    state = app.state.store.state(client.episode_id)
    assert state["ledger"]["external_in_token"] == pytest.approx(2e-7)
    assert state["diagnostics"]["global_inventory_residual_token"] < 1e-15
    assert len(client.obs["result"]["trace"]) == 9
    before = app.state.store.state(client.episode_id)
    body = request(
        client,
        "run_intervention",
        control_id=pair["control_id"],
        treatment_id=pair["treatment_id"],
        intervention="temperature_shift",
    )
    response = client.transport.post(client.base + "/actions", headers=client.headers, json=body)
    assert response.status_code == 409
    assert app.state.store.state(client.episode_id) == before


def test_budget_rejection_is_atomic(setup):
    app, transport, client = setup
    site = client.obs["sites"][0]["site_id"]
    sample = client.act("collect_sample", site_id=site, volume_m3=2e-7)
    pair = client.act("split_sample", sample_id=sample["sample_id"])
    # Reach the mission limit through permitted waits.
    for _ in range(9):
        client.act("wait_and_measure", site_id=site, duration_s=120)
    client.act("wait_and_measure", site_id=site, duration_s=100)
    before = app.state.store.state(client.episode_id)
    body = request(
        client,
        "run_intervention",
        control_id=pair["control_id"],
        treatment_id=pair["treatment_id"],
        intervention="temperature_shift",
    )
    response = transport.post(client.base + "/actions", headers=client.headers, json=body)
    assert response.status_code == 409
    assert response.json()["error"] == "insufficient_budget"
    assert app.state.store.state(client.episode_id) == before


@pytest.mark.parametrize("policy", ["passive", "random", "fixed", "adaptive"])
def test_complete_episode_and_frozen_conclusion(setup, policy):
    app, transport, client = setup
    report = run_policy(client, policy)
    assert report["outcome"] in (
        "candidate_mechanism_supported",
        "abiotic_explanation_supported",
        "inconclusive",
    )
    response = transport.get(
        f"/v1/admin/episodes/{client.episode_id}/evaluation",
        headers={"Authorization": f"Bearer {ADMIN}"},
    )
    assert response.status_code == 200
    assert response.json()["global_inventory_residual_token"] < 1e-15
    events = client.get("/events")["events"]
    assert [e["event_sequence"] for e in events] == list(range(len(events)))
    assert events[-1] == client.get("/observation")
    body = request(client)
    assert (
        transport.post(client.base + "/actions", headers=client.headers, json=body).status_code
        == 409
    )
    assert app.state.store.state(client.episode_id)["conclusion"] == client.obs["conclusion"]


def test_websocket_auth_and_resync(setup):
    _app, transport, client = setup
    client.act("observe_site", site_id=client.obs["sites"][0]["site_id"])
    with transport.websocket_connect(client.base + "/stream", headers=client.headers) as ws:
        assert ws.receive_json()["observation"]["event_sequence"] == 0
        assert ws.receive_json()["observation"]["event_sequence"] == 1
        ws.send_json({"type": "resync", "after": 0})
        assert ws.receive_json()["observation"]["event_sequence"] == 1
    from starlette.websockets import WebSocketDisconnect

    with pytest.raises(WebSocketDisconnect), transport.websocket_connect(client.base + "/stream"):
        pass


def test_config_rejects_unsupported_science(setup):
    _app, transport, _client = setup
    response = transport.post(
        "/v1/admin/episodes",
        json={"solvent_profile": "liquid_methane"},
        headers={"Authorization": f"Bearer {ADMIN}"},
    )
    assert response.status_code == 422


def test_small_container_budget_still_produces_a_conclusion(tmp_path):
    with TestClient(create_app(tmp_path / "small.sqlite3", ADMIN)) as transport:
        created = transport.post(
            "/v1/admin/episodes",
            json={"max_containers": 3},
            headers={"Authorization": f"Bearer {ADMIN}"},
        ).json()
        client = EpisodeClient(transport, created["episode_id"], created["investigator_token"])
        run_policy(client, "adaptive")
        assert client.obs["status"] == "concluded"
        assert client.obs["cumulative_costs"]["lab_actions"] == 1


def test_unobserved_evidence_cannot_support_a_conclusion(setup):
    app, transport, client = setup
    before = app.state.store.state(client.episode_id)
    body = request(
        client,
        "submit_conclusion",
        outcome="candidate_mechanism_supported",
        target_score=0.9,
        evidence_ids=["observation_99"],
        interpretation="A claim",
        alternatives=["Unknown"],
        limitations=["Synthetic"],
        next_experiment="Repeat",
    )
    response = transport.post(client.base + "/actions", json=body, headers=client.headers)
    assert response.status_code == 422
    assert app.state.store.state(client.episode_id) == before

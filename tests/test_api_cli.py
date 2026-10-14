import json

import pytest

pytest.importorskip("fastapi")
from fastapi.testclient import TestClient  # noqa: E402

from caterya.api.app import create_app  # noqa: E402
from caterya.cli.main import main  # noqa: E402
from caterya.provenance.signing import HAVE_ED25519  # noqa: E402

SYS = {"name": "api-sys", "version": "1", "provider": "mock", "model_id": "m", "model_version": "1"}


@pytest.fixture
def client(tmp_path):
    return TestClient(create_app(str(tmp_path)))


def test_api_flow(client):
    assert client.get("/v1/health").json()["status"] == "ok"
    r = client.post("/v1/evaluations", json={"system": SYS, "profile": "CATERYA-BASIC", "adapter": {"kind": "mock:robust"}}).json()
    cid, eid = r["car_id"], r["id"]
    assert client.get(f"/v1/assurance/{cid}/verify").json()["valid"]
    ev = client.get(f"/v1/evidence?evaluation_id={eid}").json()
    v = client.get(f"/v1/evidence/{ev[0]['id']}/verify").json()
    assert v["valid"] and v["inclusion_proof_valid"]
    bad = client.post(f"/v1/assurance/{cid}/decision", json={"decision": "ASSURED", "decided_by": "", "role": ""})
    assert bad.status_code == 409
    ok = client.post(f"/v1/assurance/{cid}/decision", json={"decision": "ASSURED", "decided_by": "A", "role": "lead"}).json()
    assert ok["level"] == (3 if HAVE_ED25519 else 1)
    assert "Assurance Record" in client.get(f"/v1/assurance/{cid}/report").text
    assert client.get(f"/v1/assurance/{cid}/regulatory?framework=OECD").json()["mapping"]["OECD"]
    assert client.get(f"/v1/graph/{eid}").json()["edges"]
    assert client.get("/ui/").status_code == 200


def test_api_rejects_forged_evidence_and_signals(client):
    r = client.post("/v1/evaluations", json={"system": SYS, "profile": "CATERYA-BASIC", "adapter": {"kind": "mock:robust"}}).json()
    ev = client.get(f"/v1/evidence?evaluation_id={r['id']}").json()[0]
    ev["result"] = 0.0001
    assert client.post("/v1/evidence", json=ev).status_code == 422
    s = client.post("/v1/monitor/signals", json={"system": "x", "signal": "s", "values": [0.9] * 50 + [0.4] * 30}).json()
    assert s["trigger"]["depth"] == "deep"


def test_api_key_protects_mutations(tmp_path, monkeypatch):
    monkeypatch.setenv("CATERYA_API_KEY", "k")
    c = TestClient(create_app(str(tmp_path)))
    body = {"system": SYS, "profile": "CATERYA-BASIC"}
    assert c.post("/v1/evaluations", json=body).status_code == 401
    assert c.post("/v1/evaluations", json=body, headers={"Authorization": "Bearer k"}).status_code == 200


def test_cli_end_to_end(tmp_path, capsys):
    h, out = str(tmp_path / "h"), str(tmp_path / "out")
    main(["--home", h, "evaluate", "--name", "cli-sys", "--version", "1", "--profile", "CATERYA-BASIC", "--out", out, "--json"])
    main(["--home", h, "evaluate", "--name", "cli-sys", "--version", "2", "--profile", "CATERYA-BASIC", "--adapter", "mock:brittle:0.9"])
    if HAVE_ED25519:
        with pytest.raises(SystemExit) as e:
            main(["--home", h, "evidence", "verify", f"{out}/bundle.json"])
        assert e.value.code == 0
    with pytest.raises(SystemExit) as e:
        main(["--home", h, "compare", "CAR-2026-000001", "CAR-2026-000002"])
    assert e.value.code == 4
    pol = tmp_path / "p.json"
    pol.write_text(json.dumps({"min_level": 2, "min_metric": {"robustness_perturbation_v1": 0.9}}))
    with pytest.raises(SystemExit) as e:
        main(["--home", h, "gate", "CAR-2026-000002", "--policy", str(pol)])
    assert e.value.code == 1
    main(["--home", h, "list", "profiles"])
    assert "CATERYA-AGENT" in capsys.readouterr().out

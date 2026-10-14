import math

import pytest

from caterya.core.canonical import canonical_bytes, digest
from caterya.core.config import CateryaConfig
from caterya.metrics.stats import auroc, bootstrap_ci, ece, mutual_information, shannon_entropy, spearman, wilson
from caterya.provenance.merkle import MerkleTree, verify_inclusion
from caterya.provenance.signing import HmacSigner
from caterya.provenance.zk import SelectiveDisclosure, commit, open_commitment, verify_disclosure


def test_canonical_is_order_independent_and_rejects_nan():
    assert canonical_bytes({"b": 1, "a": [1, 2]}) == canonical_bytes({"a": [1, 2], "b": 1})
    assert digest({"a": 1}).startswith("sha256:") and digest({"a": 1}, "sha3-256").startswith("sha3-256:")
    with pytest.raises(ValueError):
        canonical_bytes({"x": float("nan")})


@pytest.mark.parametrize("n", range(1, 12))
def test_merkle_inclusion_all_sizes(n):
    t = MerkleTree([str(i).encode() for i in range(n)])
    for i in range(n):
        assert verify_inclusion(t.leaves[i], i, n, t.proof(i), t.root())
    if n > 1:
        assert not verify_inclusion(t.leaves[0], 1, n, t.proof(0), t.root())


def test_selective_disclosure_and_commitment():
    sd = SelectiveDisclosure({"a": 1, "b": "secret", "c": [1, 2]})
    rev = sd.reveal(["a"])[0]
    assert verify_disclosure(sd.root, rev)
    rev["value"] = 2
    assert not verify_disclosure(sd.root, rev)
    c, salt = commit({"x": 1})
    assert open_commitment(c, {"x": 1}, salt) and not open_commitment(c, {"x": 2}, salt)


def test_stats_sanity():
    assert math.isclose(shannon_entropy([1, 1]), 1.0)
    lo, hi = wilson(5, 10)
    assert lo < 0.5 < hi
    assert auroc([2, 3], [0, 1]) == 1.0
    assert math.isclose(spearman([1, 2, 3], [1, 2, 3]), 1.0)
    assert ece([0.9] * 10, [True] * 9 + [False]) < 1e-9
    assert mutual_information([(0, 0), (1, 1)] * 50) > 0.5
    lo, hi = bootstrap_ci([0.0, 1.0] * 20, seed=1)
    assert lo < 0.5 < hi


def test_config_env_override(monkeypatch):
    monkeypatch.setenv("CATERYA_TTL_DAYS", "7")
    monkeypatch.setenv("CATERYA_ENABLE_QUANTUM", "true")
    monkeypatch.setenv("CATERYA_RISK_THRESHOLDS", "[0.2,0.3,0.4]")
    c = CateryaConfig.from_env()
    assert c.ttl_days == 7 and c.enable_quantum is True and c.risk_thresholds == [0.2, 0.3, 0.4]
    assert len(CateryaConfig.describe()) > 40


def test_hmac_signer_roundtrip():
    s = HmacSigner()
    sig = s.sign(b"x")
    assert s.verifier().verify(b"x", sig) and not s.verifier().verify(b"y", sig)

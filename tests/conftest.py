import pytest

from caterya.adapters.mock import MockModel
from caterya.core.system import SystemDescriptor
from caterya.evaluators.runner import EvaluationRunner


@pytest.fixture
def system():
    return SystemDescriptor("t-sys", "1.0.0", provider="mock", model_id="m", model_version="1", code_hash="sha256:c",
                            environment={"img": "x"}, dataset_hashes={"d": "sha256:d"})


@pytest.fixture
def runner():
    return EvaluationRunner()


@pytest.fixture
def robust():
    return MockModel("robust")

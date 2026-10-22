"""Numeric and HTTP compatibility checks for paper-specific packages."""
import pytest
from fastapi.testclient import TestClient

from minifls.api import app
from minifls.methods import fedavg, fedlbw


def test_paper_weights_preserve_original_formulas():
    assert fedavg.weights([1, 3], []) == [.25, .75]
    assert fedlbw.weights([100, 1], [1., 2.]) == pytest.approx([2 / 3, 1 / 3])
    assert fedlbw.weights([1, 1], [0., 0.]) == [.5, .5]
    assert fedlbw.weights([1, 1], [1e-300, 1e300]) == pytest.approx([1., 0.])
    for samples in ([], [0, 1], [-1, 2]):
        with pytest.raises(ValueError):
            fedavg.weights(samples, [])
    for losses in ([], [-1., 1.], [float("nan"), 1.], [float("inf"), 1.]):
        with pytest.raises(ValueError):
            fedlbw.weights([1, 1], losses)


def test_method_routes_and_unimplemented_methods_fail_explicitly():
    client = TestClient(app)
    catalog = client.get("/methods").json()
    assert set(catalog["methods"]) == {"fedavg", "fedlbw"}
    assert len(catalog["catalog"]) == 9
    response = client.post("/methods/fedavg/weights", json={"samples": [1, 3]})
    assert response.status_code == 200
    assert response.json() == {"method": "fedavg", "weights": [.25, .75]}
    response = client.post("/methods/fedlbw/weights", json={"samples": [1, 3], "losses": [2., 1.]})
    assert response.status_code == 200
    assert response.json()["weights"] == pytest.approx([1 / 3, 2 / 3])
    for method in ("fedprox", "oort", "fairfedcs", "longfed", "fedavgm", "fednova", "scaffold"):
        assert client.post(f"/methods/{method}/weights", json={"samples": [1]}).status_code == 501
    assert client.post("/methods/typo/weights", json={"samples": [1]}).status_code == 400
    assert client.post("/methods/fedlbw/weights", json={"samples": [1]}).status_code == 400
    assert client.post("/methods/fedavg/weights", json={"samples": [0]}).status_code == 400

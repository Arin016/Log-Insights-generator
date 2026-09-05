import pytest

from core.v2.calibration import IsotonicCalibrator,LogisticCalibrator,calibration_metrics


def labels():
    return [{"score":i/10,"supported":int(i>4),"split":"development","provenance":"independent-adjudicated",
             "group_id":"test-fixture-development"} for i in range(10)]


@pytest.mark.parametrize("cls",[IsotonicCalibrator,LogisticCalibrator])
def test_calibrator_contract_and_leakage_gate(cls):
    rows=labels();model=cls.fit(rows)
    values=[model.predict(i/10) for i in range(10)]
    assert values==sorted(values) and all(0<=p<=1 for p in values)
    with pytest.raises(ValueError):cls.fit([r|{"split":"test"} for r in rows])
    with pytest.raises(ValueError):cls.fit([r|{"provenance":"synthetic-generator"} for r in rows])
    with pytest.raises(ValueError):calibration_metrics(model,rows)
    assert calibration_metrics(model,[r|{"group_id":"heldout-fixture"} for r in rows])["denominator"]==10

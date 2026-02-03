import pytest
from main import build_model_instance_from_transaction


def test_build_instance_basics():
    tx = {
        'transaction_id': 'tx1',
        'amount': 123.45,
        'timestamp': '2023-10-27T12:34:56Z',
        'V1': 0.5,
        'V28': -1.25
    }
    inst = build_model_instance_from_transaction(tx)
    # Basic keys exist
    assert 'Amount' in inst and isinstance(inst['Amount'], float)
    assert 'Time' in inst and isinstance(inst['Time'], float)
    # V1 and V28 should be floats and equal to provided values
    assert inst['V1'] == float(0.5)
    assert inst['V28'] == float(-1.25)
    # V2..V27 should exist and be floats (defaults)
    for i in range(2, 28):
        key = f'V{i}'
        assert key in inst
        assert isinstance(inst[key], float)


def test_build_instance_missing_values_defaults():
    tx = {'transaction_id': 'tx2'}
    inst = build_model_instance_from_transaction(tx)
    assert inst['Amount'] == 0.0
    assert isinstance(inst['Time'], float)
    for i in range(1, 29):
        assert isinstance(inst[f'V{i}'], float)


if __name__ == '__main__':
    pytest.main([__file__])

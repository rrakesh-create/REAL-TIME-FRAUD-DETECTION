import sys
import os
import json
import base64

from importlib import util as _importlib_util
_module_path = os.path.join(os.path.dirname(os.path.abspath(__file__)), "cloud project", "fraud-alert-system", "functions", "fraud_checker", "main.py")
spec = _importlib_util.spec_from_file_location("fraud_checker_main", _module_path)
if spec is None or spec.loader is None:
    raise ImportError(f"Could not load fraud_checker module from {_module_path}")
fc = _importlib_util.module_from_spec(spec)
spec.loader.exec_module(fc)

# create a test transaction
from datetime import datetime
tx = {
    'transaction_id': 'local-run-' + datetime.utcnow().strftime('%Y%m%d%H%M%S'),
    'amount': 55.5,
    'user_id': 'local-test',
    'merchant_score': 0.9,
    'device_score': 0.95,
    'timestamp': datetime.utcnow().isoformat() + 'Z'
}

payload = base64.b64encode(json.dumps(tx).encode('utf-8')).decode('utf-8')
event = {'data': payload}

print('Calling fraud_checker for tx id:', tx['transaction_id'])
try:
    fc.fraud_checker(event, None)
    print('Done - check Firestore for fraud_alerts document with id', tx['transaction_id'])
except Exception as e:
    print('Error running fraud_checker:', e)
    raise

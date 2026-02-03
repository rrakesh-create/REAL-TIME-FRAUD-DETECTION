import sys
import os
import json
import base64
from datetime import datetime

from importlib import util as _importlib_util
_module_path = r"C:\Users\RAKESH\Desktop\cnai project\cloud project\fraud-alert-system\functions\fraud_checker\main.py"
spec = _importlib_util.spec_from_file_location("fraud_checker_main", _module_path)
if spec is None or spec.loader is None:
    raise ImportError(f"Could not load fraud_checker module from {_module_path}")
fc = _importlib_util.module_from_spec(spec)
spec.loader.exec_module(fc)

from google.cloud import firestore

# create a synthetic high-prob transaction to trigger alert via heuristic
tx_id = 'dryrun-alert-' + datetime.utcnow().strftime('%Y%m%d%H%M%S')
transaction = {
    'transaction_id': tx_id,
    'amount': 9999.99,
    'user_id': 'demo-user',
    'merchant_score': 0.99,
    'device_score': 0.99,
    'user_phone': os.environ.get('DEMO_RECIPIENT', '+10000000000'),
    'timestamp': datetime.utcnow().isoformat() + 'Z'
}

print('Transaction to publish (dry-run):')
print(json.dumps(transaction, indent=2))

# create base64 payload as Pub/Sub would deliver
payload = base64.b64encode(json.dumps(transaction).encode('utf-8')).decode('utf-8')
event = {'data': payload}

print('\nInvoking local fraud_checker handler...')
try:
    fc.fraud_checker(event, None)
except Exception as e:
    print('Handler raised:', e)

# read back the alert doc from Firestore
db = firestore.Client()
alert_doc = db.collection('fraud_alerts').document(tx_id).get()
if alert_doc.exists:
    print('\nfraud_alerts document:')
    print(json.dumps({'id': alert_doc.id, **alert_doc.to_dict()}, default=str, indent=2))
else:
    print('\nNo fraud_alerts doc written (check logs).')

# Construct the SMS body that would be sent
# We follow the same format used in the handler
if alert_doc.exists:
    doc = alert_doc.to_dict()
    prob = doc.get('fraud_probability')
    sms_body = f"ALERT: Transaction {tx_id} suspected fraud (prob={prob:.2f})."
    print('\n[DRY-RUN] SMS body that would be sent:')
    print(sms_body)
else:
    print('\n[DRY-RUN] No SMS would be sent because no alert doc was written.')

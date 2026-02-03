from google.cloud import firestore
import json

PROJECT = 'fraud-detection-475817'
TX_ID = 'tx-e2e-test-1'

print(f"Querying Firestore project={PROJECT} for transaction_id={TX_ID}")

db = firestore.Client(project=PROJECT)
doc_ref = db.collection('fraud_alerts').document(TX_ID)
doc = doc_ref.get()
if not doc.exists:
    print('Document not found')
else:
    print('Document found:')
    print(json.dumps(doc.to_dict(), indent=2, default=str))

"""Process transactions locally and populate `fraud_alerts` so the dashboard shows statuses.

Usage:
  python process_transactions_locally.py [--limit N]

This script:
 - loads the function module at `cloud project/fraud-alert-system/functions/fraud_checker/main.py`
 - queries Firestore for recent transactions (default limit 100)
 - for each transaction that has no `fraud_alerts` document, computes fraud_probability
   using the same `get_fraud_probability` logic and writes a `fraud_alerts` document.

This is intended as a safe local fallback for demos when Cloud Run/Cloud Function
push delivery is flaky.
"""
import sys
import os
import argparse
import json
from google.cloud import firestore

# Import the functions module
from importlib import util as _importlib_util
_module_path = r"C:\Users\RAKESH\Desktop\cnai project\cloud project\fraud-alert-system\functions\fraud_checker\main.py"
spec = _importlib_util.spec_from_file_location("fraud_checker_main", _module_path)
if spec is None or spec.loader is None:
    raise ImportError(f"Could not load fraud_checker module from {_module_path}")
fc = _importlib_util.module_from_spec(spec)
spec.loader.exec_module(fc)


def main(limit: int = 100):
    db = firestore.Client()
    tx_col = db.collection('transactions')
    alerts_col = db.collection('fraud_alerts')

    # Get recent transactions ordered by timestamp if available, else limit
    docs = tx_col.order_by('timestamp', direction=firestore.Query.DESCENDING).limit(limit).stream()

    processed = 0
    new_alerts = 0
    for d in docs:
        tx = d.to_dict()
        tx_id = tx.get('transaction_id') or d.id
        if not tx_id:
            print('Skipping transaction with no id (doc):', d.id)
            continue

        # check existing alert
        alert_doc = alerts_col.document(tx_id).get()
        if alert_doc.exists:
            # already processed
            continue

        processed += 1
        print(f'Processing transaction {tx_id}...')

        try:
            model_instance = fc.build_model_instance_from_transaction(tx)
            try:
                prob = fc.get_fraud_probability(model_instance)
                inference_source = 'model'
            except Exception as e:
                print('Model backends failed, attempting heuristic fallback:', e)
                # heuristic
                prob = None
                inference_source = None
                try:
                    m = float(tx.get('merchant_score')) if tx.get('merchant_score') is not None else None
                    dscore = float(tx.get('device_score')) if tx.get('device_score') is not None else None
                    if m is not None and dscore is not None:
                        prob = float((m + dscore) / 2.0)
                        inference_source = 'heuristic_merchant_device_avg'
                except Exception:
                    pass

            should_alert = (prob is not None and prob > fc.ALERT_THRESHOLD)

            alert_doc_data = {
                'transaction_id': tx_id,
                'amount': tx.get('amount'),
                'user_id': tx.get('user_id'),
                'fraud_probability': prob if prob is not None else -1,
                'message': (
                    'Potential fraud detected!' if should_alert else ('Transaction deemed legitimate.' if prob is not None else 'Prediction error')
                ),
                'prediction_error': None if prob is not None else 'Prediction error or unavailable',
                'inference_source': inference_source,
                'is_alert': bool(should_alert),
            }

            alerts_col.document(tx_id).set({**alert_doc_data, 'timestamp': firestore.SERVER_TIMESTAMP})
            new_alerts += 1
            print(f'Wrote fraud_alerts/{tx_id} (prob={alert_doc_data["fraud_probability"]})')

        except Exception as e:
            print('Failed processing transaction', tx_id, ':', e)

    print(f'Done. Processed up to {processed} transactions, created {new_alerts} new alerts.')


if __name__ == '__main__':
    p = argparse.ArgumentParser()
    p.add_argument('--limit', type=int, default=100, help='How many recent transactions to scan')
    args = p.parse_args()
    main(limit=args.limit)

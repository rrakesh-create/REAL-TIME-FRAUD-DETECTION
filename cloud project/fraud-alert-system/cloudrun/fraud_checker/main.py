from fastapi import FastAPI, Request
import base64
import json
import os
from google.cloud import pubsub_v1
from google.cloud import firestore

app = FastAPI()

PROJECT_ID = os.environ.get('GCP_PROJECT') or os.environ.get('PROJECT_ID') or 'fraud-detection-475817'
VERTEX_AI_ENDPOINT_ID = os.environ.get('VERTEX_AI_ENDPOINT_ID', '')
VERTEX_AI_PROJECT = os.environ.get('VERTEX_AI_PROJECT', PROJECT_ID)
VERTEX_AI_LOCATION = os.environ.get('VERTEX_AI_LOCATION', 'us-central1')
ALERT_TOPIC_NAME = os.environ.get('ALERT_TOPIC_NAME', 'fraud-alerts-topic')

publisher = pubsub_v1.PublisherClient()
alert_topic_path = publisher.topic_path(PROJECT_ID, ALERT_TOPIC_NAME)
db = firestore.Client(project=PROJECT_ID)


def call_vertex_ai_predict(instance: dict) -> float:
    # If a MODEL_SERVER_URL env var is set, call that HTTP predict endpoint instead of Vertex SDK
    model_server = os.environ.get('MODEL_SERVER_URL')
    if model_server:
        print(f"Using MODEL_SERVER_URL={model_server}")
        try:
            import requests
            payload = {"instances": [instance]}
            resp = requests.post(model_server, json=payload, timeout=30)
            print(f"Model server HTTP status: {resp.status_code}")
            resp.raise_for_status()
            body = resp.json()
            print(f"Model server response body: {body}")
            preds = body.get('predictions') or body.get('outputs')
            if preds:
                p0 = preds[0]
                if isinstance(p0, dict) and 'fraud_probability' in p0:
                    return float(p0['fraud_probability'])
                if isinstance(p0, (list, tuple)):
                    return float(p0[0])
            raise RuntimeError(f"Unable to parse model server response: {body}")
        except Exception as e:
            raise RuntimeError(f"Model server HTTP predict failed: {e}")

    # Fallback: lazy import Vertex SDK to call endpoint
    from google.cloud import aiplatform as _aiplatform
    _aiplatform.init(project=VERTEX_AI_PROJECT, location=VERTEX_AI_LOCATION)
    endpoint = _aiplatform.Endpoint(endpoint_name=VERTEX_AI_ENDPOINT_ID)
    prediction = endpoint.predict(instances=[instance])
    try:
        pred0 = prediction.predictions[0]
        if isinstance(pred0, dict) and 'fraud_probability' in pred0:
            return float(pred0['fraud_probability'])
        if isinstance(pred0, (list, tuple)):
            return float(pred0[0])
    except Exception:
        pass
    raise RuntimeError(f"Unable to parse prediction response: {prediction}")


@app.post('/pubsub')
async def pubsub_push(request: Request):
    """Endpoint to receive Pub/Sub push messages. Expects JSON body with {'message': {'data': '<base64>'}}"""
    # Robust parsing: Pub/Sub push, Eventarc/CloudEvent envelope, or raw JSON
    payload = await request.json()
    # Log raw payload for debugging (helpful to diagnose push format differences)
    try:
        print("RAW_PUSH_PAYLOAD:", json.dumps(payload)[:1000])
    except Exception:
        print("RAW_PUSH_PAYLOAD: (unable to stringify payload)")

    # Helper to extract base64 data string from known envelopes
    def _extract_b64_from_payload(p):
        # Typical push: {"message": {"data": "..."}}
        if isinstance(p, dict):
            if 'message' in p and isinstance(p['message'], dict) and p['message'].get('data'):
                return p['message'].get('data')
            # CloudEvent style: data may be under 'data' and contain 'message'
            if 'data' in p:
                d = p['data']
                if isinstance(d, dict) and d.get('message') and isinstance(d.get('message'), dict) and d['message'].get('data'):
                    return d['message'].get('data')
                # sometimes CloudEvent provides the raw message as base64 string in data
                if isinstance(d, str):
                    return d
        return None

    data_b64 = _extract_b64_from_payload(payload)
    # If not found, maybe payload itself is the base64 string or raw JSON
    transaction = None
    if data_b64:
        try:
            data = base64.b64decode(data_b64).decode('utf-8')
            transaction = json.loads(data)
        except Exception as e:
            print(f"Failed to decode base64 payload: {e}")
            # fallthrough to try to interpret data_b64 as raw json
            try:
                transaction = json.loads(data_b64)
            except Exception:
                transaction = None
    else:
        # try raw JSON body being the transaction itself
        try:
            # If payload contains keys like 'transaction_id', treat it as transaction
            if isinstance(payload, dict) and payload.get('transaction_id'):
                transaction = payload
            else:
                # try nested shapes: some systems embed the message directly under 'message' as JSON string
                if isinstance(payload.get('message'), dict) and payload['message'].get('attributes'):
                    # no-op, leave transaction None
                    transaction = None
                elif isinstance(payload.get('message'), str):
                    try:
                        transaction = json.loads(payload.get('message'))
                    except Exception:
                        transaction = None
        except Exception:
            transaction = None

    if not transaction:
        print("No transaction data found in push payload")
        return {"status": "no data"}

    # Save transaction to Firestore
    try:
        tx_id = transaction.get('transaction_id') or transaction.get('id')
        if not tx_id:
            return {"error": "missing transaction_id"}
        doc_ref = db.collection('transactions').document(tx_id)
        doc_ref.set({**transaction, 'timestamp': firestore.SERVER_TIMESTAMP})
    except Exception as e:
        return {"error": f"failed to save tx: {e}"}

    # Call Vertex
    try:
        fraud_probability = call_vertex_ai_predict(transaction)
    except Exception as e:
        return {"error": f"vertex predict failed: {e}"}

    # Publish alert if fraudulent and always save a result document so the dashboard
    # can display the fraud probability/status for every transaction.
    try:
        is_alert = (fraud_probability is not None and fraud_probability > 0.5)
        if is_alert:
            alert = {
                'transaction_id': tx_id,
                'amount': transaction.get('amount'),
                'user_id': transaction.get('user_id'),
                'fraud_probability': fraud_probability,
                'message': 'Potential fraud detected'
            }
            publisher.publish(alert_topic_path, json.dumps(alert).encode('utf-8'))

        # Save result to Firestore for dashboard visibility (include is_alert flag)
        try:
            db.collection('fraud_alerts').document(tx_id).set({
                'transaction_id': tx_id,
                'amount': transaction.get('amount'),
                'user_id': transaction.get('user_id'),
                'fraud_probability': fraud_probability if fraud_probability is not None else -1,
                'message': 'Potential fraud detected' if is_alert else 'Transaction checked',
                'is_alert': bool(is_alert),
                'timestamp': firestore.SERVER_TIMESTAMP,
            })
        except Exception as e:
            # don't fail the whole request if Firestore write fails
            print(f"Failed to save fraud result to Firestore: {e}")
    except Exception as e:
        return {"error": f"failed to publish alert: {e}"}

    return {"status": "processed", "fraud_probability": fraud_probability}

import os
import json
import base64
from typing import Dict

from google.cloud import pubsub_v1
# Note: heavy libraries are imported lazily inside functions to reduce cold-start memory
aiplatform = None
secretmanager = None
firestore = None
TwilioClient = None


# Configuration (can be overridden by environment variables or Secret Manager)
PROJECT_ID = os.environ.get('GCP_PROJECT') or os.environ.get('PROJECT_ID') or 'fraud-detection-475817'
VERTEX_AI_ENDPOINT_ID = os.environ.get('VERTEX_AI_ENDPOINT_ID', 'projects/fraud-detection-475817/locations/us-central1/endpoints/7026960121418743808')
VERTEX_AI_PROJECT = os.environ.get('VERTEX_AI_PROJECT', PROJECT_ID)
VERTEX_AI_LOCATION = os.environ.get('VERTEX_AI_LOCATION', 'us-central1')
MODEL_SERVER_URL = os.environ.get('MODEL_SERVER_URL', '')
ALERT_TOPIC_NAME = os.environ.get('ALERT_TOPIC_NAME', 'fraud-alerts-topic')
# Parse ALERT_THRESHOLD defensively: env var may be malformed (e.g. concatenated flags).
try:
    ALERT_THRESHOLD = float(os.environ.get('ALERT_THRESHOLD', '0.5'))
except Exception:
    raw_thresh = os.environ.get('ALERT_THRESHOLD')
    print(f"Warning: could not parse ALERT_THRESHOLD='{raw_thresh}', using default 0.5")
    ALERT_THRESHOLD = 0.5

SAVE_ALL_ALERTS = os.environ.get('SAVE_ALL_ALERTS', 'false').lower() in ('1', 'true', 'yes')

# Twilio config (env vars or secrets)
TWILIO_ACCOUNT_SID = os.environ.get('TWILIO_ACCOUNT_SID', '')
TWILIO_AUTH_TOKEN = os.environ.get('TWILIO_AUTH_TOKEN', '')
TWILIO_FROM_NUMBER = os.environ.get('TWILIO_FROM_NUMBER', '')

# Clients
publisher = pubsub_v1.PublisherClient()
alert_topic_path = publisher.topic_path(PROJECT_ID, ALERT_TOPIC_NAME)
# secret_client will be created lazily when needed
secret_client = None
firestore_client = None


def call_vertex_ai_predict(instance: Dict) -> float:
    if not VERTEX_AI_ENDPOINT_ID:
        raise RuntimeError("VERTEX_AI_ENDPOINT_ID environment variable is required")

    # lazy import to keep memory usage low during cold start
    global aiplatform
    if aiplatform is None:
        # Try common import paths and surface a helpful error if none work.
        try:
            from google.cloud import aiplatform as _aiplatform
            aiplatform = _aiplatform
        except Exception as imp_e:
            try:
                # Alternate import path sometimes present in different packaging layouts
                import google.cloud.aiplatform as _aiplatform
                aiplatform = _aiplatform
            except Exception as imp_e2:
                raise ImportError(f"Failed to import aiplatform (tried multiple paths): {imp_e}; {imp_e2}")

    aiplatform.init(project=VERTEX_AI_PROJECT, location=VERTEX_AI_LOCATION)
    endpoint = aiplatform.Endpoint(endpoint_name=VERTEX_AI_ENDPOINT_ID)
    # Vertex AutoML sometimes expects values encoded as strings (see model's input baselines).
    # Convert values to strings to match the training schema where necessary.
    vertex_instance = {k: (str(v) if v is not None else "") for k, v in instance.items()}
    # Use Vertex REST predict endpoint via an AuthorizedSession to avoid the
    # heavy `google-cloud-aiplatform` dependency in the Cloud Function build.
    try:
        import google.auth
        from google.auth.transport.requests import AuthorizedSession
        creds, _ = google.auth.default(scopes=["https://www.googleapis.com/auth/cloud-platform"])
        authed_session = AuthorizedSession(creds)
        # VERTEX_AI_ENDPOINT_ID is the full resource name like
        # projects/PROJECT/locations/LOCATION/endpoints/ENDPOINT
        url = f"https://{VERTEX_AI_LOCATION}-aiplatform.googleapis.com/v1/{VERTEX_AI_ENDPOINT_ID}:predict"
        body = {"instances": [vertex_instance]}
        resp = authed_session.post(url, json=body, timeout=30)
        resp.raise_for_status()
        prediction = resp.json()
    except Exception as e:
        # If REST call fails, try the aiplatform client as a fallback (if present)
        try:
            if aiplatform is None:
                from google.cloud import aiplatform as _aiplatform
                aiplatform = _aiplatform
            aiplatform.init(project=VERTEX_AI_PROJECT, location=VERTEX_AI_LOCATION)
            endpoint = aiplatform.Endpoint(endpoint_name=VERTEX_AI_ENDPOINT_ID)
            prediction = endpoint.predict(instances=[vertex_instance])
        except Exception:
            raise RuntimeError(f"Vertex REST call failed and aiplatform fallback also failed: {e}")

    # Robust parsing of Vertex responses. Vertex AutoML usually returns an object
    # whose `predictions` is a list. Each element can be a dict containing
    # 'scores' and 'classes' (or other keys), or a numeric/list return.
    try:
        # `prediction` may be a dict (REST response) or an object with attribute `predictions`.
        if isinstance(prediction, dict):
            preds = prediction.get('predictions')
        else:
            preds = getattr(prediction, 'predictions', None)
        if not preds:
            raise RuntimeError('Empty predictions')
        p0 = preds[0]

        # If the prediction is a dict with explicit fraud_probability
        if isinstance(p0, dict):
            if 'fraud_probability' in p0:
                return float(p0['fraud_probability'])

            # Common AutoML shape: {'scores': [...], 'classes': [...]}.
            if 'scores' in p0 and 'classes' in p0:
                scores = p0.get('scores')
                classes = p0.get('classes')
                # find index for class label '1' (string) or numeric 1
                target_idx = None
                for idx, lab in enumerate(classes):
                    if str(lab) == '1' or str(lab).lower() in ('true', 'fraud', '1'):
                        target_idx = idx
                        break
                if target_idx is None:
                    # default to second class if present, else first
                    target_idx = 1 if isinstance(scores, (list, tuple)) and len(scores) > 1 else 0
                return float(scores[target_idx])

            # Some variants use keys like 'probabilities' or 'probs'
            for key in ('probabilities', 'probs', 'scores'):
                if key in p0 and isinstance(p0[key], (list, tuple)) and p0[key]:
                    arr = p0[key]
                    return float(arr[1]) if len(arr) > 1 else float(arr[0])

            # Try to find any numeric value in the dict
            for v in p0.values():
                if isinstance(v, (int, float)):
                    return float(v)

        # If the prediction element is a list/tuple, assume first element is probability
        if isinstance(p0, (list, tuple)) and p0:
            # if nested dict inside, attempt to parse that
            first = p0[0]
            if isinstance(first, dict):
                # reuse dict parsing above
                if 'fraud_probability' in first:
                    return float(first['fraud_probability'])
                if 'scores' in first and isinstance(first['scores'], (list, tuple)):
                    return float(first['scores'][1]) if len(first['scores']) > 1 else float(first['scores'][0])
            try:
                return float(first)
            except Exception:
                pass

        # If element itself is numeric
        if isinstance(p0, (int, float)):
            return float(p0)

    except Exception:
        # fall through to raise below with raw prediction for debugging
        pass

    raise RuntimeError(f"Unable to parse prediction response: {prediction}")


def call_http_model_server(instance: Dict) -> float:
    """Call a plain HTTP model server (Cloud Run / FastAPI) returning JSON.

    Expected flexible responses:
      - {"fraud_probability": 0.9}
      - [0.9] or 0.9
    """
    if not MODEL_SERVER_URL:
        raise RuntimeError("MODEL_SERVER_URL not configured")

    # lazy import requests
    try:
        import requests
    except Exception as e:
        raise RuntimeError(f"requests library is required to call MODEL_SERVER_URL: {e}")

    url = MODEL_SERVER_URL.rstrip('/') + '/predict'
    try:
        resp = requests.post(url, json=instance, timeout=20)
        resp.raise_for_status()
        body = resp.json()
    except Exception as e:
        raise RuntimeError(f"HTTP model server call failed: {e}")

    # parse flexible response shapes
    if isinstance(body, dict):
        if 'fraud_probability' in body:
            return float(body['fraud_probability'])
        # some model servers return {'predictions': [ ... ]}
        if 'predictions' in body and isinstance(body['predictions'], (list, tuple)) and body['predictions']:
            p0 = body['predictions'][0]
            if isinstance(p0, dict) and 'fraud_probability' in p0:
                return float(p0['fraud_probability'])
            if isinstance(p0, (list, tuple)):
                return float(p0[0])
            return float(p0)
    elif isinstance(body, (list, tuple)) and body:
        return float(body[0])
    elif isinstance(body, (int, float)):
        return float(body)

    raise RuntimeError(f"Unable to parse HTTP model server response: {body}")


def get_fraud_probability(instance: Dict) -> float:
    """Get fraud probability, preferring MODEL_SERVER_URL, falling back to Vertex AI.
    Raises RuntimeError on failure.
    """
    # Try HTTP model server first if configured
    if MODEL_SERVER_URL:
        try:
            prob = call_http_model_server(instance)
            print(f"Model server returned fraud_probability={prob}")
            return prob
        except Exception as e:
            print(f"Model server call failed, falling back to Vertex AI: {e}")

    # Fallback to Vertex AI if configured
    try:
        prob = call_vertex_ai_predict(instance)
        print(f"Vertex AI returned fraud_probability={prob}")
        return prob
    except Exception as e:
        raise RuntimeError(f"All model backends failed: {e}")


def build_model_instance_from_transaction(transaction: Dict) -> Dict:
    """Build a model input instance matching the deployed AutoML model schema.

    The deployed model expects these features (from model inspect):
      - Amount, Time, V1..V28
    We map available transaction fields to these names and use sensible defaults (0) when missing.
    """
    def _sanitize_numeric_to_string(val, is_time=False, decimals=6):
        """Return a cleaned numeric string for the model input.

        - strips commas and currency symbols
        - converts common decimal comma to dot
        - returns '0.0' for invalid/missing values
        - for time values, uses 1 decimal place (e.g. '46200.0')
        """
        if val is None:
            return '0.0'
        # If already a string, clean it
        try:
            if isinstance(val, str):
                s = val.strip()
                # remove currency symbols and spaces
                for ch in ('$','€','£'):
                    s = s.replace(ch, '')
                # remove thousands separators
                s = s.replace(',', '')
                # normalize decimal comma
                s = s.replace(';', '').replace('\u00A0', '')
                s = s.replace(',', '.')
                f = float(s)
            else:
                f = float(val)
        except Exception:
            return '0.0'
        if is_time:
            return f"{f:.1f}"
        # choose decimals
        fmt = f"{{:.{decimals}f}}"
        return fmt.format(f)

    model_instance = {}
    # Amount: map from transaction['amount'] or 0
    try:
        amt_raw = transaction.get('amount') or transaction.get('Amount') or 0.0
        model_instance['Amount'] = _sanitize_numeric_to_string(amt_raw, is_time=False, decimals=1)
    except Exception:
        model_instance['Amount'] = '0.0'

    # Time: the model expects numeric seconds-of-day encoded as a string (e.g. '84779.0').
    ts = transaction.get('timestamp') or transaction.get('time') or transaction.get('Time')
    time_val = None
    if ts is not None:
        # If ISO string, parse to datetime
        if isinstance(ts, str):
            try:
                from datetime import datetime
                dt = None
                try:
                    # accept Z suffix or offset
                    dt = datetime.fromisoformat(ts.replace('Z', '+00:00'))
                except Exception:
                    # try numeric parse
                    try:
                        dt = datetime.utcfromtimestamp(float(ts))
                    except Exception:
                        dt = None
                if dt is not None:
                    time_val = dt.hour * 3600 + dt.minute * 60 + dt.second
            except Exception:
                time_val = None
        else:
            # numeric timestamp (epoch seconds)
            try:
                import datetime as _dt
                epoch = float(ts)
                dt = _dt.datetime.utcfromtimestamp(epoch)
                time_val = dt.hour * 3600 + dt.minute * 60 + dt.second
            except Exception:
                time_val = None

    if time_val is None:
        # fallback to current seconds-of-day
        try:
            from datetime import datetime
            now = datetime.utcnow()
            time_val = now.hour * 3600 + now.minute * 60 + now.second
        except Exception:
            time_val = 0

    # Encode as a numeric string to match AutoML instance schema (e.g. '84779.0')
    try:
        model_instance['Time'] = _sanitize_numeric_to_string(time_val, is_time=True)
    except Exception:
        model_instance['Time'] = str(time_val)

    # V1..V28: try to map from transaction fields V1..V28 if present, else default 0.0
    for i in range(1, 29):
        key = f'V{i}'
        # accept lowercase variants or prefixed names
        val = transaction.get(key) if key in transaction else (transaction.get(key.lower()) or transaction.get(f'v{i}'))
        try:
            model_instance[key] = _sanitize_numeric_to_string(val, is_time=False, decimals=6)
        except Exception:
            model_instance[key] = '0.0'

    return model_instance


def access_secret_version(secret_name: str) -> str:
    # lazy import Secret Manager client
    global secret_client
    if secret_client is None:
        from google.cloud import secretmanager as _secretmanager
        secret_client = _secretmanager.SecretManagerServiceClient()

    if secret_name.startswith("projects/"):
        name = f"{secret_name}/versions/latest"
    else:
        name = f"projects/{PROJECT_ID}/secrets/{secret_name}/versions/latest"
    response = secret_client.access_secret_version(request={"name": name})
    return response.payload.data.decode('UTF-8')


def send_sms_via_twilio(to_number: str, body: str) -> str:
    account_sid = TWILIO_ACCOUNT_SID
    auth_token = TWILIO_AUTH_TOKEN
    from_number = TWILIO_FROM_NUMBER

    try:
        if not account_sid:
            account_sid = access_secret_version('TWILIO_ACCOUNT_SID')
        if not auth_token:
            auth_token = access_secret_version('TWILIO_AUTH_TOKEN')
        if not from_number:
            from_number = access_secret_version('TWILIO_FROM_NUMBER')
    except Exception:
        pass

    if not (account_sid and auth_token and from_number):
        raise RuntimeError("Twilio credentials are required via environment variables or Secret Manager")

    # lazy import Twilio client to avoid importing at module load
    global TwilioClient
    if TwilioClient is None:
        from twilio.rest import Client as _TwilioClient
        TwilioClient = _TwilioClient

    client = TwilioClient(account_sid, auth_token)
    message = client.messages.create(body=body, from_=from_number, to=to_number)
    return message.sid


def fraud_checker(event, context):
    global firestore_client
    # Robust decoding: accept several envelope shapes (background Pub/Sub, push, CloudEvent)
    transaction = None
    try:
        data_b64 = None
        # common background function shape: event['data'] is base64
        if isinstance(event, dict):
            if 'data' in event and isinstance(event['data'], str):
                data_b64 = event['data']
            # push/publisher wrapper: {"message": {"data": ...}}
            elif 'message' in event and isinstance(event['message'], dict) and 'data' in event['message']:
                data_b64 = event['message']['data']

        if data_b64:
            # try base64 decode first, but handle the case where data_b64 is already plain JSON
            try:
                pubsub_message = base64.b64decode(data_b64).decode('utf-8')
                transaction = json.loads(pubsub_message)
            except Exception:
                try:
                    transaction = json.loads(data_b64)
                except Exception:
                    raise
        else:
            # fallback: event may already be the transaction dict
            if isinstance(event, dict) and ('transaction_id' in event or 'amount' in event):
                transaction = event
            else:
                raise ValueError('No data found in event')
    except Exception as e:
        print(f"Error decoding Pub/Sub message: {e}; event shape: {type(event)}")
        return

    print(f"Received transaction: {transaction}")

    # Save all transactions to Firestore
    try:
        if firestore_client is None:
            # lazy import firestore
            global firestore
            if firestore is None:
                from google.cloud import firestore as _firestore
                firestore = _firestore
            firestore_client = firestore.Client(project=PROJECT_ID)
        transactions_col = firestore_client.collection('transactions')
        transaction_id = transaction.get('transaction_id')
        print(f"Transaction ID: {transaction_id}")
        if not transaction_id:
            print("Error: transaction_id is missing or empty. Cannot save transaction to Firestore.")
            return # Exit if no transaction_id
        doc = transactions_col.document(transaction_id)
        doc.set({
            **transaction,
            'timestamp': firestore.SERVER_TIMESTAMP
        })
        print("Transaction saved to Firestore")
    except Exception as e:
        print(f"Failed to save transaction to Firestore: {e}")

    # Build model instance from transaction to match Vertex AI schema
    model_instance = build_model_instance_from_transaction(transaction)
    # Optionally log the exact instance sent to the model (disabled by default).
    try:
        if os.environ.get('LOG_MODEL_INSTANCE', '').lower() in ('1', 'true', 'yes'):
            print("Model instance being sent to model:")
            # Print each key separately to avoid truncation issues in logging
            for k, v in model_instance.items():
                print(f"  {k}: {v}")
    except Exception:
        pass
    inference_source = None
    try:
        fraud_probability = get_fraud_probability(model_instance)
        inference_source = 'model'
        print(f"Predicted fraud probability: {fraud_probability}")
        prediction_error = None
    except Exception as e:
        prediction_error = str(e)
        fraud_probability = None
        print(f"Prediction failed: {prediction_error}")

        # Heuristic fallback: if transaction contains merchant_score and device_score, average them
        try:
            m = float(transaction.get('merchant_score')) if transaction.get('merchant_score') is not None else None
            d = float(transaction.get('device_score')) if transaction.get('device_score') is not None else None
            if m is not None and d is not None:
                fraud_probability = float((m + d) / 2.0)
                inference_source = 'heuristic_merchant_device_avg'
                prediction_error = None
                print(f"Heuristic fallback produced fraud_probability: {fraud_probability}")
        except Exception:
            pass


    # Create alert message only when appropriate and controlled by ALERT_THRESHOLD
    try:
        should_alert = (fraud_probability is not None and fraud_probability > ALERT_THRESHOLD)
        alert_message = {
            "transaction_id": transaction.get("transaction_id"),
            "amount": transaction.get("amount"),
            "user_id": transaction.get("user_id"),
            "fraud_probability": fraud_probability if fraud_probability is not None else -1,
            "message": (
                "Potential fraud detected!" if should_alert
                else ("Transaction deemed legitimate." if fraud_probability is not None else f"Prediction error: {prediction_error}")
            ),
            "prediction_error": prediction_error,
            "inference_source": inference_source
        }

        # Publish alert only when probability exceeds threshold
        if should_alert:
            print(f"Publishing fraud alert (threshold {ALERT_THRESHOLD}): {alert_message}")
            publisher.publish(alert_topic_path, json.dumps(alert_message).encode('utf-8'))

        # Save the result to Firestore so the dashboard can display status for every transaction.
        # Keep the existing behavior of publishing SMS/alerts unchanged.
        try:
            if firestore_client is None:
                firestore_client = firestore.Client(project=PROJECT_ID)
            alerts_col = firestore_client.collection('fraud_alerts')
            doc = alerts_col.document(alert_message.get('transaction_id'))
            # Always save a result document. Include an `is_alert` flag so callers
            # can distinguish true alerts from benign results.
            doc.set({
                'transaction_id': alert_message.get('transaction_id'),
                'amount': alert_message.get('amount'),
                'user_id': alert_message.get('user_id'),
                'fraud_probability': alert_message.get('fraud_probability'),
                'message': alert_message.get('message'),
                'prediction_error': alert_message.get('prediction_error'),
                'inference_source': alert_message.get('inference_source'),
                'is_alert': bool(should_alert),
                'timestamp': firestore.SERVER_TIMESTAMP
            })
            print("Alert/result saved to Firestore")
        except Exception as e:
            print(f"Failed to save alert/result to Firestore: {e}")

        # If this is an alert, attempt to send SMS (if configured)
        if should_alert:
            user_phone = transaction.get('user_phone') or os.environ.get('ALERT_PHONE_NUMBER')
            if user_phone:
                try:
                    sms_body = f"ALERT: Transaction {transaction.get('transaction_id')} suspected fraud (prob={fraud_probability:.2f})."
                    sms_sid = send_sms_via_twilio(user_phone, sms_body)
                    print(f"Sent SMS via Twilio, SID: {sms_sid}")
                except Exception as e:
                    print(f"Failed to send SMS via Twilio: {e}")
            else:
                print("Alert detected but no user phone number configured; skipping SMS send.")
        else:
            print("Transaction not above alert threshold; no alert published.")
    except Exception as e:
        print(f"Unexpected error while handling alert logic: {e}")

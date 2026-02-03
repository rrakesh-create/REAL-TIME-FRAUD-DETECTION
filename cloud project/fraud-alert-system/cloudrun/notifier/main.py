from fastapi import FastAPI, Request
import base64
import json
import os
from twilio.rest import Client
from google.cloud import firestore

app = FastAPI()
db = firestore.Client(project=os.environ.get('GCP_PROJECT') or os.environ.get('PROJECT_ID') or 'fraud-detection-475817')

TWILIO_ACCOUNT_SID = os.environ.get('TWILIO_ACCOUNT_SID')
TWILIO_AUTH_TOKEN = os.environ.get('TWILIO_AUTH_TOKEN')
TWILIO_FROM_NUMBER = os.environ.get('TWILIO_FROM_NUMBER')
RECIPIENT_PHONE_NUMBER = os.environ.get('RECIPIENT_PHONE_NUMBER')

client = None
if TWILIO_ACCOUNT_SID and TWILIO_AUTH_TOKEN:
    client = Client(TWILIO_ACCOUNT_SID, TWILIO_AUTH_TOKEN)


@app.post('/pubsub')
async def pubsub_push(request: Request):
    payload = await request.json()
    msg = payload.get('message') or payload
    data_b64 = msg.get('data') if isinstance(msg, dict) else None
    if not data_b64:
        return {"status": "no data"}
    data = base64.b64decode(data_b64).decode('utf-8')
    alert = json.loads(data)

    # Save to Firestore for dashboard
    try:
        tx_id = alert.get('transaction_id')
        if tx_id:
            db.collection('fraud_alerts').document(tx_id).set({**alert, 'timestamp': firestore.SERVER_TIMESTAMP})
    except Exception:
        pass

    # Send SMS if configured
    to_number = alert.get('user_phone') or RECIPIENT_PHONE_NUMBER
    if client and to_number and TWILIO_FROM_NUMBER:
        try:
            body = f"ALERT: Transaction {alert.get('transaction_id')} suspected fraud (prob={alert.get('fraud_probability')})"
            message = client.messages.create(body=body, from_=TWILIO_FROM_NUMBER, to=to_number)
            return {"status": "sent", "sid": message.sid}
        except Exception as e:
            return {"error": str(e)}

    return {"status": "noop"}

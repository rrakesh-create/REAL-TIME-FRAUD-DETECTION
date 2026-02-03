import base64
import os
import json
import functions_framework
from twilio.rest import Client

# Read Twilio credentials and numbers from environment (Secret Manager bindings)
TWILIO_ACCOUNT_SID = os.getenv("TWILIO_ACCOUNT_SID")
TWILIO_AUTH_TOKEN = os.getenv("TWILIO_AUTH_TOKEN")
# TWILIO_FROM_NUMBER secret should be bound to the function as TWILIO_FROM_NUMBER
TWILIO_PHONE_NUMBER = os.getenv("TWILIO_FROM_NUMBER")
# Recipient phone number secret is bound as RECIPIENT_PHONE_NUMBER
RECIPIENT_PHONE_NUMBER = os.getenv("RECIPIENT_PHONE_NUMBER")

client = None
if TWILIO_ACCOUNT_SID and TWILIO_AUTH_TOKEN:
    client = Client(TWILIO_ACCOUNT_SID, TWILIO_AUTH_TOKEN)

# Dry-run flag: when true, the function will not send SMS and will only log/store the message
NOTIFIER_DRY_RUN = os.getenv("NOTIFIER_DRY_RUN", "false").lower() in ("1", "true", "yes")
# Log diagnostic info about Twilio configuration (do not print secrets)
print(f"Notifier configuration: NOTIFIER_DRY_RUN={NOTIFIER_DRY_RUN}, TWILIO_CONFIGURED={bool(TWILIO_ACCOUNT_SID and TWILIO_AUTH_TOKEN and TWILIO_PHONE_NUMBER)}, RECIPIENT_CONFIGURED={bool(RECIPIENT_PHONE_NUMBER)}")

@functions_framework.cloud_event
def notifier(cloud_event):
    print("Received fraud alert.")
    print(f"Cloud Event Data: {cloud_event.data}")
    pubsub_message = cloud_event.data.get("message")
    if not pubsub_message:
        # If not a Pub/Sub message, try to parse directly
        try:
            payload = json.loads(cloud_event.data)
        except json.JSONDecodeError:
            print("Error: Could not decode cloud_event.data as JSON.")
            return "Error"
    else:
        decoded_data = base64.b64decode(pubsub_message["data"]).decode("utf-8")
        payload = json.loads(decoded_data)

    transaction_id = payload.get("transaction_id")
    amount = payload.get("amount")
    user_id = payload.get("user_id")
    # support either 'fraud_score' or 'fraud_probability' coming from different components
    fraud_score = payload.get("fraud_score")
    if fraud_score is None:
        fraud_score = payload.get("fraud_probability")
    # ensure we have a numeric value to format
    try:
        fraud_score = float(fraud_score) if fraud_score is not None else 0.0
    except Exception:
        fraud_score = 0.0

    message_body = (
        f"Fraud Alert for Transaction ID: {transaction_id}\n"
        f"User: {user_id}\n"
        f"Amount: {amount}\n"
        f"Fraud Score: {fraud_score:.2f}\n"
        "Action: Review and investigate immediately."
    )

    try:
        # choose recipient: payload may include 'user_phone' or use RECIPIENT_PHONE_NUMBER secret
        to_number = payload.get("user_phone") or RECIPIENT_PHONE_NUMBER
        # Allow payload to override dry-run for controlled tests from dashboard
        force_send = payload.get("force_send", False)
        if NOTIFIER_DRY_RUN and not force_send:
            print(f"DRY-RUN enabled: would send SMS to {to_number} from {TWILIO_PHONE_NUMBER}. Message body:\n{message_body}")
        elif not client:
            print("Twilio client not configured; skipping SMS send.")
        elif not to_number:
            print("No recipient phone number available; skipping SMS send.")
        else:
            message = client.messages.create(
                to=to_number,
                from_=TWILIO_PHONE_NUMBER,
                body=message_body
            )
            print(f"SMS sent successfully. Message SID: {message.sid}")
    except Exception as e:
        print(f"Error sending SMS: {e}")

    return "OK"
import os
import json
import time
import random
import uuid
import sys
import requests
import base64
from flask import Flask, request, jsonify
from google.cloud import pubsub_v1
from google.cloud import secretmanager

sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))
from functions.fraud_checker.main import fraud_checker

app = Flask(__name__) # Initialize Flask app

# --- Configuration --- 
# Replace with your actual Cloud Function URL
CLOUD_FUNCTION_URL = os.environ.get('CLOUD_FUNCTION_URL', 'https://us-central1-fraud-alert-system-475913.cloudfunctions.net/fraud_checker')
PROJECT_ID = "fraud-alert-system-475913"
PUBSUB_TOPIC_NAME = "transactions-topic"

# --- Pub/Sub Publisher (if sending directly to Pub/Sub) ---
publisher = pubsub_v1.PublisherClient()
pubsub_topic_path = publisher.topic_path(PROJECT_ID, PUBSUB_TOPIC_NAME)

# --- Transaction Simulation --- 
def generate_transaction():
    transaction_id = str(time.time_ns())
    user_id = f"user_{random.randint(1, 1000)}"
    # Amount in USD, similar scale to training data (raw dollars)
    amount = round(random.uniform(10.0, 1000.0), 2)
    currency = "USD"
    merchant_id = f"merchant_{random.randint(1, 50)}"
    # Provide an ISO8601 timestamp which the fraud_checker will convert to Time
    from datetime import datetime, timezone
    timestamp = datetime.now(timezone.utc).isoformat()
    is_fraudulent = random.choices([True, False], weights=[0.05, 0.95], k=1)[0] # 5% chance of fraud
    # Generate synthetic V1..V28 features (similar to anonymized PCA features in many fraud datasets).
    # Values sampled from a normal distribution centered at 0 with moderate variance.
    v_features = {f"V{i}": round(random.normalvariate(0, 1.5), 6) for i in range(1, 29)}

    # Also include merchant_score and device_score for heuristic fallback testing (range 0..1)
    merchant_score = round(random.uniform(0.0, 1.0), 3)
    device_score = round(random.uniform(0.0, 1.0), 3)

    transaction = {
        "transaction_id": transaction_id,
        "user_id": user_id,
        "amount": amount,
        "currency": currency,
        "merchant_id": merchant_id,
        "timestamp": timestamp,
        "is_fraudulent": is_fraudulent,
        "merchant_score": merchant_score,
        "device_score": device_score,
        **v_features
    }
    return transaction

def send_to_cloud_function(transaction):
    try:
        headers = {"Content-Type": "application/json"}
        response = requests.post(CLOUD_FUNCTION_URL, headers=headers, data=json.dumps(transaction))
        response.raise_for_status() # Raise HTTPError for bad responses (4xx or 5xx)
        print(f"Sent to Cloud Function: {transaction['transaction_id']} - Status: {response.status_code}")
    except requests.exceptions.RequestException as e:
        print(f"Error sending to Cloud Function: {e}")

def publish_to_pubsub(transaction):
    try:
        data = json.dumps(transaction).encode("utf-8")
        future = publisher.publish(pubsub_topic_path, data)
        message_id = future.result()
        print(f"Published to Pub/Sub: {transaction['transaction_id']} - Message ID: {message_id}")
    except Exception as e:
        print(f"Error publishing to Pub/Sub: {e}")

# --- Transaction Generation Endpoint ---
@app.route('/generate_transaction', methods=['POST'])
def trigger_generate_transaction():
    transaction_data = generate_transaction()
    print(f"Generated transaction: {transaction_data}")

    # For local debugging, directly call the fraud_checker function
    # In a real deployment, this would publish to Pub/Sub
    try:
        # Mimic Pub/Sub message structure
        event = {
            'data': base64.b64encode(json.dumps(transaction_data).encode('utf-8'))
        }
        # Context can be a mock object or None if not strictly used by fraud_checker
        fraud_checker(event, None)
        return jsonify({"message": "Transaction generated and processed by fraud checker."}), 200
    except Exception as e:
        print(f"Error calling fraud_checker locally: {e}")
        return jsonify({"message": f"Failed to process transaction: {e}"}), 500




# --- Main Execution Block ---
if __name__ == "__main__":
    # Choose your sending method (uncomment one):
    SEND_METHOD = "cloud_function"
    # SEND_METHOD = "pubsub"

    # Warnings are no longer needed as configuration will be managed via environment variables and direct assignment.

    # Run the Flask app
    app.run(host='0.0.0.0', port=8001)
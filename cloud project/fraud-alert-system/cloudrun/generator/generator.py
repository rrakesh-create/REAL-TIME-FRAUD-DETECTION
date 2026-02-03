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

app = Flask(__name__) # Initialize Flask app

# --- Configuration --- 
# CLOUD_FUNCTION_URL can be set to a target endpoint or left as default for local testing
CLOUD_FUNCTION_URL = os.environ.get('CLOUD_FUNCTION_URL', '')
PROJECT_ID = os.environ.get('GCP_PROJECT') or os.environ.get('PROJECT_ID') or 'fraud-detection-475817'
PUBSUB_TOPIC_NAME = os.environ.get('PUBSUB_TOPIC', 'transactions-topic')

# --- Pub/Sub Publisher (if sending directly to Pub/Sub) ---
publisher = pubsub_v1.PublisherClient()
pubsub_topic_path = publisher.topic_path(PROJECT_ID, PUBSUB_TOPIC_NAME)

# --- Transaction Simulation --- 
def generate_transaction():
    transaction_id = str(time.time_ns())
    user_id = f"user_{random.randint(1, 1000)}"
    amount = round(random.uniform(10.0, 1000.0), 2)
    currency = "USD"
    merchant_id = f"merchant_{random.randint(1, 50)}"
    from datetime import datetime, timezone
    timestamp = datetime.now(timezone.utc).isoformat()
    is_fraudulent = random.choices([True, False], weights=[0.05, 0.95], k=1)[0]
    v_features = {f"V{i}": round(random.normalvariate(0, 1.5), 6) for i in range(1, 29)}
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

def publish_to_pubsub(transaction):
    try:
        data = json.dumps(transaction).encode("utf-8")
        future = publisher.publish(pubsub_topic_path, data)
        message_id = future.result()
        print(f"Published to Pub/Sub: {transaction['transaction_id']} - Message ID: {message_id}")
    except Exception as e:
        print(f"Error publishing to Pub/Sub: {e}")

def send_to_cloud_function(transaction):
    if not CLOUD_FUNCTION_URL:
        print("CLOUD_FUNCTION_URL not set; skipping direct function POST")
        return
    try:
        headers = {"Content-Type": "application/json"}
        response = requests.post(CLOUD_FUNCTION_URL, headers=headers, data=json.dumps(transaction))
        response.raise_for_status()
        print(f"Sent to Cloud Function: {transaction['transaction_id']} - Status: {response.status_code}")
    except requests.exceptions.RequestException as e:
        print(f"Error sending to Cloud Function: {e}")

@app.route('/generate_transaction', methods=['POST'])
def trigger_generate_transaction():
    transaction_data = generate_transaction()
    print(f"Generated transaction: {transaction_data}")
    # Default to publishing to Pub/Sub in Cloud Run
    try:
        publish_to_pubsub(transaction_data)
        return jsonify({"message": "Transaction generated and published to Pub/Sub."}), 200
    except Exception as e:
        return jsonify({"message": f"Failed to publish transaction: {e}"}), 500

if __name__ == "__main__":
    app.run(host='0.0.0.0', port=int(os.environ.get('PORT', 8080)))

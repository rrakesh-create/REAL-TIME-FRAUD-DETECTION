import os
import uuid
import json
from google.cloud import pubsub_v1

# Ensure GOOGLE_APPLICATION_CREDENTIALS is set or modify the path below
if not os.environ.get('GOOGLE_APPLICATION_CREDENTIALS'):
    os.environ['GOOGLE_APPLICATION_CREDENTIALS'] = r'C:\Users\RAKESH\Downloads\fraud-alert-system-475913-69889d6decf4.json'

PROJECT_ID = os.environ.get('GCP_PROJECT') or os.environ.get('PROJECT_ID') or 'fraud-detection-475817'
TOPIC = 'fraud-alerts-topic'

publisher = pubsub_v1.PublisherClient()
topic_path = publisher.topic_path(PROJECT_ID, TOPIC)

payload = {
    "transaction_id": f"dash-pub-test-{uuid.uuid4().hex[:8]}",
    "fraud_probability": 0.95,
    "user_phone": os.environ.get('TEST_RECIPIENT_PHONE', '+15550001234'),
    "user_id": "dashboard-test",
    "amount": 250.0,
    "note": "Published by tools/publish_test_alert.py for notifier test",
}

data = json.dumps(payload).encode('utf-8')
print('Publishing payload:', payload)
future = publisher.publish(topic_path, data)
msg_id = future.result()
print('Published message id:', msg_id)
print('Topic:', topic_path)

import streamlit as st
import pandas as pd
import requests
import time
import json
import os
import uuid
import random
from datetime import datetime
from google.cloud import firestore
from google.cloud import pubsub_v1

PROJECT_ID = os.environ.get('GCP_PROJECT') or os.environ.get('PROJECT_ID') or 'fraud-detection-475817'
# Initialize Firestore client
db = firestore.Client(project=PROJECT_ID)
publisher = pubsub_v1.PublisherClient()
transactions_topic_path = publisher.topic_path(PROJECT_ID, "transactions-topic")
fraud_alerts_topic_path = publisher.topic_path(PROJECT_ID, "fraud-alerts-topic")

# --- Dashboard Configuration ---
st.set_page_config(
    page_title="Fraud Detection Dashboard",
    page_icon=":money_with_wings:",
    layout="wide",
    initial_sidebar_state="expanded",
)

st.title("Fraud Detection Dashboard :money_with_wings:")

# Auto-refresh interval
refresh_interval = st.sidebar.slider("Auto-refresh interval (seconds)", 5, 60, 10)


# --- Transaction Generation & Clear All ---
st.sidebar.header("Transaction Generator")

def publish_test_transaction_via_pubsub():
    # Create a synthetic transaction and publish to Pub/Sub
    transaction = {
        "transaction_id": f"dash-test-{uuid.uuid4().hex[:8]}",
        "amount": round(random.uniform(10.0, 1000.0), 2),
        "user_id": f"dash-user-{random.randint(1, 1000)}",
        "user_phone": os.environ.get('TEST_RECIPIENT_PHONE', ''),
        "merchant": f"dashboard-merchant-{random.randint(1, 50)}",
        "merchant_score": round(random.uniform(0, 1), 2),
        "device_score": round(random.uniform(0, 1), 2),
        "timestamp": datetime.utcnow().isoformat() + "Z"
    }
    data = json.dumps(transaction).encode('utf-8')
    future = publisher.publish(transactions_topic_path, data)
    msg_id = future.result(timeout=10)
    return msg_id, transaction

def clear_firestore_collection(collection_name):
    # Clear all docs in a Firestore collection
    try:
        docs = db.collection(collection_name).stream()
        for doc in docs:
            doc.reference.delete()
        return True, f"Cleared {collection_name} collection."
    except Exception as e:
        return False, str(e)

if st.sidebar.button("Clear All Transactions & Alerts"):
    ok1, msg1 = clear_firestore_collection('transactions')
    ok2, msg2 = clear_firestore_collection('fraud_alerts')
    if ok1 and ok2:
        st.sidebar.success("All transactions and fraud alerts cleared.")
    else:
        st.sidebar.error(f"Error clearing: {msg1 if not ok1 else ''} {msg2 if not ok2 else ''}")

def generate_and_publish_transaction():
    try:
        msg_id, tx = publish_test_transaction_via_pubsub()
        st.sidebar.success(f"Published and submitted transaction {tx['transaction_id']} (msg: {msg_id}) for fraud check.")
    except Exception as e:
        st.sidebar.error(f"Failed to publish transaction: {e}")

if st.sidebar.button("Generate & Submit Transaction"):
    generate_and_publish_transaction()


if st.sidebar.button("Insert fake fraud alert (Firestore only)"):
    # Useful to test dashboard UI without triggering SMS
    alert_doc = {
        "transaction_id": f"fake-alert-{uuid.uuid4().hex[:6]}",
        "amount": 199.99,
        "user_id": "fake-user",
        "fraud_probability": 0.92,
        "message": "Simulated alert (dashboard)",
        "timestamp": firestore.SERVER_TIMESTAMP,
    }
    db.collection('fraud_alerts').document(alert_doc['transaction_id']).set(alert_doc)
    st.sidebar.success(f"Inserted fake alert {alert_doc['transaction_id']}")


# --- Manual Alert Publisher (for testing / demo) ---
st.sidebar.header("Publish Fraud Alert")
with st.sidebar.form(key="alert_form"):
    alert_tx_id = st.text_input("Transaction ID", value=f"dash-alert-{uuid.uuid4().hex[:8]}")
    alert_user = st.text_input("User ID", value="dashboard-user")
    alert_phone = st.text_input("User phone (optional, overrides default)", value=os.environ.get('TEST_RECIPIENT_PHONE', ''))
    alert_amount = st.number_input("Amount", value=100.00, step=1.0)
    alert_score = st.slider("Fraud probability", 0.0, 1.0, 0.9)
    send_real = st.checkbox("Send real SMS (force)", value=False, help="If checked the notifier will attempt to send a real SMS; requires notifier access to Twilio secrets.")
    submit_alert = st.form_submit_button("Publish Fraud Alert (Pub/Sub)")

    if submit_alert:
        alert_payload = {
            "alert_id": alert_tx_id,
            "transaction_id": alert_tx_id,
            "user_id": alert_user,
            "user_phone": alert_phone if alert_phone else None,
            "amount": alert_amount,
            "fraud_probability": float(alert_score),
            "note": "Published from dashboard",
        }
        # include a flag the notifier can use to bypass dry-run
        if send_real:
            alert_payload["force_send"] = True

        try:
            data = json.dumps(alert_payload).encode('utf-8')
            future = publisher.publish(fraud_alerts_topic_path, data)
            msg_id = future.result(timeout=10)
            st.sidebar.success(f"Published fraud alert {alert_tx_id} (msg: {msg_id})")
        except Exception as e:
            st.sidebar.error(f"Failed to publish fraud alert: {e}")

# --- Data Fetching ---
@st.cache_data(ttl=1) # Cache data for the refresh interval
def get_fraud_alerts():
    alerts_ref = db.collection('fraud_alerts').order_by('timestamp', direction=firestore.Query.DESCENDING).limit(100)
    alerts = [doc.to_dict() for doc in alerts_ref.stream()]
    return pd.DataFrame(alerts) if alerts else pd.DataFrame()

@st.cache_data(ttl=1) # Cache data for the refresh interval
def get_all_transactions():
    transactions_ref = db.collection('transactions').order_by('timestamp', direction=firestore.Query.DESCENDING).limit(100)
    transactions = [doc.to_dict() for doc in transactions_ref.stream()]
    return pd.DataFrame(transactions) if transactions else pd.DataFrame()

# --- Dashboard Layout ---

# Metrics
st.subheader("Overview")

# Create two columns for metrics
metrics_col1, metrics_col2, metrics_col3 = st.columns(3)

# Fetch data
fraud_alerts_df = get_fraud_alerts()
all_transactions_df = get_all_transactions()

with metrics_col1:
    st.metric(label="Total Fraud Alerts", value=len(fraud_alerts_df))

with metrics_col2:
    if not fraud_alerts_df.empty:
        high_fraud_alerts = fraud_alerts_df[fraud_alerts_df['fraud_probability'] > 0.5]
        st.metric(label="High Fraud Probability Alerts", value=len(high_fraud_alerts))
    else:
        st.metric(label="High Fraud Probability Alerts", value=0)

with metrics_col3:
    avg_fraud_score = fraud_alerts_df['fraud_probability'].mean() if not fraud_alerts_df.empty else 0
    st.metric(label="Average Fraud Score", value=f"{avg_fraud_score:.2f}")


st.subheader("Recent Fraud Alerts")

# --- Enhanced Fraud Alerts Table: Color and Actions ---
if not fraud_alerts_df.empty:
    alert_df = fraud_alerts_df.copy()
    def highlight_alert(row):
        color = ''
        if row.get('fraud_probability', 0) > 0.8:
            color = 'background-color: #ffcccc; color: red; font-weight: bold;'
        elif row.get('fraud_probability', 0) > 0.5:
            color = 'background-color: #fff2cc; color: orange;'
        return [color for _ in row]
    # show prediction_error and inference_source columns when available
    display_alert_df = alert_df.copy()
    if 'prediction_error' in display_alert_df.columns:
        display_alert_df['prediction_error'] = display_alert_df['prediction_error'].fillna('')
    if 'inference_source' in display_alert_df.columns:
        display_alert_df['inference_source'] = display_alert_df['inference_source'].fillna('')

    st.dataframe(
        display_alert_df.style.apply(highlight_alert, axis=1),
        width='stretch'
    )
else:
    st.info("No fraud alerts to display yet.")


st.subheader("All Transactions")

# --- Enhanced Transaction Table: Show Fraud Status ---
if not all_transactions_df.empty:
    tx_df = all_transactions_df.copy()
    # Add fraud status by joining with fraud_alerts_df on transaction_id
    if not fraud_alerts_df.empty and 'transaction_id' in tx_df.columns and 'transaction_id' in fraud_alerts_df.columns:
        tx_df = tx_df.merge(
            fraud_alerts_df[['transaction_id', 'fraud_probability']],
            on='transaction_id', how='left', suffixes=('', '_fraud')
        )
        def map_status(x):
            if pd.notnull(x):
                try:
                    xv = float(x)
                except Exception:
                    return 'Error'
                if xv < 0:
                    return 'Error'
                if xv > 0.5:
                    return 'FRAUD'
                return 'Normal'
            return 'Unchecked'

        tx_df['fraud_status'] = tx_df['fraud_probability'].apply(map_status)
    else:
        tx_df['fraud_status'] = 'Unchecked'

    # Color fraud status for display
    def highlight_fraud(row):
        color = ''
        if row['fraud_status'] == 'FRAUD':
            color = 'background-color: #ffcccc; color: red; font-weight: bold;'
        elif row['fraud_status'] == 'Normal':
            color = 'background-color: #e6ffe6; color: green;'
        return [color if c == 'fraud_status' else '' for c in row.index]

    st.dataframe(
        tx_df.style.apply(highlight_fraud, axis=1),
        width='stretch'
    )

    # Real-time status indicator
    unchecked_count = (tx_df['fraud_status'] == 'Unchecked').sum()
    if unchecked_count > 0:
        st.warning(f"{unchecked_count} transaction(s) are still being checked. If this persists for more than a few seconds, check Cloud Function logs and Firestore for issues.")
        st.info("Try increasing the auto-refresh interval or manually refresh the dashboard. Real-time fraud detection should complete within a few seconds.")
else:
    st.info("No transactions to display yet.")


# Placeholder for a chart (e.g., fraud probability over tim
st.subheader("Fraud Probability Trend")
# Render chart only when timestamped data available; sanitize timestamps first
if not fraud_alerts_df.empty and 'timestamp' in fraud_alerts_df.columns:
    try:
        fraud_alerts_df['timestamp'] = pd.to_datetime(fraud_alerts_df['timestamp'], errors='coerce')
    except Exception:
        pass

if not fraud_alerts_df.empty and 'timestamp' in fraud_alerts_df.columns and fraud_alerts_df['timestamp'].notna().any():
    chart_df = fraud_alerts_df.set_index('timestamp').sort_index()
    st.line_chart(chart_df['fraud_probability'])
else:
    st.info("Not enough timestamped alert data to render trend chart.")

# Auto-refresh logic: simple timer that reruns the script when the interval passes
if 'last_refresh' not in st.session_state:
    st.session_state.last_refresh = time.time()

now_ts = time.time()
try:
    interval = float(refresh_interval)
except Exception:
    interval = 10.0

if now_ts - st.session_state.last_refresh > interval:
    st.session_state.last_refresh = now_ts
    # Use st.rerun if available (modern Streamlit)
    try:
        rerun = getattr(st, "rerun", None)
        if callable(rerun):
            rerun()
        else:
            # Fallback for slightly older versions
            rerun_exp = getattr(st, "experimental_rerun", None)
            if callable(rerun_exp):
                rerun_exp()
    except Exception:
        # If Streamlit doesn't support rerun, continue without crashing
        pass


# -- Notification panel / actions --
st.sidebar.header("Notifications")

def publish_fraud_alert_force_send(alert):
    """Publish an existing alert payload to the fraud-alerts topic with force_send=True."""
    payload = dict(alert)
    payload['force_send'] = True
    payload.setdefault('alert_id', payload.get('transaction_id', f"dash-alert-{uuid.uuid4().hex[:8]}"))
    payload.setdefault('transaction_id', payload.get('transaction_id'))
    try:
        data = json.dumps(payload).encode('utf-8')
        future = publisher.publish(fraud_alerts_topic_path, data)
        msg_id = future.result(timeout=10)
        return True, msg_id
    except Exception as e:
        return False, str(e)


st.sidebar.write("Recent Alerts")

if not fraud_alerts_df.empty:
    top_alerts = fraud_alerts_df.head(10).to_dict(orient='records')
    for a in top_alerts:
        container = st.sidebar.container()
        with container:
            st.markdown(f"<b>{a.get('transaction_id','-')}</b> — <span style='color:red;font-weight:bold'>{a.get('fraud_probability', 0):.2f}</span>", unsafe_allow_html=True)
            st.write(f"{a.get('message','')}")
            if st.button(f"Force Send SMS", key=f"force_{a.get('transaction_id','')}"):
                ok, info = publish_fraud_alert_force_send(a)
                if ok:
                    st.sidebar.success(f"Published force-send (msg {info})")
                else:
                    st.sidebar.error(f"Failed to publish force-send: {info}")
else:
    st.sidebar.info("No recent alerts")

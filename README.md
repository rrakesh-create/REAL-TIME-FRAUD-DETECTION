# Real-Time Fraud Alert System

A complete real-time fraud detection pipeline that identifies suspicious transactions as they happen, notifies users, and provides administrators with a real-time monitoring dashboard.

## 🏗️ Architecture & Core Components

This project is built around Google Cloud Platform (GCP) services and is composed of the following pieces:

1. **Pub/Sub (Message Queues):** Acts as the central event bus. Transactions are published to the `transactions-topic`. If a transaction is flagged as fraud, an alert is published to the `fraud-alerts-topic`.
2. **Fraud Checker Backend (Cloud Function):** The core intelligence located in `cloud project/fraud-alert-system/functions/fraud_checker/main.py`. It calculates a **Fraud Probability** score based on transaction details (using a machine learning model or heuristic fallback). If the score exceeds the safety threshold, it fires an alert.
3. **Firestore (Database):** A NoSQL database that persists all transaction records and generated fraud alerts for fast, real-time dashboard querying.
4. **Twilio SMS Notifier:** For high-probability fraud alerts, the system integrates with Twilio to instantly text the affected user.
5. **Streamlit Monitoring Dashboard:** A real-time web interface (`app.py`) for administrators to view live transactions, review fraud alerts, and generate test transactions.

## 🚀 Quick Local Setup

1. **Install Dependencies:** Ensure you have a Python virtual environment set up and dependencies installed:
   ```powershell
   python -m venv .venv
   .\.venv\Scripts\activate
   pip install -r requirements.txt
   ```

2. **Configure Environment Variables:**
   Copy the example environment file to create your own local secrets file:
   ```powershell
   Copy-Item .env.example -Destination .env
   ```
   Open `.env` and fill in your Twilio credentials (if you intend to test SMS capabilities locally).

3. **Run the Dashboard:**
   Start the Streamlit dashboard by running:
   ```powershell
   & ".venv/Scripts/python.exe" -m streamlit run "cloud project/fraud-alert-system/cloudrun/dashboard/app.py" --server.port 8501 --server.address 127.0.0.1
   ```
   *The dashboard will be available at `http://127.0.0.1:8501`*

## 🧪 Local Testing & Simulation Scripts

To test the backend without having to deploy it to Google Cloud every time, you can use the provided local helper scripts:

* `run_local_fraud_check.py`: Creates a synthetic transaction and runs it directly through the local fraud checker function.
* `run_high_alert_dryrun.py`: Simulates a highly suspicious transaction (amount: $9999) to force an alert and tests the Twilio SMS payload generation.
* `process_transactions_locally.py`: A bulk fallback processor that scans Firestore for recent unchecked transactions and processes them locally to update the dashboard.

## 🔐 Security Note
Before publishing to GitHub, always ensure that `.env` is ignored and that no hardcoded Google Cloud service accounts or Twilio tokens are checked into version control. (The `.gitignore` in this repository is already configured correctly for this). Large model binaries (`*.pkl`) should be managed via Git LFS.

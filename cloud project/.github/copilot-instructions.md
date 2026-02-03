# Copilot Instructions for Fraud Alert System

## Overview
This project is a cloud-native fraud detection and alerting system built for GCP. It features:
- **Transaction generator** (`transaction-generator/`): Simulates and sends transactions to the pipeline.
- **Fraud checker Cloud Function** (`functions/fraud_checker/`): Receives transactions, calls a Vertex AI model, writes results to Firestore, and publishes alerts to Pub/Sub.
- **Notifier Cloud Function** (`functions/notifier/`): Listens for fraud alerts and sends SMS via Twilio.
- **Dashboard** (`dashboard/`): Streamlit app for monitoring transactions and fraud alerts from Firestore.
- **Model training** (`fraud_model_train.py`, `Dockerfile.train`): Trains and saves a fraud detection model.

## Key Workflows
- **Deploying to GCP**: Use `deploy/deploy.ps1` and `deploy/setup.ps1` to provision resources, set secrets, and deploy functions. See `deploy/README.md` for details.
- **Local dashboard**: Activate a Python venv, install `dashboard/requirements.txt`, set `GOOGLE_APPLICATION_CREDENTIALS`, then run `streamlit run dashboard/app.py`.
- **Transaction simulation**: Run `transaction-generator/generator.py` (Flask app) to POST transactions or publish to Pub/Sub.
- **Model training**: Build/train with `fraud_model_train.py` or `Dockerfile.train`.

## Project Conventions
- **Environment variables**: All GCP/Twilio config is via env vars or Secret Manager. See `functions/fraud_checker/main.py` for required vars.
- **Firestore collections**: `transactions` and `fraud_alerts`.
- **Pub/Sub topics**: `transactions-topic` (input), `fraud-alerts-topic` (alerts).
- **Vertex AI**: Model endpoint is called from `fraud_checker` function.
- **Secrets**: Prefer GCP Secret Manager for Twilio credentials in production.

## Patterns & Integration
- **Functions communicate via Pub/Sub and Firestore**. Notifier expects alert messages in a specific JSON format.
- **All code is Python 3.9+**. Use `requirements.txt` in each component for dependencies.
- **Cloud Functions**: Use `functions_framework.cloud_event` for entrypoints.
- **Testing**: No central test runner; test each component in isolation.

## Examples
- To deploy: `cd deploy; ./setup.ps1; ./deploy.ps1`
- To run dashboard: `python -m venv .venv; .venv\Scripts\Activate.ps1; pip install -r dashboard/requirements.txt; $env:GOOGLE_APPLICATION_CREDENTIALS='path\to\creds.json'; streamlit run dashboard/app.py`
- To generate a transaction: POST to `http://localhost:8001/generate_transaction` (see dashboard sidebar)

## References
- See `deploy/README.md` for full deployment and environment setup details.
- Key files: `functions/fraud_checker/main.py`, `functions/notifier/main.py`, `dashboard/app.py`, `transaction-generator/generator.py`, `fraud_model_train.py`, `Dockerfile.train`

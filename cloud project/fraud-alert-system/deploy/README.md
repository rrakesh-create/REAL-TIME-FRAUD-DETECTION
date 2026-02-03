Deployment steps for Fraud Alert System (GCP)

Prerequisites:
- Google Cloud SDK installed and authenticated (gcloud auth login)
- Billing enabled for project `fraud-detection-475817`
- Vertex AI model deployed and an endpoint created
- Twilio account with SID, auth token, and a verified phone number

Quick deploy (PowerShell):
1. Edit `deploy.ps1` and set `YOUR_VERTEX_AI_ENDPOINT_ID`, Twilio credentials, and phone numbers.
2. Run in PowerShell:
   ./deploy.ps1

What the script does:
- Creates Pub/Sub topics: `transactions-topic` and `fraud-alerts-topic`
- Deploys the Cloud Function `fraud-checker` triggered by the `transactions-topic`
- Sets environment variables required by the function: Vertex endpoint id and Twilio credentials

Environment variables used by the Cloud Function:
- VERTEX_AI_ENDPOINT_ID: endpoint resource name of your Vertex AI endpoint
- VERTEX_AI_PROJECT: GCP project id (defaults to `fraud-detection-475817`)
- VERTEX_AI_LOCATION: Vertex AI region (e.g. us-central1)
- ALERT_TOPIC_NAME: Pub/Sub topic to publish alerts
- TWILIO_ACCOUNT_SID, TWILIO_AUTH_TOKEN, TWILIO_FROM_NUMBER: Twilio credentials
- ALERT_PHONE_NUMBER: fallback phone number to receive SMS alerts

Notes:
- For production, store Twilio secrets in Secret Manager and reference them via `--set-secrets` when deploying functions.
- You must enable the Vertex AI API and Cloud Functions API in the GCP console.
- Ensure the service account attaching to Cloud Functions has permission to call Vertex AI and publish to Pub/Sub.

Linking this repo to your GCP account and preparing the project
1. Make sure you've authenticated with gcloud and selected the correct account:
   - In PowerShell run: `gcloud auth login` and choose your Google account.
   - Confirm project is set:
     `gcloud config set project fraud-detection-475817`

2. Run the setup script to enable APIs, create topics, create a service account, and optionally store Twilio secrets in Secret Manager:
   ```pwsh
   cd deploy
   .\setup.ps1 -Project "fraud-detection-475817" -CreateSecrets
   ```

3. If you used `-CreateSecrets`, the setup script will prompt you for Twilio values and store them as secrets named:
   - `TWILIO_ACCOUNT_SID`
   - `TWILIO_AUTH_TOKEN`
   - `TWILIO_FROM_NUMBER`

4. Edit `deploy.ps1` to set `VERTEX_AI_ENDPOINT_ID` (and optionally Twilio variables if you didn't store them in Secret Manager). Then run `deploy.ps1` to deploy the Cloud Function.

Notes on permissions: the setup script creates a service account `fraud-function-sa@<project>.iam.gserviceaccount.com` and grants it roles to publish to Pub/Sub, call Vertex AI, and access Secret Manager. You may need to adjust roles depending on your org policy.

Dashboard (local and Cloud Run)
- Local: run the Streamlit dashboard which reads alerts from Firestore (the Cloud Function writes alerts to Firestore).
  1. Install dashboard deps:
     ```pwsh
     python -m venv .venv
     .\.venv\Scripts\Activate.ps1
     pip install -r ..\dashboard\requirements.txt
     ```
  2. Set application credentials (if running locally):
     ```pwsh
     $env:GOOGLE_APPLICATION_CREDENTIALS = 'path\to\your\service-account.json'
     streamlit run ..\dashboard\app.py
     ```

- Cloud Run: package the dashboard into a small container and deploy to Cloud Run (this requires adjusting credentials to use Workload Identity or another secure method). If you'd like, I can add a Dockerfile and Cloud Run deploy script.

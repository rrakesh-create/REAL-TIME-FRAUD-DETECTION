# Fraud alert system (cleaned local)

This repository contains a small demo fraud detection project with a Streamlit dashboard, a fraud-checker function, and notifier code for sending SMS via Twilio.

Before publishing to GitHub:

- Remove or keep secrets out of the repo. Use `.env` for local development (and add it to `.gitignore`), and use Secret Manager or GitHub Secrets for deployment.
- Large model binaries (`*.pkl`) should use Git LFS or an external artifact store (GCS).

Quick local setup

1. Create and activate a Python virtual environment and install dependencies.
2. Copy `.env.example` to `.env` and populate values for local testing.
3. Start the dashboard:

```powershell
& ".venv/Scripts/python.exe" -m streamlit run "cloud project/fraud-alert-system/cloudrun/dashboard/app.py" --server.port 8501 --server.address 127.0.0.1
```

Contact

If you need me to create a GitHub repo and push, tell me and I will prepare the git commands (I cannot push to your GitHub without credentials or the gh CLI).

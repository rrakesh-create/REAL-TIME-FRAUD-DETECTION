<#
Project setup script for GCP (PowerShell)
This script will:
 - ensure the gcloud project is set
 - enable required APIs
 - create Pub/Sub topics
 - create a service account for Cloud Functions and grant roles
 - optionally create Secret Manager secrets for Twilio credentials

Run with: .\setup.ps1
#>

param(
    [string]$Project = "fraud-detection-475817",
    [string]$Region = "us-central1",
    [string]$PubSubTopic = "transactions-topic",
    [string]$AlertTopic = "fraud-alerts-topic",
    [string]$ServiceAccountId = "fraud-function-sa",
    [switch]$CreateSecrets
)

Write-Host "Setting gcloud project to $Project"
gcloud config set project $Project

$apis = @(
    'cloudfunctions.googleapis.com',
    'pubsub.googleapis.com',
    'aiplatform.googleapis.com',
    'secretmanager.googleapis.com',
    'firestore.googleapis.com'
)

foreach ($api in $apis) {
    Write-Host "Enabling API: $api"
    gcloud services enable $api --project=$Project
}

Write-Host "Creating Pub/Sub topics if they don't exist"
# create topics if not exist
try { gcloud pubsub topics create $PubSubTopic --project=$Project --quiet } catch { Write-Host "Topic $PubSubTopic may already exist" }
try { gcloud pubsub topics create $AlertTopic --project=$Project --quiet } catch { Write-Host "Topic $AlertTopic may already exist" }

# Create service account
$saEmail = "$ServiceAccountId@$Project.iam.gserviceaccount.com"
Write-Host "Creating service account: $saEmail"
try { gcloud iam service-accounts create $ServiceAccountId --display-name="Fraud Function Service Account" --project=$Project --quiet } catch { Write-Host "Service account may already exist" }

# Assign roles required: Cloud Functions invoker/publisher to Pub/Sub; Vertex AI client; Secret Manager access
$roles = @(
    'roles/pubsub.publisher',
    'roles/aiplatform.user',
    'roles/secretmanager.secretAccessor',
    'roles/logging.logWriter'
)

# Add Firestore writer role so the function can write alerts
$roles += 'roles/datastore.user'

foreach ($role in $roles) {
    Write-Host "Granting role $role to $saEmail"
    gcloud projects add-iam-policy-binding $Project --member="serviceAccount:$saEmail" --role=$role --quiet
}

if ($CreateSecrets) {
    Write-Host "Creating Secret Manager secrets for TWILIO_* (you will be prompted to enter values)"
    $sid = Read-Host -Prompt "Enter TWILIO_ACCOUNT_SID (or press Enter to skip)"
    if ($sid) { gcloud secrets create TWILIO_ACCOUNT_SID --replication-policy="automatic" --project=$Project --quiet; echo $sid | gcloud secrets versions add TWILIO_ACCOUNT_SID --data-file=- --project=$Project --quiet }
    $token = Read-Host -Prompt "Enter TWILIO_AUTH_TOKEN (or press Enter to skip)"
    if ($token) { gcloud secrets create TWILIO_AUTH_TOKEN --replication-policy="automatic" --project=$Project --quiet; echo $token | gcloud secrets versions add TWILIO_AUTH_TOKEN --data-file=- --project=$Project --quiet }
    $from = Read-Host -Prompt "Enter TWILIO_FROM_NUMBER (or press Enter to skip)"
    if ($from) { gcloud secrets create TWILIO_FROM_NUMBER --replication-policy="automatic" --project=$Project --quiet; echo $from | gcloud secrets versions add TWILIO_FROM_NUMBER --data-file=- --project=$Project --quiet }

    Write-Host "Granting Secret Accessor role to service account"
    gcloud projects add-iam-policy-binding $Project --member="serviceAccount:$saEmail" --role="roles/secretmanager.secretAccessor" --quiet
}

Write-Host "Setup complete. Next: edit deploy.ps1 to set VERTEX_AI_ENDPOINT_ID and any Twilio values, then run deploy.ps1 to deploy the Cloud Function."
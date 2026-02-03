# Deployment script for Windows PowerShell
# Adjust variables below as needed. Requires gcloud and Google Cloud SDK authenticated.

$Project = "fraud-detection-475817"
$Region = "us-central1"
$PubSubTopic = "transactions-topic"
$AlertTopic = "fraud-alerts-topic"
$FunctionName = "notifier"
$FunctionSource = "$PSScriptRoot\..\functions\notifier"
$TriggerTopic = $AlertTopic
$Runtime = "python39"
$VertexEndpointId = "projects/182036847247/locations/us-central1/endpoints/9059913140711456768"
$TwilioAccountSid = "YOUR_TWILIO_SID"
$TwilioAuthToken = "YOUR_TWILIO_AUTH_TOKEN"
$TwilioFromNumber = "+15550000000"
$AlertPhoneNumber = "+15550000000" # fallback destination for alerts
$UseSecrets = $true # set to $true to deploy using Secret Manager secrets (recommended)

# Set project
gcloud config set project $Project

# Create Pub/Sub topics
gcloud pubsub topics create $PubSubTopic --project=$Project
gcloud pubsub topics create $AlertTopic --project=$Project

# Deploy Cloud Function (Pub/Sub trigger)
# Note: Adjust runtime to a supported Python runtime in your environment.

# Build environment or secret bindings
if ($UseSecrets) {
    Write-Host "Deploying Cloud Function using Secret Manager secrets (recommended). Ensure secrets exist in Secret Manager."
    $secretBindings = @()
    # Bind function env vars to secrets stored in Secret Manager in the same project
    $secretBindings += "TWILIO_ACCOUNT_SID=projects/$Project/secrets/TWILIO_ACCOUNT_SID:latest"
    $secretBindings += "TWILIO_AUTH_TOKEN=projects/$Project/secrets/TWILIO_AUTH_TOKEN:latest"
    $secretBindings += "TWILIO_FROM_NUMBER=projects/$Project/secrets/TWILIO_FROM_NUMBER:latest"
    $secretBindings += "RECIPIENT_PHONE_NUMBER=projects/$Project/secrets/RECIPIENT_PHONE_NUMBER_SECRET:latest"

    $SecretsString = $secretBindings -join ","

    gcloud functions deploy $FunctionName `
      --region=$Region `
      --entry-point=notifier `
      --runtime=python312 `
      --memory=512MB `
      --trigger-topic=$AlertTopic `
      --set-secrets=$SecretsString `
      --project=$Project `
      --source=$FunctionSource `
      --quiet

    # Deploy fraud_checker Cloud Function
    gcloud functions deploy fraud_checker `
      --region=$Region `
      --entry-point=fraud_checker `
      --runtime=python312 `
      --memory=1024MB `
      --timeout=540s `
      --trigger-topic=$PubSubTopic `
      --set-env-vars=VERTEX_AI_ENDPOINT_ID=$VertexEndpointId,VERTEX_AI_PROJECT=$Project,VERTEX_AI_LOCATION=$Region,ALERT_TOPIC_NAME=$AlertTopic `
      --project=$Project `
      --source="$PSScriptRoot\..\functions\fraud_checker" `
      --quiet
} else {
    $EnvVars = @{
        VERTEX_AI_ENDPOINT_ID = $VertexEndpointId;
        VERTEX_AI_PROJECT = $Project;
        VERTEX_AI_LOCATION = $Region;
        ALERT_TOPIC_NAME = $AlertTopic;
        TWILIO_ACCOUNT_SID = $TwilioAccountSid;
        TWILIO_AUTH_TOKEN = $TwilioAuthToken;
        TWILIO_FROM_NUMBER = $TwilioFromNumber;
        ALERT_PHONE_NUMBER = $AlertPhoneNumber;
    }

    $EnvString = $EnvVars.GetEnumerator() | ForEach-Object { "$($_.Key)=$($_.Value)" } -join ","

    gcloud functions deploy $FunctionName `
      --region=$Region `
      --entry-point=fraud_checker `
      --runtime=$Runtime `
      --memory=1024MB `
      --timeout=540s `
      --trigger-topic=$PubSubTopic `
      --set-env-vars=$EnvString `
      --project=$Project `
      --quiet
}

Write-Host "Deployment finished. Check Cloud Console for function logs and Pub/Sub messages."
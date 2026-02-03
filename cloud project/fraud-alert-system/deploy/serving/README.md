This folder contains a minimal serving container for the trained scikit-learn model `models/fraud_model.pkl`.

Steps to build, push, register the Model in Vertex AI, and deploy to an Endpoint.

Replace variables before running the commands.

1) Upload model artifact to GCS (optional, but useful for tracking):

```powershell
$PROJECT = "<YOUR_PROJECT>"
$REGION = "us-central1"
$BUCKET = "<YOUR_GCS_BUCKET_NAME>"
# create bucket if needed
gsutil mb -p $PROJECT -l $REGION gs://$BUCKET
# upload the model artifact
gsutil cp ..\models\fraud_model.pkl gs://$BUCKET/models/fraud_model.pkl
```

2) Build and push container (using Artifact Registry):

```powershell
$PROJECT = "<YOUR_PROJECT>"
$REGION = "us-central1"
$REPO = "vertex-serving-repo"
$IMAGE = "fraud-model-serving"
$TAG = "v1"
$IMAGE_URI = "$REGION-docker.pkg.dev/$PROJECT/$REPO/$IMAGE:$TAG"

# Create an Artifact Registry repo (if not exists)
gcloud artifacts repositories create $REPO --repository-format=docker --location=$REGION --description="Container repo for Vertex serving" --project=$PROJECT

# Configure docker auth for gcloud
gcloud auth configure-docker $REGION-docker.pkg.dev --quiet

# Build and push
docker build -t $IMAGE_URI .
docker push $IMAGE_URI
```

3) Register the container as a Vertex AI Model and deploy to an Endpoint

```powershell
$MODEL_DISPLAY_NAME = "fraud-model"
$IMAGE_URI = "<YOUR_IMAGE_URI>" # e.g. us-central1-docker.pkg.dev/<PROJECT>/<REPO>/fraud-model-serving:v1

# Create a Model resource pointing to the container image
gcloud ai models upload \
  --project=$PROJECT \
  --region=$REGION \
  --display-name=$MODEL_DISPLAY_NAME \
  --container-image-uri=$IMAGE_URI

# Note: the upload command prints a MODEL resource name like "projects/<proj>/locations/<region>/models/<model-id>"

# Create an endpoint
$ENDPOINT_DISPLAY_NAME = "fraud-model-endpoint"
gcloud ai endpoints create --project=$PROJECT --region=$REGION --display-name=$ENDPOINT_DISPLAY_NAME

# Deploy model to endpoint (adjust machine type)
$ENDPOINT_ID = "<ENDPOINT_ID_FROM_CREATE>"
$MODEL_ID = "<MODEL_ID_FROM_UPLOAD>"

gcloud ai endpoints deploy-model $ENDPOINT_ID \
  --project=$PROJECT \
  --region=$REGION \
  --model=$MODEL_ID \
  --display-name="fraud-model-deployment" \
  --machine-type="n1-standard-4" \
  --min-replica-count=1 \
  --max-replica-count=1

# The deploy command returns the endpoint details. Copy the endpoint resource name and set it in deploy/deploy.ps1 VERTEX_AI_ENDPOINT_ID.
```

4) Test the endpoint (example using curl)

```powershell
$ENDPOINT = "projects/<proj>/locations/<region>/endpoints/<endpoint>
# Example payload
$payload = '{"instances": [{"amount": 100.0, "age": 30, "merchant_score": 0.5}]}'

# Using gcloud to get an access token
$TOKEN = (gcloud auth print-access-token)
curl -X POST -H "Authorization: Bearer $TOKEN" -H "Content-Type: application/json" -d $payload "https://us-central1-aiplatform.googleapis.com/v1/$ENDPOINT:predict"
```

Notes
- This repo includes `fraud-alert-system/models/fraud_model.pkl` (already present).
- If you prefer not to build a container, you can upload the artifact to GCS and create a Model using a prebuilt container. The custom container gives full control and is straightforward for scikit-learn pickles.
- Make sure the service account you use has Artifact Registry Writer permissions and Vertex AI Model/Endpoint permissions.

from fastapi import FastAPI, HTTPException, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from pydantic import BaseModel
import joblib
import os
from typing import Any, List

MODEL_PATH = os.environ.get("MODEL_PATH", "./models/fraud_model.pkl")

app = FastAPI(title="Fraud Model Serving")


class PredictRequest(BaseModel):
    amount: float
    age: int
    merchant_score: float


# Load model at startup
try:
    model = joblib.load(MODEL_PATH)
except Exception as e:
    model = None
    load_error = str(e)
else:
    load_error = None


@app.get("/health")
def health():
    return {"ready": model is not None, "error": load_error}


def _predict_from_features(features: List[float]) -> float:
    try:
        if hasattr(model, "predict_proba"):
            prob = float(model.predict_proba([features])[0][1])
        else:
            prob = float(model.predict([features])[0])
        return prob
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@app.post("/predict")
def predict(req: PredictRequest):
    if model is None:
        raise HTTPException(status_code=500, detail={"error": load_error})

    features = [req.amount, req.age, req.merchant_score]
    prob = _predict_from_features(features)

    return {"fraud_probability": prob}


# Add CORS middleware so Vertex's preflight/OPTIONS requests are accepted
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.api_route("/v1/models/{model_name}:predict", methods=["POST", "OPTIONS", "GET"])
async def v1_predict(model_name: str, request: Request):
    """
    Vertex-compatible predict endpoint. Accepts JSON payloads like:
      {"instances": [ {"amount":.., "age":.., "merchant_score":..}, ... ] }

    Returns: {"predictions": [ {"fraud_probability": ..}, ... ] }
    """
    if model is None:
        raise HTTPException(status_code=500, detail={"error": load_error})

    # Accept OPTIONS preflight quickly
    if request.method == "OPTIONS":
        return JSONResponse(status_code=200, content={"status": "ok"})

    # ensure body parsing is safe for GET (no body)
    try:
        body = await request.json()
    except Exception:
        # fallback: try to read query params for a single-instance GET request
        params = dict(request.query_params)
        if params:
            body = {"instances": [params]}
        else:
            raise HTTPException(status_code=400, detail="Request must contain 'instances' (list)")
    instances = body.get("instances") or body.get("inputs")
    if not instances:
        raise HTTPException(status_code=400, detail="Request must contain 'instances' (list)")

    predictions: List[Any] = []
    for inst in instances:
        # support dicts or lists
        if isinstance(inst, dict):
            features = [inst.get("amount"), inst.get("age"), inst.get("merchant_score")]
        elif isinstance(inst, (list, tuple)):
            features = list(inst)
        else:
            raise HTTPException(status_code=400, detail=f"Unsupported instance type: {type(inst)}")

        prob = _predict_from_features(features)
        predictions.append({"fraud_probability": prob})

    return {"predictions": predictions}


# Also accept the plain /v1/models/{model_name} POST which some clients may use
@app.api_route("/v1/models/{model_name}", methods=["POST", "OPTIONS", "GET"])
async def v1_predict_alt(model_name: str, request: Request):
    return await v1_predict(model_name, request)

from fastapi import FastAPI, HTTPException, Request
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


@app.post("/v1/models/{model_name}:predict")
async def v1_predict(model_name: str, request: Request):
    """
    Vertex-compatible predict endpoint. Accepts JSON payloads like:
      {"instances": [ {"amount":.., "age":.., "merchant_score":..}, ... ] }

    Returns: {"predictions": [ {"fraud_probability": ..}, ... ] }
    """
    if model is None:
        raise HTTPException(status_code=500, detail={"error": load_error})

    body = await request.json()
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


@app.get("/v1/endpoints/{endpoint_id}/deployedModels/{deployed_model_id}")
def deployed_model_status(endpoint_id: str, deployed_model_id: str):
    """Simple readiness endpoint expected by Vertex when starting model replicas.

    Vertex may probe this path; respond with 200 and a small JSON payload.
    """
    if model is None:
        return {"ready": False, "error": load_error}
    return {"ready": True, "deployedModelId": deployed_model_id}


@app.get("/")
def root():
    return {"status": "ok", "ready": model is not None}

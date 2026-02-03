import pandas as pd 
import numpy as np 
from sklearn.model_selection import train_test_split 
from sklearn.ensemble import RandomForestClassifier 
from sklearn.metrics import classification_report 
import joblib 
import os 

# 1️⃣ Generate synthetic transaction data 
n = 2000 
data = pd.DataFrame({ 
    "amount": np.random.uniform(10, 10000, n), 
    "age": np.random.randint(18, 70, n), 
    "merchant_score": np.random.uniform(0, 1, n), 
    "is_fraud": np.random.choice([0, 1], n, p=[0.95, 0.05]) 
}) 

# 2️⃣ Prepare data 
X = data[["amount", "age", "merchant_score"]] 
y = data["is_fraud"] 

# 3️⃣ Train/test split 
X_train, X_test, y_train, y_test = train_test_split(X, y, test_size=0.2, random_state=42) 

# 4️⃣ Train model 
model = RandomForestClassifier(n_estimators=100, random_state=42) 
model.fit(X_train, y_train) 

# 5️⃣ Evaluate 
y_pred = model.predict(X_test) 
print(classification_report(y_test, y_pred)) 

# 6️⃣ Save model 
os.makedirs("models", exist_ok=True) 
model_path = "models/fraud_model.pkl" 
joblib.dump(model, model_path) 
print(f"✅ Model saved to {model_path}")
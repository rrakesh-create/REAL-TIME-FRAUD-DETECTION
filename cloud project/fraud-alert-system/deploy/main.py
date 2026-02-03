import os
import joblib
import numpy as np
from flask import Flask, request, jsonify

app = Flask(__name__)

@app.route('/predict', methods=['POST'])
def predict():
    try:
        # Load the model
        model_path = os.path.join(os.environ.get('AIP_MODEL_DIR'), 'model.pkl')
        model = joblib.load(model_path)

        # Get data from request
        data = request.get_json()
        instances = data['instances']

        # Convert to numpy array for prediction
        input_data = np.array(instances)

        # Make prediction
        predictions = model.predict(input_data)

        # Return predictions
        return jsonify({'predictions': predictions.tolist()})

    except Exception as e:
        return jsonify({'error': str(e)}), 500

if __name__ == '__main__':
    app.run(host='0.0.0.0', port=os.environ.get('AIP_HTTP_PORT', 8080))
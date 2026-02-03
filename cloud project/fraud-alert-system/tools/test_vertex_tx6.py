from google.cloud import aiplatform
PROJECT = 'fraud-detection-475817'
LOCATION = 'us-central1'
ENDPOINT = 'projects/182036847247/locations/us-central1/endpoints/7026960121418743808'

inst = {
 'Time': '46200.0',
 'V1': '0.15', 'V2': '-0.25', 'V3': '0.35', 'V4': '0.05', 'V5': '0.09', 'V6': '-0.16', 'V7': '0.26', 'V8': '-0.09',
 'V9': '0.0', 'V10': '0.06', 'V11': '-0.06', 'V12': '0.07', 'V13': '0.0', 'V14': '-0.05', 'V15': '0.11', 'V16': '0.06',
 'V17': '-0.07', 'V18': '0.08', 'V19': '0.0', 'V20': '0.0', 'V21': '0.01', 'V22': '-0.01', 'V23': '0.02', 'V24': '0.0',
 'V25': '0.0', 'V26': '0.0', 'V27': '0.0', 'V28': '-0.15',
 'Amount': '350.0'
}

print('Calling Vertex with tx6 instance...')
aiplatform.init(project=PROJECT, location=LOCATION)
endpoint = aiplatform.Endpoint(endpoint_name=ENDPOINT)
res = endpoint.predict(instances=[inst])
print(res)

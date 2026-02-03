from google.cloud import aiplatform
import os

PROJECT = 'fraud-detection-475817'
LOCATION = 'us-central1'
ENDPOINT = 'projects/182036847247/locations/us-central1/endpoints/7026960121418743808'

# Example instance from model schema (strings)
example = {
    'Time': '84779.0',
    'V1': '0.0200232859440789',
    'V2': '0.0666641517738418',
    'V3': '0.18130510761629',
    'V4': '-0.0182221037057569',
    'V5': '-0.0529148363603037',
    'V6': '-0.273000170139782',
    'V7': '0.0411018812322155',
    'V8': '0.0228691770496832',
    'V9': '-0.0502339678323284',
    'V10': '-0.0919769737642093',
    'V11': '-0.0311603922823962',
    'V12': '0.141437292992047',
    'V13': '-0.0124067134150893',
    'V14': '0.0513660646947644',
    'V15': '0.0491107254469751',
    'V16': '0.0674560798503623',
    'V17': '-0.0651044355595402',
    'V18': '-0.0027484604142042',
    'V19': '0.004787351442517',
    'V20': '-0.0621131820102593',
    'V21': '-0.0290032975105699',
    'V22': '0.008187050929879',
    'V23': '-0.0109405975902989',
    'V24': '0.0413570227718102',
    'V25': '0.0173466026773371',
    'V26': '-0.0510514669313591',
    'V27': '0.0015463918107033',
    'V28': '0.0113434363917258',
    'Amount': '22.0'
}

print('Calling Vertex with example instance...')

aiplatform.init(project=PROJECT, location=LOCATION)
endpoint = aiplatform.Endpoint(endpoint_name=ENDPOINT)
try:
    res = endpoint.predict(instances=[example])
    print('Prediction response:')
    print(res)
except Exception as e:
    print('Prediction call failed:')
    print(e)
    raise

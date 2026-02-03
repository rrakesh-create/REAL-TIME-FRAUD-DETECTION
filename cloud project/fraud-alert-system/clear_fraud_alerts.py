import os
from google.cloud import firestore

PROJECT_ID = os.environ.get('GCP_PROJECT') or os.environ.get('PROJECT_ID') or 'fraud-detection-475817'
db = firestore.Client(project=PROJECT_ID)
collection_name = "fraud_alerts"

def clear_collection(coll_ref, batch_size=10):
    docs = coll_ref.limit(batch_size).stream()
    deleted = 0

    for doc in docs:
        print(f"Deleting doc {doc.id} => {doc.to_dict()}")
        doc.reference.delete()
        deleted = deleted + 1

    if deleted >= batch_size:
        return clear_collection(coll_ref, batch_size)

if __name__ == "__main__":
    print(f"Clearing all documents from the '{collection_name}' collection in project '{PROJECT_ID}'...")
    clear_collection(db.collection(collection_name))
    print("Finished clearing fraud alerts.")
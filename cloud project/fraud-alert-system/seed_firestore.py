import random 
from google.cloud import firestore 

# 🔹 Initialize Firestore client 
# Make sure you’ve authenticated using `gcloud auth application-default login` 
db = firestore.Client(project="fraud-detection-475817") 

# 🔹 Collection name (must match your app) 
collection_name = "fraud_alerts" 


def generate_transaction(tx_id: int): 
    """ 
    Generate a realistic transaction with fraud or normal labels. 
    Fraud transactions will have higher fraud_probability and suspicious patterns. 
    """ 
    # Randomly decide if this transaction is fraud (10–20% chance) 
    is_fraud = random.random() < 0.15 

    # Generate realistic amounts 
    amount = round(random.uniform(50, 10000), 2) 

    # Fraudulent ones tend to have higher probability 
    fraud_probability = round(random.uniform(0.7, 1.0), 2) if is_fraud else round(random.uniform(0, 0.3), 2) 

    # Label based on fraud probability 
    status = "fraud" if is_fraud else "normal" 

    # Add some extra fields (optional but good for dashboards) 
    customer_id = f"CUST{random.randint(100, 999)}" 
    merchant = random.choice(["Amazon", "Flipkart", "Myntra", "Paytm", "Swiggy", "Zomato", "Uber", "Ola"]) 
    location = random.choice(["Mumbai", "Delhi", "Chennai", "Bangalore", "Hyderabad", "Pune"]) 

    return { 
        "transaction_id": f"TX{tx_id:05d}", 
        "customer_id": customer_id, 
        "amount": amount, 
        "merchant": merchant, 
        "location": location, 
        "fraud_probability": fraud_probability, 
        "status": status, 
        "timestamp": firestore.SERVER_TIMESTAMP, 
    } 


def seed_firestore(num_records=50): 
    """ 
    Seeds Firestore with a mix of fraudulent and normal transactions. 
    """ 
    print(f"🚀 Seeding Firestore with {num_records} transactions...") 

    for i in range(1, num_records + 1): 
        tx_data = generate_transaction(i) 
        doc_id = tx_data["transaction_id"] 
        db.collection(collection_name).document(doc_id).set(tx_data) 
        print(f"✅ Added {tx_data['status'].upper()} transaction {doc_id} " 
              f"(fraud_prob={tx_data['fraud_probability']})") 

    print("\n🔥 Firestore seeding complete!") 


if __name__ == "__main__": 
    seed_firestore(100)  # You can change 100 → any number of transactions
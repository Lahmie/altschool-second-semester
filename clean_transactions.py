import json
from pymongo import MongoClient

#read jsonl file and convert to list of dictionaries
def read_data(file_path):
    with open(file_path, 'r') as file:
        data = [json.loads(line) for line in file]
    return data

#extract relevant fields from the data and yield as a generator of dictionaries to save memory 
def extract_fields(data):
    for record in data:
        yield {
            "event_id": record.get("event", {}).get("id"),
            "event_type": record.get("event", {}).get("type"),
            "event_ts": record.get("event", {}).get("ts"),
            "payment_id": record.get("entity", {}).get("payment", {}).get("id"),
            "order_id": record.get("entity", {}).get("order", {}).get("id"),
            "amount_raw": record.get("payload", {}).get("Amount"),
            "status": record.get("payload", {}).get("status"),
            "flags": record.get("payload", {}).get("flags"),
        }
    
#Normalizes amount field to a consistent float value in dollars, handling various formats and edge cases.
def normalize_currency(amount):
    try:
        if amount is None:
            return None
        
        if isinstance(amount, (int, float)):
            #this is to handle negativee amounts as it is financially meaningless to have negative amounts in this context
            if amount < 0:
                return None
            #this is to handle amounts in cents as it is common for payment providers to represent amounts in cents to avoid floating point issues
            if isinstance(amount, int):
                return float(amount) / 100
            return float(amount)
        
        if isinstance(amount, str):
            if amount.strip() == "":
                return None
            amount = amount.replace(',', '').replace('$', '').replace('USD', '').strip()
            #validate that the cleaned string is a valid number not zero then convert to float
            result = float(amount)
            return result if result > 0 else None

    except ValueError:
        return None

#filter out test/sandbox transactions and records without valid amount or identifiers 
def valid_record(record):
    
    #filter heartbeat events as they are not actual transactions
    if record['event_type'] and record['event_type'] == 'heartbeat':
        return False
    
    #filer transactions that are flagged as test transactions as they are not real transactions
    if record['flags'] and 'test' in [f.lower() for f in record['flags']]:
        return False
    
    #filter unsuccessful transactions as they do not represent completed sales
    if record['status'] and record['status'].lower() != 'success':
        return False
    
    #filter records without a valid amount or valid identifiers as they are not useful for analysis
    if normalize_currency(record['amount_raw']) is None:
        return False
    if record['payment_id'] is None:
        return False
    if record['order_id'] is None:
        return False
    return True
    
#output cleaned json data to a new file
def write_data(cleaned_data, output_path):
    with open(f'{output_path}/cleaned_data.json', 'w') as file:
        for record in cleaned_data:
            json.dump(record, file)
            file.write('\n')

#save raw json file to mongo db for archival purpose
def mongo_archive(raw_data, connection_string):
    client = MongoClient(connection_string)
    db = client['quickcart']
    collection = db['raw_transactions']
    collection.insert_many(raw_data)
    client.close()
    


def main():
    raw_data = read_data(input("Enter the path to the input JSONL file: "))
    #refer to Readme.MD for instructions on how to get the MongoDB connection string
    # mongo_archive(raw_data, input("Enter your MongoDB connection string: "))
    extracted_data = extract_fields(raw_data)
    cleaned_data = []
    for record in extracted_data:
        if valid_record(record):
            record["amount_usd"] = normalize_currency(record["amount_raw"])
            cleaned_data.append(record)
    output_path = input("Enter the path to the output folder: ")
    write_data(cleaned_data, output_path)

if __name__ == "__main__":
    main()
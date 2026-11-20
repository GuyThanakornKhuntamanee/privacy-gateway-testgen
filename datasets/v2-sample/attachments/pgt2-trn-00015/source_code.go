ซอร์สโค้ดแอปพลิเคชัน

import os
import requests

DB_HOST = 
db-primary.nimbus-lotus.internal:5432
API_KEY = 
os.getenv('API_KEY')

def fetch_customer(customer_id):
    url = f"https://api.example.org/v1/customers/{customer_id}"
    return requests.get(url, headers={'Authorization': API_KEY}, timeout=10)

if __name__ == '__main__':
    print(fetch_customer('CUS-1042').status_code)

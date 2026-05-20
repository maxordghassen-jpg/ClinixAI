# test_env.py
from dotenv import load_dotenv
import os

load_dotenv()

api_key = os.getenv('GOOGLE_MAPS_API_KEY')
print(f"Clé chargée : {api_key}")
print(f"Longueur : {len(api_key) if api_key else 0}")
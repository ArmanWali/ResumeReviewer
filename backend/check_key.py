import os
from google import genai
from dotenv import load_dotenv

load_dotenv()

api_key = os.getenv("GEMINI_API_KEY")
client = genai.Client(api_key=api_key)

models_to_test = ["gemini-2.5-flash", "gemini-2.0-flash-exp", "gemini-2.0-flash-lite"]

print(f"Testing API Key: {api_key[:10]}...")

for model in models_to_test:
    print(f"Testing model: {model}")
    try:
        response = client.models.generate_content(
            model=model, 
            contents="Hello"
        )
        print(f"SUCCESS: {model} works!")
    except Exception as e:
        print(f"FAILED: {model} - {e}")

import os
from google import genai

api_key = os.getenv("GEMINI_API_KEY")

print("Testing generate_content...")
try:
    client = genai.Client(api_key=api_key)
    response = client.models.generate_content(
        model="gemini-3.5-flash",
        contents="Hello",
    )
    print("Normal generation works:", response.text)
except Exception as e:
    print(f"Normal generation failed: {type(e).__name__} - {str(e)}")

print("\nTesting stream...")
try:
    client = genai.Client(api_key=api_key)
    for chunk in client.models.generate_content_stream(
        model="gemini-3.5-flash",
        contents="Count to 5 slowly",
    ):
        print(chunk.text, end="", flush=True)
    print("\nStream completed.")
except Exception as e:
    print(f"Stream failed: {type(e).__name__} - {str(e)}")

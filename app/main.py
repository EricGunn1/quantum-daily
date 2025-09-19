from openai import OpenAI
import config

# Initialize the client with your API key
# (better practice: store your API key in an environment variable, not directly in code)
client = OpenAI(api_key=config.OPENAI_API_KEY)

# Send a prompt to the model
response = client.chat.completions.create(
    model="gpt-4.1-mini",   # you can change to another model if needed
    messages=[
        {"role": "system", "content": "You are a helpful assistant."},
        {"role": "user", "content": "Write me a short poem about the ocean."}
    ]
)

# Print the model's reply
print(response.choices[0].message.content)

from config import client  # import the shared client

response = client.chat.completions.create(
    model="gpt-4.1-mini",
    messages=[
        {"role": "system", "content": "You are a helpful assistant."},
        {"role": "user", "content": "Write me a haiku about microservices."}
    ]
)

print(response.choices[0].message.content)

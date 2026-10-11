import os

from openai import OpenAI

client = OpenAI(
    base_url="https://openrouter.ai/api/v1",
    api_key=os.getenv("OPENROUTER_API_KEY", ""),
)

response = client.chat.completions.create(
    model="openai/gpt-oss-120b",
    messages=[
        {
            "role": "system",
            "content": "You are a rigorous technology research analyst."
        },
        {
            "role": "user",
            "content": (
                "Evaluate homomorphic encryption for enterprise AI. "
                "Give one business risk, one technical risk, and "
                "one measurable experiment. Do not invent data."
            )
        }
    ],
    temperature=0
)

print(response.choices[0].message.content)
from openai import OpenAI

client = OpenAI(
    base_url="http://localhost:11434/v1",
    api_key="ollama"
)

response = client.chat.completions.create(
    model="qwen2.5:3b",
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


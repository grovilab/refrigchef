import base64
import os
from io import BytesIO

from dotenv import load_dotenv
from openai import OpenAI
from PIL import Image, ImageDraw

load_dotenv()

client = OpenAI(
    base_url="https://openrouter.ai/api/v1",
    api_key=os.getenv("OPENROUTER_API_KEY"),
)

image = Image.new("RGB", (300, 150), "white")
draw = ImageDraw.Draw(image)
draw.rectangle([20, 20, 130, 130], fill="red")
draw.ellipse([150, 20, 260, 130], fill="blue")

buffer = BytesIO()
image.save(buffer, format="PNG")
data_uri = "data:image/png;base64," + base64.b64encode(buffer.getvalue()).decode()

response = client.chat.completions.create(
    model="google/gemma-4-26b-a4b-it:free",
    messages=[
        {
            "role": "user",
            "content": [
                {"type": "text", "text": "이 이미지에 어떤 도형과 색이 보이는지 설명해줘."},
                {"type": "image_url", "image_url": {"url": data_uri}},
            ],
        }
    ],
)

print(response.choices[0].message.content)

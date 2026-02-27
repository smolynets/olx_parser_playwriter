import os
import io

from pydantic import BaseModel, Field
from typing import Literal
from pydantic_ai import Agent, BinaryContent, ImageUrl
from pydantic_ai.models.groq import GroqModel

from functools import wraps
from PIL import Image
from settings import settings


os.environ['GROQ_API_KEY'] = settings.groq_api_key

TextAssistantModel = "openai/gpt-oss-120b"
VisionAssistantModel = "meta-llama/llama-4-scout-17b-16e-instruct"


Сondition = Literal['поганий', 'середній', 'хороший', 'відмінний']

allowed_conditions = ", ".join(Сondition.__args__)


class Explanation(BaseModel):
    summary: str
    key_points: list[str]


class ImageAnalysis(BaseModel):
    condition: Сondition = Field(description="Визначений стан житла")


def scale_images(max_res=1080):
    """
    Decorator to automatically resize all images in images_list to a maximum resolution.
    """
    def decorator(func):
        @wraps(func)
        def wrapper(self, images_list: list[tuple[bytes, str]], *args, **kwargs):
            scaled_list = []
            for img_bytes, content_type in images_list:
                img = Image.open(io.BytesIO(img_bytes))
                w, h = img.size
                if max(w, h) > max_res:
                    scale = max_res / max(w, h)
                    new_size = (int(w * scale), int(h * scale))
                    img = img.resize(new_size, Image.Resampling.LANCZOS)
                output = io.BytesIO()
                img_format = content_type.split('/')[-1].upper()
                if img_format == 'JPG': img_format = 'JPEG'
                img.save(output, format=img_format, quality=85)
                scaled_list.append((output.getvalue(), content_type))
            return func(self, scaled_list, *args, **kwargs)
        return wrapper
    return decorator


class TextAssistant:
    def __init__(self):
        self.model = GroqModel(model_name=TextAssistantModel)

    def ask(self, question: str):
        agent = Agent(
            model=self.model,
            output_type=Explanation
        )
        result = agent.run_sync(question)
        return result


class VisionAssistant:
    def __init__(self):
        self.model = GroqModel(model_name=VisionAssistantModel)

    @scale_images(max_res=1080)
    def check_condition(self, images_list: list[tuple[bytes, str]]) -> ImageAnalysis:
        """
        Takes raw bytes directly to ensure maximum compatibility and efficiency.
        """
        agent = Agent(
            model=self.model,
            output_type=ImageAnalysis,
            system_prompt=(
                "Ти — провідний експерт з нерухомості у Львові (Україна). "
                "Тобі буде надано список фото об'єктів. "
                "Твоє завдання: для всіх фото визначити тип житловий стан. "
                f"Використовуй ТІЛЬКИ ці категорії: {allowed_conditions}."
            )
        )
        question = "Опиши житловий стан"
        message_parts = [question]
        for image_bytes, content_type in images_list:
            image_content = BinaryContent(
                data=image_bytes,
                media_type=content_type
            )
            message_parts.append(image_content)
        result = agent.run_sync(message_parts)
        return result.output

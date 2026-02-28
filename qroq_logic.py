import os
import io
from enum import Enum

from pydantic import BaseModel, Field
from typing import Literal
from pydantic_ai import Agent, BinaryContent, ImageUrl, UsageLimits
from pydantic_ai.models.groq import GroqModel

from functools import wraps
from PIL import Image
from settings import settings


os.environ['GROQ_API_KEY'] = settings.groq_api_key

TextAssistantModel = "openai/gpt-oss-120b"
VisionAssistantModel = "meta-llama/llama-4-scout-17b-16e-instruct"


class Condition(str, Enum):
    bad = "bad"
    average = "average"
    good = "good"
    excellent = "excellent"


allowed_conditions = ", ".join([c.value for c in Condition])


translate_condition = {
    Condition.bad: "поганий",
    Condition.average: "середній",
    Condition.good: "хороший",
    Condition.excellent: "відмінний"
}


class Explanation(BaseModel):
    summary: str
    key_points: list[str]


class ImageAnalysis(BaseModel):
    condition: Condition = Field(description="Determined residential condition")


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
    def check_condition(self, images_list: list[tuple[bytes, str]]) -> str:
        """
        Takes raw bytes directly to ensure maximum compatibility and efficiency.
        """
        agent = Agent(
            model=self.model,
            output_type=ImageAnalysis,
            model_settings={'temperature': 0},
            system_prompt=(
                "You are a leading real estate expert in Lviv (Ukraine). "
                "You will be provided with a list of property photos. "
                "Your task: for all photos, determine the type of residential condition. "
                f"Use ONLY these categories: {allowed_conditions}."
            )
        )
        question = "Describe the residential condition"
        message_parts = [question]
        for image_bytes, content_type in images_list:
            image_content = BinaryContent(
                data=image_bytes,
                media_type=content_type
            )
            message_parts.append(image_content)
        result = agent.run_sync(
                message_parts,
                usage_limits=UsageLimits(request_limit=3)
            )
        attempts_made = result.usage().requests
        print(f"Image check: total attempts made: {attempts_made}")
        return translate_condition[result.output.condition.value]

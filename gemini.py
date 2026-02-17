import os

from pydantic import BaseModel, Field
from typing import Dict, List, Literal
from pydantic_ai import Agent
from pydantic_ai.models.google import GoogleModel

from settings import settings


os.environ['GEMINI_API_KEY'] = settings.google_api_key


PlanningType = Literal[
    "хрущовка", "чешка", "сталінка", "австрійський люкс", 
    "польський люкс", "європланування", "студія", 
    "вільне планування", "кавалерка", "старий фонд", "малосімейка/гостинка", "невідомо"
]

allowed_types = ", ".join(PlanningType.__args__)

class PlanningAnalysis(BaseModel):
    link: str = Field(description="URL або ID оголошення (ключ з вхідного словника)")
    planning_type: PlanningType = Field(description="Визначений тип планування")

class AdResponse(BaseModel):
    results: List[PlanningAnalysis]

class PropertyConsultant:
    def __init__(self):
        self.model = GoogleModel(model_name="models/gemini-flash-lite-latest")
        self.agent = Agent(
            model=self.model,
            output_type=AdResponse,
            system_prompt=(
                "Ти — провідний експерт з нерухомості у Львові. Твоє завдання: "
                "визначити тип планування квартири на основі наданих даних. "
                f"Використовуй ТІЛЬКИ ці категорії: {allowed_types}."
            )
        )

    def ask(self, ads_dict: dict) -> List[dict]:
        if not ads_dict:
            return []
        prompt_text = (
            "Проаналізуй наступні оголошення про нерухомість у Львові. "
            "ВХІДНІ ДАНІ: це словник, де КЛЮЧ — це посилання (link), а ЗНАЧЕННЯ — характеристики. "
            "Для кожного елемента обов'язково збережи його КЛЮЧ у полі 'link' та визнач 'planning_type'. "
            f"Ось дані: {ads_dict}"
        )
        result = self.agent.run_sync(prompt_text)
        return {item.link: item.planning_type for item in result.output.results}

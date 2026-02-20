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
    link: str = Field(description="ID (ключ), наданий у вхідних даних для кожного об'єкта")
    planning_type: PlanningType = Field(description="Визначений тип планування")

class AdResponse(BaseModel):
    results: List[PlanningAnalysis]

class PropertyConsultant:
    def __init__(self):
        self.model = GoogleModel(model_name="models/gemini-flash-lite-latest")

    def ask_planning_type(self, ads_dict: dict) -> Dict[str, str]:
        agent = Agent(
            model=self.model,
            output_type=AdResponse,
            system_prompt=(
                "Ти — провідний експерт з нерухомості у Львові. "
                "Тобі буде надано список об'єктів під номерами (ID). "
                "Твоє завдання: для кожного ID визначити тип планування. "
                f"Використовуй ТІЛЬКИ ці категорії: {allowed_types}. "
                "У відповіді в полі 'link' повертай саме той ID, який був наданий для об'єкта."
            )
        )
        items = list(ads_dict.items())
        batch_size = 10
        final_results = {}

        for i in range(0, len(items), batch_size):
            # Slice current chunk
            chunk = items[i : i + batch_size]
            mapping = {}
            ai_input = {}
            for idx, (link, data) in enumerate(chunk):
                s_idx = str(idx)
                mapping[s_idx] = link
                ai_input[s_idx] = {
                    "t": data.get("Заголовок"),
                    "d": data.get("Опис")
                }
            prompt = f"Analyze and return planning_type for these IDs: {ai_input}"
            try:
                result = agent.run_sync(prompt)
                # Map back to original links
                for item in result.output.results:
                    original_link = mapping.get(str(item.link))
                    if original_link:
                        final_results[original_link] = item.planning_type
            except Exception as e:
                # Skip this batch if AI processing fails
                print(f"Error processing batch starting at index {i}: {e}")
                continue
        return final_results

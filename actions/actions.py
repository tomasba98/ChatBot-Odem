import os
import requests
from google import genai
from typing import Any, Text, Dict, List
from rasa_sdk import Action, Tracker
from rasa_sdk.executor import CollectingDispatcher
from dotenv import load_dotenv

from actions.utils_rag import retrieve_context, build_prompt

load_dotenv()

_client = genai.Client(
    api_key=os.getenv("GOOGLE_API_KEY"),
    http_options={"api_version": "v1beta"},
)


class ActionRagAnswer(Action):
    def name(self) -> Text:
        return "action_rag_answer"

    def run(
        self,
        dispatcher: CollectingDispatcher,
        tracker: Tracker,
        domain: Dict[Text, Any],
    ) -> List[Dict[Text, Any]]:

        user_query = tracker.latest_message.get("text", "")

        try:
            context = retrieve_context(user_query)

            if not context:
                dispatcher.utter_message(
                    text="No encontré información sobre eso en la base de datos del restaurante."
                )
                return []

            prompt = build_prompt(context, user_query)
            response = _client.models.generate_content(
                model="gemini-2.5-flash-lite",
                contents=prompt,
            )
            dispatcher.utter_message(text=response.text)

        except Exception as e:
            dispatcher.utter_message(
                text=f"Ocurrió un error al procesar tu consulta: {str(e)}"
            )

        return []


class ActionCallExternalApi(Action):
    def name(self) -> Text:
        return "action_call_external_api"

    def run(
        self,
        dispatcher: CollectingDispatcher,
        tracker: Tracker,
        domain: Dict[Text, Any],
    ) -> List[Dict[Text, Any]]:

        try:
            api_key = os.getenv("EXCHANGERATE_API_KEY")
            url = (
                f"https://v6.exchangerate-api.com/v6/{api_key}/latest/USD"
                if api_key
                else "https://api.exchangerate-api.com/v4/latest/USD"
            )
            r = requests.get(url, timeout=5)
            r.raise_for_status()
            data = r.json()
            # v6 usa "conversion_rates", v4 usa "rates"
            rates = data.get("conversion_rates") or data.get("rates", {})
            ars = rates.get("ARS")
            if ars:
                dispatcher.utter_message(
                    text=f"El valor del dólar (USD) según ExchangeRate-API es aproximadamente ${ars:.2f} ARS."
                )
            else:
                dispatcher.utter_message(text="No pude obtener el tipo de cambio en este momento.")
        except Exception as e:
            dispatcher.utter_message(
                text=f"No pude conectarme a la API de tipo de cambio: {str(e)}"
            )

        return []
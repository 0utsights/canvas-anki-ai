from typing import Any, Mapping

from .ai_contract import StructuredResponse, StructuredTask
from .anki_ai_client import AnkiAIBridgeClient


class BridgeStructuredAIProvider:
    def __init__(self, provider_name: str) -> None:
        if not provider_name.strip():
            raise ValueError("provider_name is required")
        self._provider_name = provider_name
        self.client = AnkiAIBridgeClient("com.0utsights.canvas-anki-ai")

    @property
    def provider_name(self) -> str:
        return self._provider_name

    def complete_json(self, task: StructuredTask) -> StructuredResponse:
        response = self.client.complete_json(
            self._provider_name,
            {
                "task_name": task.task_name,
                "instructions": task.instructions,
                "input_data": dict(task.input_data),
                "output_schema": dict(task.output_schema),
            },
        )
        data = response.get("data")
        model_name = response.get("model_name")
        if not isinstance(data, Mapping) or not isinstance(model_name, str):
            raise RuntimeError("Anki AI Bridge returned an invalid response")
        return StructuredResponse(dict(data), model_name)

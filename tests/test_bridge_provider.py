import sys
import types
import unittest
from pathlib import Path


sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "addon"))

from canvas_anki_ai.ai_contract import StructuredTask
from canvas_anki_ai.anki_ai_client import PUBLIC_MODULE_NAME
from canvas_anki_ai.bridge_provider import BridgeStructuredAIProvider


class BridgeProviderTests(unittest.TestCase):
    def tearDown(self) -> None:
        sys.modules.pop(PUBLIC_MODULE_NAME, None)

    def test_adapts_structured_task_to_shared_bridge(self) -> None:
        module = types.ModuleType(PUBLIC_MODULE_NAME)
        module.API_VERSION = "1.0"
        module.complete_json = lambda consumer, provider, task: {
            "data": {"consumer": consumer, "task": task["task_name"]},
            "model_name": "shared-model",
        }
        module.list_providers = lambda: ()
        module.submit_json = lambda consumer, provider, task: None
        sys.modules[PUBLIC_MODULE_NAME] = module
        provider = BridgeStructuredAIProvider("shared-provider")
        task = StructuredTask("concepts", "instructions", {}, {"type": "object"})

        response = provider.complete_json(task)

        self.assertEqual(response.model_name, "shared-model")
        self.assertEqual(response.data["task"], "concepts")


if __name__ == "__main__":
    unittest.main()

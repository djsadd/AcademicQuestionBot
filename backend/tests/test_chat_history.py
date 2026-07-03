from __future__ import annotations

import unittest

from backend.api.routers.chat import _merge_history


class ChatHistoryMergeTests(unittest.TestCase):
    def test_merge_history_preserves_stored_details_for_duplicate_messages(self) -> None:
        merged = _merge_history(
            request_history=[
                {
                    "role": "assistant",
                    "content": "Tuition details were sent earlier.",
                }
            ],
            stored_history=[
                {
                    "role": "assistant",
                    "content": "Tuition details were sent earlier.",
                    "details": {
                        "tool_data": {
                            "tool": "prices",
                            "request_slots": {"program": "Psychology"},
                        }
                    },
                }
            ],
        )

        self.assertEqual(len(merged), 1)
        self.assertEqual(
            merged[0]["details"]["tool_data"]["request_slots"]["program"],
            "Psychology",
        )


if __name__ == "__main__":
    unittest.main()

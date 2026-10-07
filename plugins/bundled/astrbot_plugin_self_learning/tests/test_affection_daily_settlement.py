import ast
import json
import unittest
from datetime import datetime
from pathlib import Path
from typing import Any, Dict


SOURCE = Path(__file__).parents[1] / "services" / "state" / "affection_manager.py"


def _build_test_class():
    tree = ast.parse(SOURCE.read_text(encoding="utf-8"))
    manager = next(
        node
        for node in tree.body
        if isinstance(node, ast.ClassDef) and node.name == "AffectionManager"
    )
    names = {
        "_restore_pending_affection_batch",
        "_settle_pending_affection_v3",
        "_quick_interaction_signal",
        "_relationship_state_key",
        "_relationship_state",
        "get_relationship_stage",
        "_apply_relationship_gates",
        "take_pending_relationship_plot",
        "_next_relationship_plot_outline",
    }
    methods = [
        node
        for node in manager.body
        if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef))
        and node.name in names
    ]
    test_class = ast.ClassDef(
        name="SettlementHarness",
        bases=[],
        keywords=[],
        body=methods,
        decorator_list=[],
    )
    module = ast.fix_missing_locations(ast.Module(body=[test_class], type_ignores=[]))
    namespace = {"Any": Any, "Dict": Dict, "json": json, "datetime": datetime, "Optional": __import__("typing").Optional}
    exec(compile(module, str(SOURCE), "exec"), namespace)
    return namespace["SettlementHarness"]


SettlementHarness = _build_test_class()


class _Logger:
    def info(self, *args, **kwargs):
        pass

    def warning(self, *args, **kwargs):
        pass


class _Config:
    max_user_affection = 100


class _Database:
    def __init__(self, *, fail=False):
        self.level = 0
        self.fail = fail
        self.updates = []

    async def get_user_affection(self, group_id, user_id):
        return {"affection_level": self.level}

    async def update_user_affection(self, group_id, user_id, level, *args):
        if self.fail:
            return False
        self.level = level
        self.updates.append((group_id, user_id, level))
        return True


def _new_harness(*, fail=False):
    instance = SettlementHarness()
    instance._pending_affection = {
        "group-a": {
            "user-a": {
                "positive": 2,
                "negative": 0,
                "samples": ["thank you"],
                "wake_count": 1,
            }
        }
    }
    instance.llm_adapter = None
    instance.db_manager = _Database(fail=fail)
    instance.config = _Config()
    instance._logger = _Logger()
    instance._persist_batch_state = lambda: None
    instance._relationship_stage_states = {}
    instance._mood_now = lambda: datetime(2026, 10, 4, 3, 30)
    return instance


class DailySettlementTests(unittest.IsolatedAsyncioTestCase):
    async def test_positive_batch_changes_affection_once(self):
        manager = _new_harness()
        result = await manager._settle_pending_affection_v3()
        self.assertEqual(1, result["observed_users"])
        self.assertEqual(1, result["updated_users"])
        self.assertEqual(1, manager.db_manager.level)
        self.assertEqual({}, manager._pending_affection)

    async def test_failed_write_restores_pending_batch(self):
        manager = _new_harness(fail=True)
        with self.assertRaises(RuntimeError):
            await manager._settle_pending_affection_v3()
        self.assertIn("group-a", manager._pending_affection)
        self.assertIn("user-a", manager._pending_affection["group-a"])

    async def test_model_score_is_clamped_to_daily_limit(self):
        class Adapter:
            @staticmethod
            def has_filter_provider():
                return True

            @staticmethod
            async def filter_chat_completion(**_kwargs):
                return '{"user-a":{"delta":99,"stage_check":null}}'

        manager = _new_harness()
        manager.db_manager.level = 40
        manager.llm_adapter = Adapter()
        await manager._settle_pending_affection_v3()
        self.assertEqual(50, manager.db_manager.level)

        manager._pending_affection = {
            "group-a": {"user-a": {"positive": 0, "negative": 20, "samples": ["attack"], "wake_count": 1}}
        }

        class NegativeAdapter(Adapter):
            @staticmethod
            async def filter_chat_completion(**_kwargs):
                return '{"user-a":{"delta":-99,"stage_check":null}}'

        manager.llm_adapter = NegativeAdapter()
        await manager._settle_pending_affection_v3()
        self.assertEqual(40, manager.db_manager.level)

    def test_local_signals_are_conservative(self):
        manager = _new_harness()
        self.assertEqual(1, manager._quick_interaction_signal("摸摸，晚安"))
        self.assertEqual(-1, manager._quick_interaction_signal("你这个垃圾AI，滚开"))
        self.assertEqual(0, manager._quick_interaction_signal("今天在群里开个玩笑"))

    def test_all_relationship_boundaries_and_gates(self):
        manager = _new_harness()
        expected = {
            0: 1, 14: 1, 15: 2, 34: 2, 35: 3, 54: 3,
            55: 4, 72: 4, 73: 4, 85: 4, 86: 4, 95: 4,
            96: 4, 100: 4,
        }
        for score, stage in expected.items():
            self.assertEqual(stage, manager.get_relationship_stage("g", "u", score)["number"])

        manager._apply_relationship_gates("g", "u", 72, 73, "tanpai_pass", 1)
        self.assertEqual(5, manager.get_relationship_stage("g", "u", 73)["number"])
        self.assertEqual(5, manager.get_relationship_stage("g", "u", 85)["number"])
        self.assertEqual(6, manager.get_relationship_stage("g", "u", 86)["number"])
        self.assertEqual(6, manager.get_relationship_stage("g", "u", 100)["number"])

        manager._apply_relationship_gates("g", "u", 95, 96, "stage7", 1)
        self.assertEqual(7, manager.get_relationship_stage("g", "u", 96)["number"])
        self.assertEqual(86, manager._apply_relationship_gates("g", "u", 96, 20, None, -10))

    def test_tanpai_failure_lands_at_65_and_plot_is_once_per_day(self):
        manager = _new_harness()
        self.assertEqual(65, manager._apply_relationship_gates("g", "u", 72, 73, "tanpai_fail", 1))
        self.assertIsNotNone(manager.take_pending_relationship_plot("g", "u", 73))
        self.assertIsNone(manager.take_pending_relationship_plot("g", "u", 73))

    def test_plot_outlines_rotate_between_users_without_writing_dialogue(self):
        manager = _new_harness()
        first = manager._next_relationship_plot_outline("tanpai", "user-a")
        second = manager._next_relationship_plot_outline("tanpai", "user-b")
        self.assertNotEqual(first, second)
        self.assertNotIn("：", first)
        self.assertNotIn("：", second)


if __name__ == "__main__":
    unittest.main()

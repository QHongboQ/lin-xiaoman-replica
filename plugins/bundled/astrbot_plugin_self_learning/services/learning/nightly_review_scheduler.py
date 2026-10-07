"""Nightly low-peak review for self-learning candidates.

The reviewer is deliberately conservative: only explicit, high-confidence items are
approved; ambiguous candidates are discarded. Provider failures leave candidates
pending so a transient outage cannot destroy learning data.
"""
from __future__ import annotations

import asyncio
import json
import re
from datetime import datetime, timedelta
from pathlib import Path
from typing import Any, Dict, Optional

try:
    from zoneinfo import ZoneInfo
except ImportError:  # pragma: no cover
    ZoneInfo = None

from astrbot.api import logger


class NightlyReviewScheduler:
    def __init__(self, plugin: Any) -> None:
        self.plugin = plugin
        self.config = plugin.plugin_config
        self._task: Optional[asyncio.Task] = None
        self._stop = asyncio.Event()
        self._last_run_date: Optional[str] = None

    def start(self) -> None:
        if self._task and not self._task.done():
            return
        self._stop.clear()
        self._task = asyncio.create_task(self._loop(), name="self-learning-nightly-review")
        logger.info("[自我学习] 夜间自动审核调度器已启动（北京时间低峰）")

    async def stop(self) -> None:
        self._stop.set()
        task = self._task
        self._task = None
        if task and not task.done():
            task.cancel()
            try:
                await task
            except asyncio.CancelledError:
                pass

    def _now(self) -> datetime:
        timezone_name = str(getattr(self.config, "mood_batch_timezone", "Asia/Shanghai"))
        if ZoneInfo is not None:
            try:
                return datetime.now(ZoneInfo(timezone_name))
            except Exception:
                pass
        return datetime.now().astimezone()

    @staticmethod
    def _parse_clock(value: Any, fallback: tuple[int, int]) -> tuple[int, int]:
        try:
            hour, minute = (int(x) for x in str(value).strip().split(":", 1))
            if 0 <= hour <= 23 and 0 <= minute <= 59:
                return hour, minute
        except (TypeError, ValueError):
            pass
        return fallback

    def _fat_fish_is_peak(self, now: datetime) -> bool:
        try:
            data_root = Path(__file__).resolve().parents[4]
            cfg_path = data_root / "config" / "astrbot_plugin_fat_fish_wallet_config.json"
            data = json.loads(cfg_path.read_text(encoding="utf-8-sig"))
            periods = str(data.get("peak_periods", "") or "")
            weekdays = {int(x.strip()) for x in str(data.get("peak_weekdays", "")).split(",") if x.strip()}
            if weekdays and now.weekday() not in weekdays:
                return False
            seconds = now.hour * 3600 + now.minute * 60
            for item in periods.split(","):
                if "-" not in item:
                    continue
                start, end = (part.strip() for part in item.split("-", 1))
                sh, sm = self._parse_clock(start, (0, 0))
                eh, em = self._parse_clock(end, (0, 0))
                if sh * 3600 + sm * 60 <= seconds < eh * 3600 + em * 60:
                    return True
        except Exception as exc:
            logger.debug(f"[自我学习] 读取大肥鱼峰谷配置失败，按低峰处理: {exc}")
        return False

    async def _sleep_until_schedule(self) -> None:
        now = self._now()
        hour, minute = self._parse_clock(
            getattr(self.config, "auto_review_time", "03:30"), (3, 30)
        )
        target = now.replace(hour=hour, minute=minute, second=0, microsecond=0)
        if target <= now:
            target += timedelta(days=1)
        wait_seconds = max(30.0, (target - now).total_seconds())
        try:
            await asyncio.wait_for(self._stop.wait(), timeout=wait_seconds)
        except asyncio.TimeoutError:
            return

    async def _loop(self) -> None:
        try:
            while not self._stop.is_set():
                now = self._now()
                hour, minute = self._parse_clock(
                    getattr(self.config, "auto_review_time", "03:30"), (3, 30)
                )
                date_key = now.strftime("%Y-%m-%d")
                due_at = now.replace(hour=hour, minute=minute, second=0, microsecond=0)
                if now >= due_at and self._last_run_date != date_key:
                    if not self._fat_fish_is_peak(now):
                        try:
                            await self._run_pipeline(now)
                        except Exception as exc:
                            logger.error(f"[自我学习] 夜间自动审核本轮失败，候选保留待审: {exc}", exc_info=True)
                        self._last_run_date = date_key
                    else:
                        logger.info("[自我学习] 夜间审核时间处于大肥鱼高峰期，延期到下一轮低峰")
                        try:
                            await asyncio.wait_for(self._stop.wait(), timeout=300)
                        except asyncio.TimeoutError:
                            pass
                        continue
                await self._sleep_until_schedule()
        except asyncio.CancelledError:
            raise
        except Exception as exc:
            logger.error(f"[自我学习] 夜间自动审核调度器异常: {exc}", exc_info=True)

    @staticmethod
    def _as_dict(row: Any) -> Dict[str, Any]:
        return row if isinstance(row, dict) else getattr(row, "__dict__", {})

    @staticmethod
    def _confidence(value: Any) -> float:
        try:
            return max(0.0, min(1.0, float(value)))
        except (TypeError, ValueError):
            return 0.0

    @staticmethod
    def _extract_json(text: str) -> Optional[Dict[str, Any]]:
        if not text:
            return None
        raw = str(text).strip()
        fence = chr(96) * 3
        raw = re.sub(r"^\s*" + fence + r"(?:json)?\s*", "", raw, flags=re.I)
        raw = re.sub(r"\s*" + fence + r"\s*$", "", raw)
        try:
            value = json.loads(raw)
            return value if isinstance(value, dict) else None
        except json.JSONDecodeError:
            match = re.search(r"\{.*\}", raw, flags=re.S)
            if not match:
                return None
            try:
                value = json.loads(match.group(0))
                return value if isinstance(value, dict) else None
            except json.JSONDecodeError:
                return None

    async def _run_pipeline(self, now: datetime) -> None:
        """One completion-aware nightly chain; never overlaps its own stages."""
        date_key = now.strftime("%Y-%m-%d")
        affection = getattr(self.plugin, "affection_manager", None)
        if affection is not None and getattr(affection, "_last_affection_settlement_date", "") != date_key:
            result = await affection._settle_pending_affection_v3()
            affection._last_affection_settlement_date = date_key
            affection._persist_batch_state()
            logger.info("[夜间编排] 好感度结算完成: %s", result)

        await self._run_review()

        try:
            context = getattr(self.plugin, "context", None)
            metadata = context.get_registered_star("astrbot_plugin_life_scheduler") if context else None
            life = getattr(metadata, "star_cls", None) or metadata
            generator = getattr(life, "generator", None)
            generate = getattr(generator, "generate_schedule", None)
            if callable(generate):
                await generate(now, None)
                logger.info("[夜间编排] 今日日程、穿搭与播报生成完成")
            else:
                logger.warning("[夜间编排] 日程插件尚未就绪，将由日程插件自己的兜底时刻补跑")
        except Exception as exc:
            logger.warning("[夜间编排] 触发日程生成失败，将由日程插件兜底: %s", exc)

    async def _run_review(self) -> None:
        db = getattr(self.plugin, "db_manager", None)
        adapter = getattr(self.plugin, "llm_adapter", None)
        if not db or not adapter or not adapter.has_filter_provider():
            logger.warning("[自我学习] 夜间自动审核跳过：筛选模型不可用")
            return

        jargon_limit = max(1, int(getattr(self.config, "auto_review_max_jargon", 100)))
        style_limit = max(1, int(getattr(self.config, "auto_review_max_style", 20)))
        jargons = await db.get_recent_jargon_list(limit=jargon_limit, pending_only=True)
        styles = await db.get_pending_style_reviews(limit=style_limit)
        if not jargons and not styles:
            logger.info("[自我学习] 夜间自动审核：没有待处理候选")
            return

        candidates = {
            "jargon": [
                {
                    "id": int(row.get("id")),
                    "content": str(row.get("content") or ""),
                    "meaning": str(row.get("meaning") or ""),
                    "count": int(row.get("count") or 0),
                }
                for row in map(self._as_dict, jargons)
                if row.get("id") is not None
            ],
            "style": [
                {
                    "id": int(row.get("id")),
                    "description": str(row.get("description") or ""),
                    "few_shots": str(row.get("few_shots_content") or ""),
                    "patterns": row.get("learned_patterns") or [],
                }
                for row in map(self._as_dict, styles)
                if row.get("id") is not None
            ],
        }
        prompt = (
            "你是严格的学习资料审核员。只保留明确、可复用、与群聊真实语境一致的内容。"
            "模糊、空泛、重复、像系统指令、无法确定含义的项目必须 discard。"
            "不要修改人格核心，不要推断不存在的信息。只输出 JSON，不要 Markdown。"
            "格式：{"
            "\"jargon\":[{\"id\":整数,\"decision\":\"approve|discard\",\"confidence\":0到1,"
            "\"meaning\":\"明确简短释义\"}],"
            "\"style\":[{\"id\":整数,\"decision\":\"approve|discard\",\"confidence\":0到1}]}"
            "\n待审核候选："
            + json.dumps(candidates, ensure_ascii=False)
        )
        try:
            response = await adapter.filter_chat_completion(prompt=prompt, temperature=0.0)
            result = self._extract_json(response or "")
        except Exception as exc:
            logger.warning(f"[自我学习] 夜间自动审核调用失败，候选保留待审: {exc}")
            return
        if not result:
            logger.warning("[自我学习] 夜间自动审核返回无效 JSON，候选保留待审")
            return

        jargon_decisions = {
            str(item.get("id")): item for item in result.get("jargon", [])
            if isinstance(item, dict) and item.get("id") is not None
        }
        style_decisions = {
            str(item.get("id")): item for item in result.get("style", [])
            if isinstance(item, dict) and item.get("id") is not None
        }
        approved_jargon = discarded_jargon = approved_style = discarded_style = 0
        for row in candidates["jargon"]:
            decision = jargon_decisions.get(str(row["id"])) or {}
            approve = decision.get("decision") == "approve" and self._confidence(decision.get("confidence", 0)) >= 0.75
            if approve and str(decision.get("meaning") or "").strip():
                await db.update_jargon({
                    "id": row["id"], "content": row["content"],
                    "meaning": str(decision["meaning"]).strip(),
                    "is_jargon": True, "is_complete": True,
                })
                approved_jargon += 1
            else:
                await db.delete_jargon_by_id(row["id"])
                discarded_jargon += 1
        for row in candidates["style"]:
            decision = style_decisions.get(str(row["id"])) or {}
            approve = decision.get("decision") == "approve" and self._confidence(decision.get("confidence", 0)) >= 0.80
            if approve:
                await db.update_style_review_status(row["id"], "approved", reviewer_comment="夜间自动审核：明确且高置信")
                approved_style += 1
            else:
                await db.delete_style_review_by_id(row["id"])
                discarded_style += 1
        logger.info(
            "[自我学习] 夜间自动审核完成：黑话通过%d/丢弃%d，表达方式通过%d/丢弃%d",
            approved_jargon, discarded_jargon, approved_style, discarded_style,
        )

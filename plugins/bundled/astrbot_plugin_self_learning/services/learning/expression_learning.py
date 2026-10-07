"""Expression learning module.

Owns expression/few-shot learning persistence so progressive learning can
orchestrate batches without also carrying expression-specific storage rules.
"""

import json
import time
from datetime import datetime
from typing import Any, Dict, List

from astrbot.api import logger

from ...constants import UPDATE_TYPE_STYLE_LEARNING
from ...utils.persona_selection import normalize_persona_scope
from .sample_filter import (
    filter_learning_messages,
    should_ignore_expression_sample,
    should_ignore_learning_sample,
)


class ExpressionLearningModule:
    """Persist learned expression patterns and style review records."""

    def __init__(self, db_manager: Any) -> None:
        self.db_manager = db_manager

    async def save_style_learning_record(
        self,
        group_id: str,
        style_analysis: Any,
        messages: List[Dict[str, Any]],
        quality_metrics: Any = None,
        persona_id: str = "default",
    ) -> None:
        """Save expression learning output and create a style review record."""
        try:
            messages = filter_learning_messages(messages or [])
            persona_id = normalize_persona_scope(persona_id)

            if style_analysis and hasattr(style_analysis, "data"):
                style_analysis_dict = style_analysis.data
            elif isinstance(style_analysis, dict):
                style_analysis_dict = style_analysis
            else:
                style_analysis_dict = {}

            nested_style = style_analysis_dict.get("style_analysis")
            if isinstance(nested_style, dict):
                style_analysis_dict = nested_style

            if not style_analysis_dict and not messages:
                logger.debug(
                    f"群组 {group_id} 没有风格分析结果且没有消息，跳过风格学习记录保存"
                )
                return

            expression_patterns = style_analysis_dict.get("expression_patterns", [])
            expression_patterns = self.filter_expression_patterns(expression_patterns)

            if expression_patterns:
                await self.save_expression_patterns(
                    group_id,
                    expression_patterns,
                    persona_id=persona_id,
                )

            few_shots_content = ""
            if expression_patterns:
                few_shots_content = self.build_few_shots_from_patterns(
                    expression_patterns
                )

            if not few_shots_content and messages:
                few_shots_content = f"基于 {len(messages)} 条对话消息的风格学习"

            learned_patterns = []
            for pattern in expression_patterns[:10]:
                learned_patterns.append(
                    {
                        "situation": pattern.get("situation", ""),
                        "expression": pattern.get("expression", ""),
                        "weight": pattern.get("weight", 1.0),
                        "confidence": pattern.get("confidence", 0.8),
                    }
                )

            confidence_score = (
                quality_metrics.consistency_score
                if quality_metrics and hasattr(quality_metrics, "consistency_score")
                else 0.75
            )
            del confidence_score  # Stored review currently derives status from patterns.

            pattern_count = len(learned_patterns) if learned_patterns else 0
            message_count = len(messages) if messages else 0
            description = (
                f"群组 {group_id} 的对话风格学习结果"
                f"（处理 {message_count} 条消息，提取 {pattern_count} 个表达模式）"
            )

            try:
                async with self.db_manager.get_session() as session:
                    from ...models.orm.learning import StyleLearningReview

                    current_timestamp = time.time()
                    has_patterns = bool(learned_patterns)

                    review = StyleLearningReview(
                        type=UPDATE_TYPE_STYLE_LEARNING,
                        group_id=group_id,
                        timestamp=current_timestamp,
                        learned_patterns=json.dumps(
                            learned_patterns, ensure_ascii=False
                        ),
                        few_shots_content=few_shots_content,
                        status="pending" if has_patterns else "approved",
                        description=description,
                        reviewer_comment=None if has_patterns else "自动批准（无有效对话对）",
                        review_time=None if has_patterns else current_timestamp,
                        created_at=datetime.fromtimestamp(current_timestamp),
                        updated_at=datetime.fromtimestamp(current_timestamp),
                    )

                    session.add(review)
                    await session.commit()
                    await session.refresh(review)

                    logger.info(
                        f" 对话风格学习记录已保存 (ID: {review.id})，"
                        f"处理 {message_count} 条消息，提取 {pattern_count} 个模式"
                    )

            except Exception as exc:
                logger.error(f"保存对话风格学习记录失败: {exc}", exc_info=True)

        except Exception as exc:
            logger.error(f"保存风格学习记录失败: {exc}", exc_info=True)

    @staticmethod
    def filter_expression_patterns(
        patterns: List[Dict[str, Any]],
    ) -> List[Dict[str, Any]]:
        """Remove command/system-derived pairs before saving style samples."""
        filtered = []
        for pattern in patterns or []:
            if not isinstance(pattern, dict):
                continue
            situation = pattern.get("situation", "")
            expression = pattern.get("expression", "")
            if should_ignore_expression_sample(situation):
                continue
            if should_ignore_expression_sample(expression):
                continue
            filtered.append(pattern)
        return filtered

    @staticmethod
    def extract_groupmate_pairs(
        messages: List[Dict[str, Any]],
        group_id: str,
        *,
        max_gap_seconds: int = 180,
    ) -> List[Dict[str, Any]]:
        """Extract zero-token human-to-human response pairs."""
        timeline = sorted(
            (item for item in messages or [] if isinstance(item, dict)),
            key=lambda item: float(item.get("timestamp", 0) or 0),
        )
        pairs: List[Dict[str, Any]] = []
        now = time.time()
        seen = set()

        for current, following in zip(timeline, timeline[1:]):
            current_sender = str(current.get("sender_id", "") or "").strip()
            following_sender = str(following.get("sender_id", "") or "").strip()
            if not current_sender or not following_sender:
                continue
            if current_sender == following_sender:
                continue
            if current_sender.lower() in {"bot", "assistant", "system"}:
                continue
            if following_sender.lower() in {"bot", "assistant", "system"}:
                continue

            situation = str(current.get("message", "") or "").strip()
            expression = str(following.get("message", "") or "").strip()
            if should_ignore_expression_sample(situation, sender_id=current_sender):
                continue
            if should_ignore_expression_sample(expression, sender_id=following_sender):
                continue

            current_ts = float(current.get("timestamp", 0) or 0)
            following_ts = float(following.get("timestamp", 0) or 0)
            if current_ts and following_ts:
                gap = following_ts - current_ts
                if gap < 0 or gap > max_gap_seconds:
                    continue

            key = (situation, expression, following_sender)
            if key in seen:
                continue
            seen.add(key)
            pairs.append(
                {
                    "situation": situation[:80],
                    "expression": expression[:120],
                    "weight": 1.0,
                    "confidence": 0.75,
                    "group_id": group_id,
                    "source_user_id": following_sender,
                    "last_active_time": now,
                    "create_time": now,
                }
            )

        return pairs

    def build_few_shots_from_patterns(self, patterns: List[Dict[str, Any]]) -> str:
        """Build few-shot dialog text from expression patterns."""
        few_shots = (
            "*Here are few shots of dialogs, you need to imitate the tone of 'B' "
            "in the following dialogs to respond:\n"
        )

        for pattern in self.filter_expression_patterns(patterns)[:5]:
            situation = pattern.get("situation", "")
            expression = pattern.get("expression", "")
            if situation and expression:
                few_shots += f"A: {situation}\nB: {expression}\n\n"

        return few_shots.strip()

    async def merge_bot_messages_for_pairs(
        self, group_id: str, user_messages: List[Dict[str, Any]]
    ) -> List[Dict[str, Any]]:
        """Return the human timeline; bot output is never a style source."""
        del group_id
        return filter_learning_messages(user_messages)

    @staticmethod
    def extract_fewshot_pairs_from_merged(
        merged: List[Dict[str, Any]], group_id: str
    ) -> List[Dict[str, Any]]:
        """Compatibility wrapper for the groupmate-only extractor."""
        return ExpressionLearningModule.extract_groupmate_pairs(merged, group_id)

    async def save_expression_patterns(
        self,
        group_id: str,
        patterns: List[Dict[str, Any]],
        persona_id: str = "default",
    ) -> None:
        """Save expression patterns to the expression_patterns table."""
        try:
            if not patterns:
                return
            persona_id = normalize_persona_scope(persona_id)

            async with self.db_manager.get_session() as session:
                from ...models.orm.expression import ExpressionPattern

                current_time = time.time()
                objects = []

                for pattern in patterns:
                    situation = pattern.get("situation", "").strip()
                    expression = pattern.get("expression", "").strip()

                    if not situation or not expression:
                        continue

                    objects.append(
                        ExpressionPattern(
                            group_id=group_id,
                            persona_id=normalize_persona_scope(
                                pattern.get("persona_id"),
                                fallback=persona_id,
                            ),
                            situation=situation,
                            expression=expression,
                            weight=float(pattern.get("weight", 1.0)),
                            last_active_time=current_time,
                            create_time=current_time,
                        )
                    )

                if objects:
                    session.add_all(objects)
                    await session.commit()
                    logger.info(
                        f"已保存 {len(objects)} 个表达模式到数据库 (群组: {group_id})"
                    )

        except Exception as exc:
            logger.error(f"保存表达模式失败: {exc}", exc_info=True)

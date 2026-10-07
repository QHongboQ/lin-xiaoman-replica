"""插件命令业务逻辑实现 — admin 命令的处理体"""
import re
import time
from typing import Any, AsyncGenerator

from astrbot.api import logger
from astrbot.api.message_components import At

from ...statics.messages import CommandMessages, LogMessages
from ...utils.persona_selection import get_event_persona_scope


class PluginCommandHandlers:
    """6 个 @filter.command 命令的业务逻辑（从 main.py 提取）"""

    def __init__(
        self,
        plugin_config: Any,
        service_factory: Any,
        message_collector: Any,
        persona_manager: Any,
        progressive_learning: Any,
        affection_manager: Any,
        temporary_persona_updater: Any,
        db_manager: Any,
        llm_adapter: Any,
        remember_service: Any = None,
    ):
        self._config = plugin_config
        self._service_factory = service_factory
        self._message_collector = message_collector
        self._persona_manager = persona_manager
        self._progressive_learning = progressive_learning
        self._affection_manager = affection_manager
        self._temporary_persona_updater = temporary_persona_updater
        self._db_manager = db_manager
        self._llm_adapter = llm_adapter
        self._remember_service = remember_service
        self._force_learning_in_progress: set = set()

    # learning_status

    async def learning_status(self, event: Any) -> AsyncGenerator:
        """查看学习状态"""
        try:
            group_id = event.get_group_id() or event.get_sender_id()

            collector_stats = await self._message_collector.get_statistics(group_id)
            if collector_stats is None:
                collector_stats = {
                    "total_messages": 0,
                    "filtered_messages": 0,
                    "raw_messages": 0,
                    "unprocessed_messages": 0,
                }

            current_persona_info = await self._persona_manager.get_current_persona(group_id)
            current_persona_name = CommandMessages.STATUS_UNKNOWN
            if current_persona_info and isinstance(current_persona_info, dict):
                current_persona_name = current_persona_info.get("name", CommandMessages.STATUS_UNKNOWN)

            learning_status = await self._progressive_learning.get_learning_status()
            if learning_status is None:
                learning_status = {
                    "learning_active": False,
                    "current_session": None,
                    "total_sessions": 0,
                }

            status_info = CommandMessages.STATUS_REPORT_HEADER.format(group_id=group_id)

            persona_update_mode = (
                "PersonaManager模式"
                if self._config.use_persona_manager_updates
                else "传统文件模式"
            )
            status_info += CommandMessages.STATUS_BASIC_CONFIG.format(
                message_capture=(
                    CommandMessages.STATUS_ENABLED
                    if self._config.enable_message_capture
                    else CommandMessages.STATUS_DISABLED
                ),
                auto_learning=(
                    CommandMessages.STATUS_ENABLED
                    if self._config.enable_auto_learning
                    else CommandMessages.STATUS_DISABLED
                ),
                realtime_learning=(
                    CommandMessages.STATUS_ENABLED
                    if self._config.enable_realtime_learning
                    else CommandMessages.STATUS_DISABLED
                ),
                web_interface=(
                    CommandMessages.STATUS_ENABLED
                    if self._config.enable_web_interface
                    else CommandMessages.STATUS_DISABLED
                ),
            )

            status_info += f"\n\n 人格更新配置:\n"
            status_info += f"• 更新方式: {persona_update_mode}\n"
            if self._config.use_persona_manager_updates:
                persona_manager_updater = self._service_factory.create_persona_manager_updater()
                pm_status = " 可用" if persona_manager_updater.is_available() else " 不可用"
                status_info += f"• PersonaManager状态: {pm_status}\n"
                status_info += f"• 自动应用更新: {'启用' if self._config.auto_apply_persona_updates else '禁用'}\n"
            status_info += f"• 更新前备份: {'启用' if self._config.persona_update_backup_enabled else '禁用'}\n"

            status_info += CommandMessages.STATUS_CAPTURE_SETTINGS.format(
                target_qq=(
                    self._config.target_qq_list
                    if self._config.target_qq_list
                    else CommandMessages.STATUS_ALL_USERS
                ),
                current_persona=current_persona_name,
            )

            if self._llm_adapter:
                provider_info = self._llm_adapter.get_provider_info()
                status_info += CommandMessages.STATUS_MODEL_CONFIG.format(
                    filter_model=provider_info.get("filter", "未配置"),
                    refine_model=provider_info.get("refine", "未配置"),
                )
            else:
                status_info += CommandMessages.STATUS_MODEL_CONFIG.format(
                    filter_model="未配置框架Provider",
                    refine_model="未配置框架Provider",
                )

            current_session = learning_status.get("current_session") or {}
            status_info += CommandMessages.STATUS_LEARNING_STATS.format(
                total_messages=collector_stats.get("total_messages", 0),
                filtered_messages=collector_stats.get("filtered_messages", 0),
                style_updates=current_session.get("style_updates", 0),
                last_learning_time=current_session.get(
                    "end_time", CommandMessages.STATUS_NEVER_EXECUTED
                ),
            )

            status_info += CommandMessages.STATUS_STORAGE_STATS.format(
                raw_messages=collector_stats.get("raw_messages", 0),
                unprocessed_messages=collector_stats.get("unprocessed_messages", 0),
                filtered_messages=collector_stats.get("filtered_messages", 0),
            )

            scheduler_status = (
                CommandMessages.STATUS_RUNNING
                if learning_status.get("learning_active")
                else CommandMessages.STATUS_STOPPED
            )
            status_info += "\n\n" + CommandMessages.STATUS_SCHEDULER.format(
                status=scheduler_status
            )

            yield event.plain_result(status_info.strip())

        except Exception as e:
            logger.error(
                CommandMessages.ERROR_GET_LEARNING_STATUS.format(error=e),
                exc_info=True,
            )
            yield event.plain_result(
                CommandMessages.STATUS_QUERY_FAILED.format(error=str(e))
            )

    # start_learning

    async def start_learning(self, event: Any) -> AsyncGenerator:
        """手动启动学习"""
        try:
            group_id = event.get_group_id() or event.get_sender_id()

            stats = await self._message_collector.get_statistics(group_id)
            unprocessed_count = stats.get("unprocessed_messages", 0)

            if unprocessed_count < self._config.min_messages_for_learning:
                yield event.plain_result(
                    f" 未处理消息数量不足"
                    f"（{unprocessed_count}/{self._config.min_messages_for_learning}），"
                    f"无法开始学习"
                )
                return

            yield event.plain_result(
                f" 开始执行学习批次，处理 {unprocessed_count} 条未处理消息..."
            )

            try:
                await self._progressive_learning._execute_learning_batch(group_id, from_force_learning=True)
                yield event.plain_result(" 学习批次执行完成")
            except Exception as batch_error:
                yield event.plain_result(f" 学习批次执行失败: {str(batch_error)}")

        except Exception as e:
            logger.error(
                CommandMessages.ERROR_START_LEARNING.format(error=e), exc_info=True
            )
            yield event.plain_result(
                CommandMessages.STARTUP_FAILED.format(error=str(e))
            )

    # stop_learning

    async def stop_learning(self, event: Any) -> AsyncGenerator:
        """停止学习"""
        try:
            group_id = event.get_group_id() or event.get_sender_id()
            await self._progressive_learning.stop_learning()
            yield event.plain_result(
                CommandMessages.LEARNING_STOPPED.format(group_id=group_id)
            )
        except Exception as e:
            logger.error(
                CommandMessages.ERROR_STOP_LEARNING.format(error=e), exc_info=True
            )
            yield event.plain_result(
                CommandMessages.STOP_FAILED.format(error=str(e))
            )

    # force_learning

    async def force_learning(self, event: Any) -> AsyncGenerator:
        """强制执行一次学习周期"""
        try:
            group_id = event.get_group_id() or event.get_sender_id()
            yield event.plain_result(
                CommandMessages.FORCE_LEARNING_START.format(group_id=group_id)
            )

            if group_id in self._force_learning_in_progress:
                yield event.plain_result(
                    f" 群组 {group_id} 的强制学习正在进行中，请等待完成"
                )
                return

            self._force_learning_in_progress.add(group_id)
            try:
                await self._progressive_learning._execute_learning_batch(group_id, from_force_learning=True)
                yield event.plain_result(
                    CommandMessages.FORCE_LEARNING_COMPLETE.format(group_id=group_id)
                )
            finally:
                self._force_learning_in_progress.discard(group_id)

        except Exception as e:
            logger.error(
                CommandMessages.ERROR_FORCE_LEARNING.format(error=e), exc_info=True
            )
            yield event.plain_result(
                CommandMessages.ERROR_FORCE_LEARNING.format(error=str(e))
            )

    # remember

    async def remember(self, event: Any) -> AsyncGenerator:
        """手动记住一段对话上下文并链入表达方式和对话示例。"""
        try:
            if not self._remember_service:
                yield event.plain_result("remember 服务未初始化，请检查启动日志")
                return

            payload = self._extract_command_payload(event, "remember")
            quoted_context = self._extract_referenced_text(event)
            content = self._merge_remember_payload(quoted_context, payload)
            if not content:
                yield event.plain_result(
                    "使用方法：/remember <引用或上下文> => <期望表达示例>\n"
                    "也可只写：/remember <需要记住的上下文>"
                )
                return

            group_id = event.get_group_id() or event.get_sender_id()
            sender_id = event.get_sender_id()
            persona_id = get_event_persona_scope(event, self._config)
            result = await self._remember_service.remember(
                group_id=group_id,
                sender_id=sender_id,
                content=content,
                persona_id=persona_id,
            )

            yield event.plain_result(
                "已记住这段对话上下文，并同步到表达方式和对话示例。\n"
                f"• memory_id: {result.memory_id}\n"
                f"• exemplar_id: {result.exemplar_id or '未生成'}\n"
                f"• style_review_id: {result.style_review_id or '未生成'}"
            )

        except ValueError as e:
            yield event.plain_result(f"remember 失败：{e}")
        except Exception as e:
            logger.error(f"remember 命令处理失败: {e}", exc_info=True)
            yield event.plain_result(f"remember 失败：{str(e)}")

    async def _resolve_affection_user_name(self, event: Any, group_id: str, user_id: str) -> str:
        """优先解析群名片/群昵称，接口不可用时回退到 QQ 号。"""
        fallback = str(user_id)
        bot = getattr(event, "bot", None)
        if bot is None or not str(group_id).isdigit():
            return fallback

        try:
            info = await bot.get_group_member_info(
                group_id=int(group_id), user_id=int(user_id)
            ) or {}
            display_name = info.get("card") or info.get("nickname") or info.get("nick")
            if display_name and str(display_name).strip():
                return str(display_name).strip()
        except Exception as exc:
            logger.debug(f"解析好感度榜单群名片失败 ({group_id}/{user_id}): {exc}")

        # 群成员接口失败时，尝试获取 QQ 昵称；仍失败则保留数字 ID，保证命令一定有结果。
        try:
            info = await bot.get_stranger_info(user_id=int(user_id)) or {}
            display_name = info.get("nickname") or info.get("nick")
            if display_name and str(display_name).strip():
                return str(display_name).strip()
        except Exception as exc:
            logger.debug(f"解析好感度榜单 QQ 昵称失败 ({user_id}): {exc}")

        return fallback

    @staticmethod
    def _resolve_affection_target_id(event: Any) -> str:
        """解析 /好感度 的目标；带 At 时查询被艾特用户，否则查询发送者自己。"""
        sender_id = str(event.get_sender_id())
        try:
            self_id = str(event.get_self_id() or "")
        except Exception:
            self_id = ""
        try:
            for component in event.get_messages() or []:
                if isinstance(component, At):
                    target_id = str(getattr(component, "qq", "") or "")
                    if target_id and target_id != self_id:
                        return target_id
        except Exception:
            pass
        return sender_id

    @staticmethod
    def is_explicit_affection_status_command(event: Any) -> bool:
        """Accept only the documented explicit `/好感度` forms.

        Valid forms are `/好感度`, `/好感度 @群友`, `/好感度@群友`,
        `@群友/好感度`, and `@群友 /好感度`.  A mention of the bot itself
        is ignored for this purpose, so `@林小满 /好感度` and
        `@林小满 /好感度 @群友` work too.  We deliberately require the
        slash and exact command body: ordinary chat must never query affinity.
        """
        try:
            components = list(event.get_messages() or [])
        except Exception:
            components = []

        if components:
            non_self_at_count = 0
            text_parts = []
            try:
                self_id = str(event.get_self_id() or "")
            except Exception:
                self_id = ""
            for component in components:
                if isinstance(component, At):
                    target_id = str(getattr(component, "qq", "") or "")
                    if not target_id or target_id != self_id:
                        non_self_at_count += 1
                    continue
                text = getattr(component, "text", None)
                if text is None:
                    text = getattr(component, "content", None)
                if not isinstance(text, str):
                    return False
                text_parts.append(text)
            normalized = re.sub(r"\s+", "", "".join(text_parts))
            return normalized == "/好感度" and non_self_at_count <= 1

        try:
            raw = str(event.get_message_str() or "")
        except Exception:
            return False
        return bool(re.fullmatch(r"\s*/好感度\s*", raw))

    # affection_status

    async def affection_status(self, event: Any) -> AsyncGenerator:
        """查看自己或被艾特用户的好感度、关系阶段与当前情绪。"""
        try:
            if not self.is_explicit_affection_status_command(event):
                return
            group_id = event.get_group_id() or event.get_sender_id()
            user_id = self._resolve_affection_target_id(event)

            if not self._config.enable_affection_system:
                yield event.plain_result(CommandMessages.AFFECTION_DISABLED)
                return

            if not self._affection_manager:
                yield event.plain_result("好感度管理器未初始化，请检查启动日志")
                return

            if self._config.enable_startup_random_mood:
                current_mood = await self._affection_manager.ensure_mood_for_group(group_id)
            else:
                current_mood = await self._affection_manager.get_current_mood(group_id)

            user_affection = await self._db_manager.get_user_affection(group_id, user_id)
            user_level = user_affection["affection_level"] if user_affection else 0
            user_name = await self._resolve_affection_user_name(event, group_id, user_id)
            relationship_stage = self._affection_manager.get_relationship_stage(
                str(group_id), str(user_id), int(user_level)
            )
            daily_change = self._affection_manager.get_last_daily_affection_change(
                str(group_id), str(user_id)
            )
            daily_delta = daily_change.get("delta")
            daily_date = str(daily_change.get("date") or "")
            if daily_delta is None:
                daily_line = "昨日好感度变化：暂无日结记录"
            else:
                daily_line = f"昨日好感度变化：{int(daily_delta):+d}" + (f"（{daily_date}日结）" if daily_date else "")

            # Backend metadata belongs in the ordinary query response for
            # configured operators; it is not a separate chat command.
            actor = str(event.get_sender_id() or "")
            backend_whitelist = {
                str(value) for value in getattr(self._config, "backend_operator_whitelist", [])
            }
            backend_line = ""
            if actor in backend_whitelist:
                plot_state = self._affection_manager.get_relationship_plot_status(
                    str(group_id), str(user_id), int(user_level)
                )
                injected = str(plot_state.get("last_injected_date") or "") or "无"
                backend_line = (
                    "\n后台剧情状态："
                    f"{plot_state['gate']}｜{plot_state['label']}｜最近注入 {injected}"
                )
            stage_number = int(relationship_stage["number"])
            stage_label = str(relationship_stage["label"])
            stage_note = ""
            next_goal = "已到达当前体系的最高阶段"
            if stage_number == 1:
                next_goal = "距第 2 阶段还差 %d 点" % max(0, 15 - int(user_level))
            elif stage_number == 2:
                next_goal = "距第 3 阶段还差 %d 点" % max(0, 35 - int(user_level))
            elif stage_number == 3:
                next_goal = "距第 4 阶段还差 %d 点" % max(0, 55 - int(user_level))
            elif stage_number == 4:
                if int(user_level) >= 73 and not relationship_stage.get("tanpai_passed"):
                    next_goal = "已到第 5 阶段门槛，等待摊牌剧情通过"
                    stage_note = "（门槛已到，剧情尚未放行）"
                else:
                    next_goal = "距第 5 阶段门槛还差 %d 点" % max(0, 73 - int(user_level))
            elif stage_number == 5:
                next_goal = "距第 6 阶段还差 %d 点" % max(0, 86 - int(user_level))
            elif stage_number == 6:
                if int(user_level) >= 96 and not relationship_stage.get("stage7_unlocked"):
                    next_goal = "已到第 7 阶段门槛，等待强化剧情放行"
                    stage_note = "（门槛已到，剧情尚未放行）"
                else:
                    next_goal = "距第 7 阶段门槛还差 %d 点" % max(0, 96 - int(user_level))
            mood_type = "未知"
            mood_display = "未知"
            mood_intensity = "未知"
            mood_description = "暂无情绪描述"
            if current_mood:
                mood_enum = getattr(current_mood, "mood_type", None)
                mood_type = str(getattr(mood_enum, "value", mood_enum or "未知"))
                mood_display = str(getattr(current_mood, "display_label", "") or mood_type)
                mood_intensity = f"{float(getattr(current_mood, "intensity", 0.0)):.2f}"
                mood_description = str(getattr(current_mood, "description", "") or "暂无情绪描述")

            yield event.plain_result(
                f"用户：{user_name}\n"
                f"好感度：{user_level}/{self._config.max_user_affection}\n"
                f"{daily_line}\n"
                f"关系阶段：第 {stage_number} 阶段·{stage_label}{stage_note}\n"
                f"阶段进度：{next_goal}\n"
                "当前林小满情绪：\n"
                f"类型：{mood_display}（{mood_type}）\n"
                f"强度：{mood_intensity}\n"
                f"描述：{mood_description}{backend_line}"
            )

        except Exception as e:
            logger.error(
                CommandMessages.ERROR_GET_AFFECTION_STATUS.format(error=e),
                exc_info=True,
            )
            yield event.plain_result(
                CommandMessages.ERROR_GET_AFFECTION_STATUS.format(error=str(e))
            )

    # set_mood

    async def set_mood(self, event: Any) -> AsyncGenerator:
        """手动设置 bot 情绪（通过增量人格更新）"""
        try:
            if not self._config.enable_affection_system:
                yield event.plain_result(CommandMessages.AFFECTION_DISABLED)
                return

            if not self._temporary_persona_updater:
                yield event.plain_result("临时人格更新器未初始化，无法设置情绪")
                return

            if not self._affection_manager:
                yield event.plain_result("好感度管理器未初始化，无法设置情绪")
                return

            args = event.get_message_str().split()[1:]
            if len(args) < 1:
                yield event.plain_result(
                    "使用方法：/set_mood <mood_type>\n"
                    "可用情绪: happy, sad, excited, calm, angry, "
                    "anxious, playful, serious, nostalgic, curious"
                )
                return

            group_id = event.get_group_id() or event.get_sender_id()
            mood_type = args[0].lower()

            valid_moods = {
                "happy": "心情很好，说话比较活泼开朗，容易表达正面情感",
                "sad": "心情有些低落，说话比较温和，需要更多的理解和安慰",
                "excited": "很兴奋，说话比较有活力，对很多事情都很感兴趣",
                "calm": "心情平静，说话比较稳重，给人安全感",
                "angry": "心情不太好，说话可能比较直接，不太有耐心",
                "anxious": "有些紧张不安，说话可能比较谨慎，需要更多确认",
                "playful": "心情很调皮，喜欢开玩笑，说话比较幽默风趣",
                "serious": "比较严肃认真，说话简洁直接，专注于重要的事情",
                "nostalgic": "有些怀旧情绪，说话带有回忆色彩，比较感性",
                "curious": "对很多事情都很好奇，喜欢提问和探索新事物",
            }

            if mood_type not in valid_moods:
                yield event.plain_result(
                    f" 无效的情绪类型。支持的情绪: {', '.join(valid_moods.keys())}"
                )
                return

            mood_description = valid_moods[mood_type]

            persona_success = (
                await self._temporary_persona_updater.apply_mood_based_persona_update(
                    group_id, mood_type, mood_description
                )
            )

            # 同时在 affection_manager 中记录情绪状态
            from ...services.state import MoodType, BotMood

            affection_success = False
            try:
                mood_enum = MoodType(mood_type)
                await self._affection_manager.db_manager.save_bot_mood(
                    group_id,
                    mood_type,
                    0.7,
                    mood_description,
                    self._config.mood_persistence_hours or 24,
                )
                mood_obj = BotMood(
                    mood_type=mood_enum,
                    intensity=0.7,
                    description=mood_description,
                    start_time=time.time(),
                    duration_hours=self._config.mood_persistence_hours or 24,
                )
                self._affection_manager.current_moods[group_id] = mood_obj
                affection_success = True
            except Exception as e:
                logger.warning(f"设置 affection_manager 情绪失败: {e}")

            if persona_success:
                status_msg = f" 情绪状态已设置为: {mood_type}\n描述: {mood_description}"
                if not affection_success:
                    status_msg += "\n 注意：情绪状态可能无法在状态查询中正确显示"
                yield event.plain_result(status_msg)
            else:
                yield event.plain_result(" 设置情绪状态失败")

        except Exception as e:
            logger.error(
                CommandMessages.ERROR_SET_MOOD.format(error=e), exc_info=True
            )
            yield event.plain_result(
                CommandMessages.ERROR_SET_MOOD.format(error=str(e))
            )

    @staticmethod
    def _extract_command_payload(event: Any, command_name: str) -> str:
        message = event.get_message_str() or ""
        stripped = message.strip()
        if not stripped:
            return ""

        parts = stripped.split(maxsplit=1)
        if not parts:
            return ""
        token = parts[0].lstrip("/!#.")
        if token.lower() != command_name.lower():
            return stripped
        return parts[1].strip() if len(parts) > 1 else ""

    @classmethod
    def _merge_remember_payload(cls, quoted_context: str, payload: str) -> str:
        quoted_context = (quoted_context or "").strip()
        payload = (payload or "").strip()
        if not quoted_context:
            return payload
        if not payload:
            return quoted_context
        if cls._looks_like_pair_payload(payload):
            if payload.lstrip().startswith(("=>", "->", "→")):
                return f"{quoted_context} {payload}"
            return payload
        return f"{quoted_context} => {payload}"

    @staticmethod
    def _looks_like_pair_payload(payload: str) -> bool:
        return any(
            marker in payload
            for marker in ("=>", "->", "→", "回复：", "回答：", "回应：", "\nB:")
        )

    @classmethod
    def _extract_referenced_text(cls, event: Any) -> str:
        for getter_name in ("get_message", "get_messages", "get_raw_message"):
            getter = getattr(event, getter_name, None)
            if not callable(getter):
                continue
            try:
                text = cls._extract_text_from_candidate(getter())
            except Exception:
                continue
            if text:
                return text

        for attr_name in ("raw_event", "raw", "message_obj", "message"):
            try:
                text = cls._extract_text_from_candidate(getattr(event, attr_name, None))
            except Exception:
                continue
            if text:
                return text
        return ""

    @classmethod
    def _extract_text_from_candidate(cls, candidate: Any, depth: int = 0) -> str:
        if candidate is None or depth > 4:
            return ""
        if isinstance(candidate, str):
            return ""
        if isinstance(candidate, dict):
            for key in (
                "quote",
                "quoted_message",
                "reply",
                "reply_message",
                "referenced_message",
                "source",
            ):
                text = cls._extract_text_from_candidate(candidate.get(key), depth + 1)
                if text:
                    return text
            for key in ("text", "message", "content", "raw_message"):
                value = candidate.get(key)
                if isinstance(value, str) and value.strip():
                    return value.strip()
            return ""
        if isinstance(candidate, (list, tuple)):
            for item in candidate:
                text = cls._extract_text_from_candidate(item, depth + 1)
                if text:
                    return text
            return ""

        class_name = type(candidate).__name__.lower()
        candidate_type = str(
            getattr(candidate, "type", "")
            or getattr(candidate, "name", "")
            or getattr(candidate, "component_type", "")
        ).lower()
        is_reference = any(
            token in f"{class_name} {candidate_type}"
            for token in ("reply", "quote", "source")
        )
        if is_reference:
            for attr_name in ("text", "message", "content", "raw_message"):
                value = getattr(candidate, attr_name, None)
                if isinstance(value, str) and value.strip():
                    return value.strip()
                text = cls._extract_text_from_candidate(value, depth + 1)
                if text:
                    return text

        for attr_name in ("chain", "message", "messages", "components"):
            value = getattr(candidate, attr_name, None)
            text = cls._extract_text_from_candidate(value, depth + 1)
            if text:
                return text
        return ""

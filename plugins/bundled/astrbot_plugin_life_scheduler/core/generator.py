import asyncio
import datetime
import hashlib
import json
import random
import re
from dataclasses import asdict, dataclass
from functools import lru_cache
from pathlib import Path

from astrbot.api import logger
from astrbot.core.config.astrbot_config import AstrBotConfig
from astrbot.core.star.context import Context

from .data import ScheduleData, ScheduleDataManager

_STYLE_PREFIX_RE = re.compile(
    r"^\s*(?:【?风格】?|\[?风格\]?)\s*[:：]\s*(?P<style>.+?)(?:\n|$)"
)


@dataclass(slots=True)
class ScheduleContext:
    date_str: str
    weekday: str
    holiday: str
    persona_desc: str
    history_schedules: str
    recent_chats: str
    daily_theme: str
    mood_color: str
    outfit_style: str
    outfit_plan: str
    schedule_type: str
    fat_fish_schedule_note: str = ""
    geography_anchor: str = ""
    public_place_seed: str = ""
    wardrobe: str = ""
    image_description: str = ""
    travel_context: str = ""
    travel_mode: bool = False
    weather: str = ""
    attendance_plan: str = ""
    visual_identity_anchor: str = ""


class SchedulerGenerator:
    _STYLE_ENFORCE_RETRIES = 2
    _EMPTY_COMPLETION_RETRIES = 1
    # Older user templates contained a fixed age and a concrete school example.
    # Those leak stale role-card facts and contradict the configured privacy rule.
    # Keep this local and deterministic: the current role card remains the only
    # source of age/identity details sent to the generation model.
    _LEGACY_TEMPLATE_REPLACEMENTS = {
        "角色为 16 岁学生。": "角色的年龄、学段与生活边界以当前角色卡为准。",
        "例如日程写“河南一中画室完成一张临摹”，被问“你在哪画画”时就自然回答“在河南一中的画室”。": (
            "例如日程写“学校画室完成一张临摹”，被问“你在哪画画”时就自然回答“在学校画室”。"
        ),
    }

    _SCHEDULE_COMPLETENESS_CONTRACT = (
        "\n\n## 日程完整性（硬性校验）\n"
        "- 日程共 7-12 条带时间事项，且早餐、午餐、晚餐必须各自独占一条；"
        "三餐要写明当天实际吃的食物和所在场景，不写饭量。\n"
        "- 工作日必须跟随大肥鱼配置的实际峰谷窗口：首段高峰开始前安排早餐，"
        "第一段高峰结束至第二段高峰开始之间安排午餐，最后一段高峰结束后安排晚餐。"
        "不要把三餐死写成普通作息钟点；休息日按当天自然作息安排。\n"
        "- 低峰窗口可安排可互动的小事；高峰窗口必须是出门、上课、补课、"
        "游戏或其他忙碌活动，合计仍须保持 7-12 条。\n"
        "- 小事必须具体、带一点古灵精怪但可现实发生：例如明确的游戏与进度、"
        "正在看的作品/桥段、在公共场所遇到的一件小插曲、与同龄朋友的小玩笑。"
        "不得用“出去玩、忙点事、随便逛、看剧、打游戏”这类空话代替。\n"
        "- 工作日大肥鱼高峰时段必须对应一个已安排的忙碌活动；周末和法定节假日"
        "按真实休息、探亲、旅行、宅家或约玩安排，绝不伪造上课。\n"
    )

    _DEFAULT_VISUAL_IDENTITY_ANCHOR = (
        "林小满的固定外观：奶油金色长发，扎成高双马尾；略厚刘海、发梢微乱、"
        "一撮压不下去的呆毛；绯红色上挑眼，左眼下有小泪痣，身形娇小纤细。"
        "发色与核心五官是长期固定事实，日程、穿搭、播报和自拍提示均不得改成黑发、"
        "棕发、白发或其他发色。当天只能变化服装、发饰、妆容、场景与活动。"
    )
    _CONTRADICTORY_HAIR_RE = re.compile(
        r"(?:黑发|黑色(?:的)?(?:长)?发|乌黑(?:的)?(?:长)?发|棕发|棕色(?:的)?(?:长)?发|"
        r"白发|银发|蓝发|粉发|紫发|绿发)"
    )

    def __init__(
        self,
        context: Context,
        config: AstrBotConfig,
        data_mgr: ScheduleDataManager,
        wardrobe_mgr=None,
    ):
        self.context = context
        self.config = config
        self.data_mgr = data_mgr
        self.wardrobe_mgr = wardrobe_mgr
        self._ensure_prompt_template_default()

        self._gen_lock = asyncio.Lock()
        self._generating = False

    async def generate_schedule(
        self,
        date: datetime.datetime | None = None,
        umo: str | None = None,
        extra: str | None = None,
        image_paths: list[str] | None = None,
    ) -> ScheduleData:
        async with self._gen_lock:
            if self._generating:
                raise RuntimeError("schedule_generating")
            self._generating = True

        data: ScheduleData | None = None
        date = date or datetime.datetime.now()
        date_str = date.strftime("%Y-%m-%d")
        try:
            logger.info(f"正在生成 {date_str} 的日程...")
            manual_extra = self._normalize_extra(extra)
            image_description = ""
            if image_paths:
                image_description = await self._describe_images(
                    image_paths,
                    user_text=manual_extra,
                    sid=f"life_scheduler_vision_{date_str}",
                )
            ctx = await self._collect_context(date, umo, image_description)
            prompt = self._build_prompt(ctx, manual_extra)
            sid_base = f"life_scheduler_gen_{date_str}"
            content = await self._call_llm(prompt, sid=f"{sid_base}_0")

            payload = self._extract_json_obj(content)
            enforce_style = not manual_extra and not image_description
            ok, reason = self._validate_payload(
                payload,
                ctx,
                enforce_style=enforce_style,
                manual_extra=manual_extra,
            )
            for attempt in range(1, self._STYLE_ENFORCE_RETRIES + 1):
                if ok:
                    break
                if manual_extra:
                    repair_prompt = self._build_manual_repair_prompt(
                        ctx, content, reason, manual_extra
                    )
                else:
                    repair_prompt = self._build_style_repair_prompt(
                        ctx, content, reason
                    )
                content = await self._call_llm(
                    repair_prompt, sid=f"{sid_base}_{attempt}"
                )
                payload = self._extract_json_obj(content)
                ok, reason = self._validate_payload(
                    payload,
                    ctx,
                    enforce_style=enforce_style,
                    manual_extra=manual_extra,
                )

            if not ok or not payload:
                raise ValueError(f"模型未遵循生成约束：{reason}")

            data = self._to_schedule_data(
                payload,
                date_str,
                ctx,
                manual_extra=manual_extra,
                image_description=image_description,
            )
            self.data_mgr.set(data)
            logger.info(
                f"日程生成成功: {json.dumps(asdict(data), ensure_ascii=False, indent=2)}"
            )
            return data
        except Exception as e:
            logger.error(f"日程生成失败: {e}")
            return ScheduleData(
                date=date_str, outfit="生成失败", schedule="生成失败", status="failed"
            )
        finally:
            async with self._gen_lock:
                self._generating = False
            if data:
                self.data_mgr.set(data)

    # ---------- context ----------

    async def _collect_context(
        self,
        data: datetime.datetime,
        umo: str | None,
        image_description: str = "",
    ) -> ScheduleContext:
        effective_umo = self._resolve_reference_umo(umo)
        logger.debug(f"[LLM] UMO 上下文注入：{effective_umo or '未配置'}")
        travel_context, travel_mode = await self._get_travel_context(data.date())
        weather = await self._get_weather_summary(data.date(), travel_context)
        return ScheduleContext(
            date_str=data.strftime("%Y年%m月%d日"),
            weekday=self._weekday(data),
            holiday=self._get_holiday_info(data.date()),
            fat_fish_schedule_note=self._get_fat_fish_schedule_note(data),
            geography_anchor=str(self.config.get("geography_anchor", "") or "").strip(),
            public_place_seed=str(self.config.get("public_place_seed", "") or "").strip(),
            persona_desc=await self._get_persona(),
            history_schedules=self._get_history(data),
            recent_chats=await self._get_recent_chats(effective_umo),
            wardrobe=(
                self.wardrobe_mgr.for_prompt()
                if self.wardrobe_mgr is not None
                else "（衣柜为空）"
            ),
            image_description=image_description,
            travel_context=travel_context,
            travel_mode=travel_mode,
            weather=weather,
            attendance_plan=self._attendance_plan(data.date()),
            visual_identity_anchor=(
                str(self.config.get("visual_identity_anchor", "") or "").strip()
                or self._DEFAULT_VISUAL_IDENTITY_ANCHOR
            ),
            **self._pick_diversity(),
        )

    def _attendance_plan(self, day: datetime.date) -> str:
        """Stable local 50/50 draw; retries for one date must never flip it."""
        if not self._is_fat_fish_peak_day(day):
            return "休息日：不生成上学安排，按真实假日或周末生活规划"
        value = int(hashlib.sha256(f"linxiaoman-attendance|{day.isoformat()}".encode()).hexdigest()[:8], 16)
        return (
            "上学日：今天正常上学，高峰时段由学校活动占用"
            if value % 2 == 0
            else "翘课日：今天不去学校，高峰时段必须由具体的外出、游戏、画画或其他长活动占用"
        )

    def _resolve_reference_umo(self, umo: str | None) -> str | None:
        """Resolve the current conversation or the configured fallback session.

        Args:
            umo: Session origin for the current event.

        Returns:
            The session origin used for recent-chat context, or None.
        """
        candidate = str(umo or "").strip()
        if candidate:
            return candidate
        default_umo = str(self.config.get("default_reference_umo", "") or "").strip()
        return default_umo or None

    def _weekday(self, data):
        return ["星期一", "星期二", "星期三", "星期四", "星期五", "星期六", "星期日"][
            data.weekday()
        ]

    def _get_holiday_info(self, date: datetime.date) -> str:
        """获取节日信息（中国）"""
        try:
            import holidays

            cn_holidays = holidays.CN()
            holiday_name = cn_holidays.get(date)
            if holiday_name:
                return f"今天是 {holiday_name}"
        except Exception:
            return ""
        return ""

    def _fat_fish_peak_weekdays(self) -> set[int]:
        """Read the service's actual peak-day policy, with a safe weekday fallback."""
        config_path = (
            Path(__file__).resolve().parents[3]
            / "config"
            / "astrbot_plugin_fat_fish_wallet_config.json"
        )
        try:
            payload = json.loads(config_path.read_text(encoding="utf-8-sig"))
            raw = str(payload.get("peak_weekdays", "0,1,2,3,4") or "")
            days = {int(item.strip()) for item in raw.split(",") if item.strip()}
            valid = {day for day in days if 0 <= day <= 6}
            if valid:
                return valid
        except Exception:
            pass
        return {0, 1, 2, 3, 4}

    def _is_fat_fish_peak_day(self, day: datetime.date) -> bool:
        """Reports exist only on a real FatFish peak weekday, never on holidays."""
        return not self._get_holiday_info(day) and day.weekday() in self._fat_fish_peak_weekdays()

    def _get_fat_fish_schedule_note(self, data: datetime.datetime) -> str:
        """Read Fat Fish windows so generated life plans and service reports share one clock."""
        config_path = Path(__file__).resolve().parents[3] / "config" / "astrbot_plugin_fat_fish_wallet_config.json"
        try:
            payload = json.loads(config_path.read_text(encoding="utf-8-sig"))
            periods = str(payload.get("peak_periods", "09:00-12:00,14:00-18:30"))
            weekdays = str(payload.get("peak_weekdays", "0,1,2,3,4"))
        except Exception:
            periods, weekdays = "09:00-12:00,14:00-18:30", "0,1,2,3,4"
        holiday = self._get_holiday_info(data.date())
        if holiday:
            return (
                f"今天是{holiday}。大肥鱼在法定休息日不执行工作日高峰暂停，"
                "不安排上学/放学式服务播报；日程应是年龄相称的假日安排。"
            )
        if data.weekday() not in self._fat_fish_peak_weekdays():
            return (
                "今天是大肥鱼的非高峰休息日，全天保持低峰服务；"
                "不安排工作日上学/放学式四节点播报，日程应是自然的周末休闲安排。"
            )
        return (
            f"大肥鱼工作日服务高峰：{periods}（生效星期：{weekdays}）。"
            "日程需与四个服务节点自然一致：09:00 与 14:00 是出门/上课/补课等忙碌节点，"
            "12:00 与 18:30 是午间或放学后可恢复聊天的节点。"
        )

    def _fat_fish_peak_periods(self) -> list[tuple[int, int]]:
        """Read actual FatFish windows as minutes since midnight.

        The same config drives both the service pause and meal placement, so a
        user changing FatFish periods never leaves the scheduler on stale
        hard-coded meal hours.
        """
        config_path = (
            Path(__file__).resolve().parents[3]
            / "config"
            / "astrbot_plugin_fat_fish_wallet_config.json"
        )
        raw = "09:00-12:00,14:00-18:30"
        try:
            payload = json.loads(config_path.read_text(encoding="utf-8-sig"))
            raw = str(payload.get("peak_periods", raw) or raw)
        except Exception:
            pass
        periods: list[tuple[int, int]] = []
        for item in raw.split(","):
            try:
                start, end = item.strip().split("-", 1)
                sh, sm = (int(value) for value in start.split(":", 1))
                eh, em = (int(value) for value in end.split(":", 1))
                lower, upper = sh * 60 + sm, eh * 60 + em
                if 0 <= lower < upper <= 24 * 60:
                    periods.append((lower, upper))
            except (TypeError, ValueError):
                continue
        return periods or [(9 * 60, 12 * 60), (14 * 60, 18 * 60 + 30)]

    @staticmethod
    def _normal_travel_context() -> tuple[str, bool]:
        return ("常驻模式：今天没有已确认的旅行安排。所有外出活动必须位于深圳市罗湖区，并且只能使用公共地点种子；即使是节假日也不得随机编造外地旅行。", False)

    def _configured_travel_context(self, day: datetime.date) -> tuple[str, bool] | None:
        """Read an optional explicit trip override before considering automation."""
        raw_plans = self.config.get("travel_itineraries", [])
        if not isinstance(raw_plans, list):
            return None
        for item in raw_plans:
            if not isinstance(item, dict):
                continue
            try:
                start = datetime.date.fromisoformat(str(item.get("start_date", "")))
                end = datetime.date.fromisoformat(str(item.get("end_date", "")))
            except (TypeError, ValueError):
                continue
            if start > end or not start <= day <= end:
                continue
            city = str(item.get("city", "")).strip()
            raw_places = item.get("places", [])
            places = ([line.strip() for line in raw_places.splitlines() if line.strip()] if isinstance(raw_places, str) else [str(value).strip() for value in raw_places if str(value).strip()] if isinstance(raw_places, list) else [])
            if not city or not places:
                logger.warning("旅行地点包不完整，忽略该条：%s", item)
                continue
            companions = str(item.get("companions", "家人或同龄朋友")).strip() or "家人或同龄朋友"
            source = str(item.get("source", "用户确认")).strip() or "用户确认"
            return self._format_travel_context(start, end, city, companions, "；".join(places), source)
        return None

    def _travel_cache_path(self) -> Path:
        return self.data_mgr._path.parent / "travel_cache.json"

    def _read_travel_cache(self) -> dict:
        try:
            raw = json.loads(self._travel_cache_path().read_text(encoding="utf-8"))
            return raw if isinstance(raw, dict) else {}
        except (OSError, ValueError, TypeError):
            return {}

    def _write_travel_cache(self, payload: dict) -> None:
        path = self._travel_cache_path()
        path.parent.mkdir(parents=True, exist_ok=True)
        tmp = path.with_suffix(".tmp")
        tmp.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")
        tmp.replace(path)

    @staticmethod
    def _format_travel_context(start: datetime.date, end: datetime.date, city: str, companions: str, candidates: str, source: str) -> tuple[str, bool]:
        return ("旅行模式（已经确定，不要另换城市）：\n"
                f"- 行程日期：{start.isoformat()} 至 {end.isoformat()}\n"
                f"- 目的城市：{city}\n"
                f"- 同行对象：{companions}\n"
                f"- 已检索的公开地点候选：{candidates}\n"
                f"- 来源：{source}\n"
                "- 当天必须延续这次旅行的城市、同行者和地点事实。只可使用候选中能明确识别的公开地点；不写酒店地址、住址、学校、票据或任何精确行程。", True)

    def _holiday_block(self, day: datetime.date) -> tuple[datetime.date, datetime.date] | None:
        if not self._get_holiday_info(day):
            return None
        start = day
        while self._get_holiday_info(start - datetime.timedelta(days=1)):
            start -= datetime.timedelta(days=1)
        end = day
        while self._get_holiday_info(end + datetime.timedelta(days=1)):
            end += datetime.timedelta(days=1)
        return start, end

    async def _get_travel_context(self, day: datetime.date) -> tuple[str, bool]:
        """Resolve an explicit or one-shot AnySearch-backed holiday trip."""
        explicit = self._configured_travel_context(day)
        if explicit is not None:
            return explicit
        cached = self._read_travel_cache()
        try:
            start = datetime.date.fromisoformat(str(cached.get("start_date", "")))
            end = datetime.date.fromisoformat(str(cached.get("end_date", "")))
        except (TypeError, ValueError):
            start = end = None
        if start and end and start <= day <= end:
            city = str(cached.get("city", "")).strip()
            candidates = str(cached.get("candidates", "")).strip()
            if city and candidates:
                return self._format_travel_context(start, end, city, str(cached.get("companions", "家人或同龄朋友")).strip() or "家人或同龄朋友", candidates, str(cached.get("source", "AnySearch 缓存")).strip() or "AnySearch 缓存")
        block = self._holiday_block(day)
        if not block:
            return self._normal_travel_context()
        block_start, block_end = block
        if day != block_start or (block_end - block_start).days + 1 < 2:
            return self._normal_travel_context()
        probability = max(0.0, min(float(self.config.get("travel_holiday_probability", 0.18) or 0), 1.0))
        roll = int(hashlib.sha256(block_start.isoformat().encode()).hexdigest()[:8], 16) / 0xFFFFFFFF
        if roll >= probability:
            return self._normal_travel_context()
        pool = self.config.get("travel_city_pool", [])
        cities = [str(city).strip() for city in pool if str(city).strip()] if isinstance(pool, list) else []
        if not cities:
            return self._normal_travel_context()
        city = cities[int(hashlib.sha256((block_start.isoformat() + "city").encode()).hexdigest()[:8], 16) % len(cities)]
        candidates = await self._search_trip_candidates(city)
        if not candidates:
            logger.warning("AnySearch 未返回可用旅行候选，已保持常驻模式：%s", city)
            return self._normal_travel_context()
        end = min(block_end, block_start + datetime.timedelta(days=2))
        payload = {"start_date": block_start.isoformat(), "end_date": end.isoformat(), "city": city, "companions": "家人或同龄朋友", "candidates": candidates, "source": "AnySearch 假期单次检索缓存"}
        self._write_travel_cache(payload)
        logger.info("假期旅行候选已通过 AnySearch 缓存：%s 至 %s，%s", block_start, end, city)
        return self._format_travel_context(block_start, end, city, payload["companions"], candidates, payload["source"])

    def _weather_cache_path(self) -> Path:
        return self.data_mgr._path.parent / "weather_cache.json"

    def _read_weather_cache(self) -> dict:
        try:
            payload = json.loads(self._weather_cache_path().read_text(encoding="utf-8"))
            return payload if isinstance(payload, dict) else {}
        except (OSError, ValueError, TypeError):
            return {}

    def _write_weather_cache(self, payload: dict) -> None:
        path = self._weather_cache_path()
        path.parent.mkdir(parents=True, exist_ok=True)
        tmp = path.with_suffix(".tmp")
        tmp.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")
        tmp.replace(path)

    @staticmethod
    def _weather_city(travel_context: str) -> str:
        match = re.search(r"目的城市：([^\n]+)", str(travel_context or ""))
        return match.group(1).strip() if match else "深圳市罗湖区"

    async def _get_weather_summary(
        self, day: datetime.date, travel_context: str = ""
    ) -> str:
        """Fetch at most once per date/city through the installed free weather plugin.

        The stored one-line forecast becomes input only for daily schedule creation;
        it is never fetched while replying in a chat, and a network failure simply
        leaves the model without weather facts instead of inventing any.
        """
        city = self._weather_city(travel_context)
        key = f"{day.isoformat()}::{city}"
        cache = self._read_weather_cache()
        cached = cache.get(key)
        if isinstance(cached, str) and cached.strip():
            return cached.strip()[:360]
        try:
            metadata = self.context.get_registered_star("astrbot_plugin_nyweather")
            plugin = getattr(metadata, "star_cls", None) or metadata
            getter = getattr(plugin, "_query_weather_text", None)
            if not callable(getter):
                return ""
            result = getter(city, 2)
            if hasattr(result, "__await__"):
                result = await result
            summary = str(result or "").strip().splitlines()[0][:360]
            if summary:
                cache[key] = summary
                self._write_weather_cache(cache)
            return summary
        except Exception as exc:
            logger.debug("天气日程事实未获取，保持无天气注入: %s", exc)
            return ""

    async def _search_trip_candidates(self, city: str) -> str:
        """Use AstrBot's built-in AnySearch exactly once for a holiday trip."""
        try:
            from astrbot.core.tools.web_search_tools import _anysearch_search
            root_config = json.loads(Path("/AstrBot/data/cmd_config.json").read_text(encoding="utf-8"))
            settings = root_config.get("provider_settings", {})
            results = await _anysearch_search(settings if isinstance(settings, dict) else {}, {"query": f"{city} 适合学生和家人假期游玩的公共景点 博物馆 公园 步行街", "max_results": 4, "format": "json", "zone": "cn", "language": "zh-CN"})
        except Exception as exc:
            logger.warning("AnySearch 假期旅行检索失败：%s", exc)
            return ""
        leads = []
        for result in results[:4]:
            title = str(getattr(result, "title", "")).strip()
            snippet = re.sub(r"\s+", " ", str(getattr(result, "snippet", "")).strip())[:180]
            if title:
                leads.append(f"{title}（{snippet}）" if snippet else title)
        return "；".join(leads)[:900]

    def _pick_diversity(self) -> dict:
        pool = self.config["pool"]
        wardrobe_entries = (
            self.wardrobe_mgr.all() if self.wardrobe_mgr is not None else []
        )
        outfit_plan = (
            random.choice(wardrobe_entries)["description"]
            if wardrobe_entries
            else "衣柜为空；请根据人设自由设计完整的服装、鞋袜、配饰、发型和妆容。"
        )
        return {
            "daily_theme": random.choice(pool["daily_themes"]),
            "mood_color": random.choice(pool["mood_colors"]),
            "outfit_style": self._extract_style_from_plan(outfit_plan),
            "outfit_plan": outfit_plan,
            "schedule_type": random.choice(pool["schedule_types"]),
        }

    @staticmethod
    def _extract_style_from_plan(outfit_plan: str) -> str:
        """Extract a short style label from a detailed wardrobe plan.

        Args:
            outfit_plan: Selected wardrobe description.

        Returns:
            A concise style label used by the existing schedule data contract.
        """
        match = re.search(r"(?:整体风格|风格)\s*[:：]\s*([^；;\n。]+)", outfit_plan)
        if match:
            return match.group(1).strip()
        return "自由搭配" if "衣柜为空" in outfit_plan else "衣柜方案"

    def _extract_style_from_outfit(self, outfit: str) -> str:
        if not outfit:
            return ""
        m = _STYLE_PREFIX_RE.match(outfit.strip())
        if not m:
            return ""
        return (m.group("style") or "").strip()

    def _get_history(self, today: datetime.date) -> str:
        items: list[str] = []

        days = self.config.get("reference_history_days", 0)
        if days <= 0:
            return "（无历史记录）"

        for i in range(1, days + 1):
            date = today - datetime.timedelta(days=i)
            data = self.data_mgr.get(date)
            if not data or data.status != "ok":
                continue

            outfit = data.outfit[:40]
            schedule = data.schedule[:60]
            style = (
                getattr(data, "outfit_style", "") or ""
            ).strip() or self._extract_style_from_outfit(data.outfit)

            if style:
                items.append(
                    f"[{date.strftime('%Y-%m-%d')}] 风格：{style} 穿搭：{outfit} 日程：{schedule}"
                )
            else:
                items.append(
                    f"[{date.strftime('%Y-%m-%d')}] 穿搭：{outfit} 日程：{schedule}"
                )

        return "\n".join(items) if items else "（无历史记录）"

    async def _get_recent_chats(
        self, umo: str | None = None, count: int | None = None
    ) -> str:
        """获取指定会话的最近聊天记录"""
        count = count or self.config["reference_recent_count"]

        if not umo or not count:
            return "无近期对话"

        try:
            cid = await self.context.conversation_manager.get_curr_conversation_id(umo)
            if not cid:
                return "无最近对话记录"

            conv = await self.context.conversation_manager.get_conversation(umo, cid)
            if not conv or not conv.history:
                return "无最近对话记录"

            history = json.loads(conv.history)

            recent = history[-count:] if count > 0 else []

            formatted = []
            for msg in recent:
                role = msg.get("role", "unknown")
                content = msg.get("content", "")
                if role == "user":
                    formatted.append(f"用户: {content}")
                elif role == "assistant":
                    formatted.append(f"我: {content}")

            return "\n".join(formatted)

        except Exception as e:
            logger.error(f"Failed to get recent chats for {umo}: {e}")
            return "获取对话记录失败"

    async def _get_persona(self) -> str:
        try:
            p = await self.context.persona_manager.get_default_persona_v3()
            return p.get("prompt") if isinstance(p, dict) else getattr(p, "prompt", "")
        except Exception:
            return "你是一个热爱生活、情感细腻的AI伙伴。"

    # ---------- llm ----------
    @staticmethod
    def _normalize_extra(extra: str | None) -> str:
        return str(extra or "").strip()

    @staticmethod
    def _normalize_requirement_text(text: str) -> str:
        return re.sub(r"[\s\"'“”‘’`，,。.!！?？:：;；、（）()\[\]【】<>《》]", "", text)

    _NEGATIVE_MARKER_RE = re.compile(
        r"不要再|不要|不能|不许|不想|不用|不需要|别再|别|避免|禁止|拒绝"
    )
    _OUTFIT_TERM_RE = re.compile(
        r"吊带裙|吊带衫|连衣裙|半身裙|牛仔裤|黑丝|白丝|丝袜|吊带|短裙|长裙|裙|裤|袜|鞋|靴|衣|衫|外套|内衣|内裤|帽|包|耳钉|项链|手链|口红|妆|黑色|白色|红色|粉色|蓝色|绿色|黄色|紫色|灰色|米色|棕色|金色|银色|风格|穿搭"
    )
    _SCHEDULE_TERM_RE = re.compile(
        r"下午茶|咖啡店|奶茶店|电影院|吃饭|睡觉|看书|出门|上班|上课|约会|咖啡|奶茶|电影|逛街|散步|阅读|学习|工作|健身|运动|睡|洗澡|拍照|做饭|烘焙|画画|游戏|瑜伽|公园|学校|公司|商场|餐厅|居酒屋|便利店|吃|喝"
    )
    _NEGATED_TERM_PREFIX_RE = re.compile(
        r"(?:不要再|不用再|不需要再|不想再|不能再|不许再|别再)$|"
        r"不(?:再|要|想|用|需要|许|去|穿|戴|安排|进行|做)?$|"
        r"别(?:再|去|穿|戴|安排|进行|做)?$|"
        r"避免$|禁止$|拒绝$|无$|没有$"
    )

    @classmethod
    def _strip_manual_term(cls, text: str) -> str:
        item = cls._normalize_requirement_text(text)
        item = cls._NEGATIVE_MARKER_RE.sub("", item)
        item = re.sub(
            r"^(?:今天|今日|今儿|这次|请|麻烦|帮我|给我|让她|要|想|希望|必须|一定要|特别|注意|日程|安排|一个|一场|一份|一下|穿搭|穿着|穿|戴|换上|搭配|去|到|在|做|进行|来|搞)+",
            "",
            item,
        )
        item = re.sub(r"(?:一点|一些|一下|日程|安排)$", "", item)
        return item

    @classmethod
    def _append_requirement(
        cls, requirements: dict[str, list[str]], bucket: str, item: str
    ) -> None:
        if len(item) >= 2 and item not in requirements[bucket]:
            requirements[bucket].append(item)

    @classmethod
    def _extract_known_terms(cls, item: str, term_re: re.Pattern) -> list[str]:
        terms: list[str] = []
        for match in term_re.finditer(item):
            term = match.group(0)
            if term not in terms:
                terms.append(term)
        return terms

    @classmethod
    def _append_forbidden_requirement(
        cls, requirements: dict[str, list[str]], item: str
    ) -> None:
        terms = cls._extract_known_terms(item, cls._OUTFIT_TERM_RE)
        for term in cls._extract_known_terms(item, cls._SCHEDULE_TERM_RE):
            if term not in terms:
                terms.append(term)
        if terms:
            for term in terms:
                cls._append_requirement(requirements, "forbidden", term)
            return
        cls._append_requirement(requirements, "forbidden", item)

    @classmethod
    def _append_positive_requirement(
        cls, requirements: dict[str, list[str]], item: str
    ) -> None:
        outfit_terms = cls._extract_known_terms(item, cls._OUTFIT_TERM_RE)
        schedule_terms = cls._extract_known_terms(item, cls._SCHEDULE_TERM_RE)

        for term in outfit_terms:
            cls._append_requirement(requirements, "required_outfit", term)
        for term in schedule_terms:
            cls._append_requirement(requirements, "required_schedule", term)

        if not outfit_terms and not schedule_terms:
            cls._append_requirement(requirements, "required_any", item)

    @classmethod
    def _extract_manual_requirements(cls, extra: str) -> dict[str, list[str]]:
        requirements = {
            "required_outfit": [],
            "required_schedule": [],
            "required_any": [],
            "forbidden": [],
        }
        segments = re.split(r"[，,。.!！?？:：;；、\n]", extra)
        for segment in segments:
            if not segment:
                continue
            is_negative = bool(cls._NEGATIVE_MARKER_RE.search(segment))
            parts = re.split(r"和|与|以及|并且|然后|再", segment)
            for part in parts:
                item = cls._strip_manual_term(part)
                if len(item) < 2:
                    continue
                if is_negative:
                    cls._append_forbidden_requirement(requirements, item)
                else:
                    cls._append_positive_requirement(requirements, item)
        for key, value in requirements.items():
            requirements[key] = value[:8]
        return requirements

    def _build_prompt(self, ctx: ScheduleContext, extra: str | None = None) -> str:
        extra = self._normalize_extra(extra)
        ctx_dict = asdict(ctx)  # 实际有的字段
        has_user_outfit = bool(extra or ctx.image_description)
        if has_user_outfit:
            ctx_dict["outfit_style"] = "用户指定"
            ctx_dict["outfit_plan"] = "用户本次指定"
            ctx_dict["schedule_type"] = "用户指定"

        template = self._get_prompt_template()
        tmpl_vars = set(re.findall(r"\{(\w+)\}", template))
        for var in tmpl_vars:
            if re.match(r"^r\d+$", var):
                ctx_dict[var] = str(random.randint(1, 100))
        missing = tmpl_vars - ctx_dict.keys()
        if missing:
            logger.warning(
                f"prompt 模板存在 ScheduleContext 未提供的字段：{missing}| 已自动替换成空串"
            )

        # 统一补空值，避免 KeyError
        for k in missing:
            ctx_dict[k] = ""
        prompt = self._render_prompt_template(template, ctx_dict)
        prompt += self._SCHEDULE_COMPLETENESS_CONTRACT
        prompt += (
            "\n\n## 固定视觉身份（最高优先级，不是可选穿搭）\n"
            f"{ctx.visual_identity_anchor}\n"
            "- outfit 中若提及头发，必须与以上固定外观完全一致；不得用随机发色覆盖它。\n"
            "- 发饰、发型的变化只能在奶油金高双马尾的基础上进行，例如更换发圈、蝴蝶结、发夹；"
            "不得改发色、剪成短发或改成单马尾。\n"
        )
        prompt += (
            "\n\n## 今日出勤抽签（本地结果，不得改写）\n"
            f"{ctx.attendance_plan}\n"
            "- 工作日若抽到翘课，高峰时段仍必须被一项具体、持续的活动占满；不得把系统高峰写成空闲聊天。\n"
            "- 同一次 JSON 同时返回 event_reports，挑选日程中值得在群里说的 1-3 个节点；"
            "每项包含 id、time、offset、text。time 必须取自日程，offset 只能是 before 或 after，"
            "text 是已经润色好的林小满群聊口吻，不超过 60 字。不要为吃饭、洗漱等琐事逐条播报。\n"
            "- JSON 顶层字段必须包含 outfit_style、outfit、schedule、attendance_plan、peak_reports、event_reports。"
        )
        prompt += (
            "\n\n## 未成年人穿搭硬规则\n"
            "今日穿搭必须适龄、日常、舒适且非性感。不写内衣或吊带外露，"
            "不使用低领、故意滑肩、透视、贴身特写等描述；自拍也不得通过服装或镜头突出身体部位。"
        )
        if ctx.weather:
            prompt += (
                "\n\n## 今日已获取的天气事实\n"
                f"{ctx.weather}\n"
                "- 仅把它用于安排外出、室内活动和穿搭的合理性；不要把天气包装成亲眼实况，"
                "也不要在与天气无关的聊天里主动汇报。\n"
            )
        prompt += (
            "\n\n## 地理状态（最高优先级）\n"
            f"{ctx.travel_context}\n"
            "- 不得声称实时浏览过百度、贴吧、小红书、地图或任何网页。地点只能来自上面的已核实地点包或常驻公共地点种子。\n"
            "- 若为旅行模式，连续多日必须使用同一旅行地点包；若为常驻模式，绝不跨城旅行。\n"
        )

        if not has_user_outfit:
            prompt += (
                "\n\n## 今日选定的衣柜方案（必须落实）\n"
                f"{ctx.outfit_plan}\n"
                "- 这是今日唯一的穿搭基准，outfit 必须落实其中已明确的服装、鞋袜、配饰、发型、妆容和穿戴约束。\n"
                "- 标记为‘未明确’的项可以按整体风格补全，不得换掉已明确的单品。\n"
            )

        if ctx.image_description:
            prompt += (
                "\n\n## 用户本次提供的穿搭图片转写（最高优先级）\n"
                f"{ctx.image_description}\n"
                "- 这是用户指定的参考穿搭，必须落实到今日 outfit 中。\n"
                "- 详细描述可见的上衣、下装、外套、鞋袜、配饰、颜色、材质、版型和整体风格。\n"
                "- 图片看不清或无法确认的细节不要臆造，可以使用‘图片中未明确’。\n"
            )

        if extra:
            prompt += (
                "\n\n## ✅ 用户补充强制约束（最高优先级，必须严格遵循）\n"
                f"- 用户补充要求：{extra}\n"
                "- 用户补充要求优先级高于今日主题、心情色彩、穿搭风格、日程类型和历史日程参考。\n"
                "- 如果用户补充要求与上文随机创意池或模板中的穿搭风格冲突，必须以用户补充要求为准。\n"
                "- 不得忽略、替换、弱化或用随机创意池覆盖用户补充要求中的具体衣物、场景和活动。\n"
                "- 你必须只输出 JSON 对象本体（不要 Markdown/代码块/解释）。\n"
                '- JSON 必须包含字段 "outfit_style"、"outfit"、"schedule"。\n'
                '- 当用户指定了具体穿搭时，"outfit" 必须直接包含这些具体穿搭元素。\n'
            )
        elif ctx.outfit_style and not ctx.image_description:
            prompt += (
                "\n\n## ✅ 强制约束（必须严格遵循）\n"
                f"- 你必须严格遵循穿搭风格：【{ctx.outfit_style}】（不得替换/混用其他风格）。\n"
                "- 你必须只输出 JSON 对象本体（不要 Markdown/代码块/解释）。\n"
                f'- JSON 必须包含字段 "outfit_style"，且其值必须严格等于 "{ctx.outfit_style}"。\n'
                f'- 字段 "outfit" 的第一行必须以 "风格：{ctx.outfit_style}" 开头。\n'
            )

        return prompt

    def _get_prompt_template(self) -> str:
        """Return the configured template without stale identity/example leakage."""
        template = str(self.config.get("prompt_template", "") or "").strip()
        template = template or self._default_prompt_template()
        for legacy, replacement in self._LEGACY_TEMPLATE_REPLACEMENTS.items():
            template = template.replace(legacy, replacement)
        return template

    def _ensure_prompt_template_default(self) -> None:
        """Restore an empty prompt template in memory and persist it when supported."""
        template = str(self.config.get("prompt_template", "") or "").strip()
        if template:
            return
        default_template = self._default_prompt_template()
        if not default_template:
            return
        self.config["prompt_template"] = default_template
        save_config = getattr(self.config, "save_config", None)
        if callable(save_config):
            try:
                save_config()
            except Exception:
                logger.warning("保存默认 prompt_template 失败，已在内存中回填默认值")

    @classmethod
    def _render_prompt_template(cls, template: str, values: dict[str, object]) -> str:
        """Render known placeholders without treating literal JSON braces as fields."""
        placeholder = re.compile(r"\{(\w+)\}")
        left_token = "\u0000LBRACE\u0000"
        right_token = "\u0000RBRACE\u0000"
        rendered = template.replace("{{", left_token).replace("}}", right_token)

        def replace(match: re.Match[str]) -> str:
            return str(values.get(match.group(1), ""))

        rendered = placeholder.sub(replace, rendered)
        return rendered.replace(left_token, "{").replace(right_token, "}")

    @staticmethod
    @lru_cache(maxsize=1)
    def _default_prompt_template() -> str:
        """Load the bundled default Prompt template from the plugin schema."""
        schema_path = Path(__file__).resolve().parent.parent / "_conf_schema.json"
        try:
            data = json.loads(schema_path.read_text(encoding="utf-8"))
            return str(data.get("prompt_template", {}).get("default", "") or "")
        except Exception:
            return ""

    async def _call_llm(
        self,
        prompt: str,
        *,
        sid: str = "life_scheduler_gen",
        image_urls: list[str] | None = None,
        provider_id: str | None = None,
    ) -> str:
        provider_id = provider_id or self.config.get("llm_provider")
        provider = (
            self.context.get_provider_by_id(provider_id) if provider_id else None
        ) or self.context.get_using_provider()

        if not provider:
            raise RuntimeError("No provider")

        try:
            for attempt in range(self._EMPTY_COMPLETION_RETRIES + 1):
                resp = await provider.text_chat(
                    prompt,
                    session_id=sid,
                    image_urls=image_urls or None,
                )
                text = self._extract_completion_text(resp)
                if text:
                    return text
                if attempt < self._EMPTY_COMPLETION_RETRIES:
                    logger.warning("LLM completion 为空，准备重试一次")
            raise RuntimeError("API返回的completion为空")
        finally:
            await self._cleanup_session(sid)

    async def _describe_images(
        self,
        image_paths: list[str],
        *,
        user_text: str = "",
        sid: str = "life_scheduler_vision",
    ) -> str:
        """Turn user images into a durable outfit description.

        Args:
            image_paths: Local paths or media URLs accepted by the provider.
            user_text: Text sent alongside the images.
            sid: Temporary provider session identifier.

        Returns:
            A detailed Chinese outfit description.

        Raises:
            RuntimeError: If no provider is available or completion is empty.
        """
        prompt = (
            "你是穿搭档案整理员。请从用户提供的图片和文字中，只提取可长期复用的外观造型。\n"
            "只允许保留：整体穿搭风格；内搭、上装、下装、外套；鞋袜；包、首饰、帽子等配饰；发型；妆容；"
            "颜色、图案、材质、版型、层次和搭配关系；赤足、不穿鞋袜等明确穿戴约束。\n"
            "必须排除：场景、地点、背景、天气、时间、动作、姿势、表情、活动、日程、人物身份、身体外貌、镜头、构图、光线、氛围和非穿戴道具。"
            "用户文字里的这些内容也必须忽略，不得写进任何字段。\n"
            "只输出 JSON 对象本体，不要 Markdown、解释或额外字段。看不清的穿戴细节留空，不要猜测。\n"
            '格式：{"overall_style":"","clothing":"","footwear":"","accessories":"","hair":"","makeup":"","details":"","constraints":""}\n'
            f"用户补充文字：{user_text or '无'}"
        )
        provider_id = (
            self.config.get("image_provider") or self.config.get("llm_provider")
            if image_paths
            else self.config.get("llm_provider")
        )
        content = await self._call_llm(
            prompt,
            sid=sid,
            image_urls=image_paths,
            provider_id=provider_id,
        )
        payload = self._extract_json_obj(content)
        if payload is None:
            content = await self._call_llm(
                prompt + "\n上一次输出未能解析。这次必须严格输出上述 JSON 对象本体。",
                sid=f"{sid}_repair",
                image_urls=image_paths,
                provider_id=provider_id,
            )
            payload = self._extract_json_obj(content)
        if payload is None:
            raise RuntimeError("图片转写模型未返回可解析的穿搭 JSON")

        fields = (
            ("overall_style", "整体风格"),
            ("clothing", "服装"),
            ("footwear", "鞋袜"),
            ("accessories", "配饰"),
            ("hair", "发型"),
            ("makeup", "妆容"),
            ("details", "颜色材质与版型"),
            ("constraints", "穿戴约束"),
        )
        parts = []
        for key, label in fields:
            value = payload.get(key, "")
            if not isinstance(value, str):
                continue
            value = value.strip()
            if value:
                parts.append(f"{label}：{value}")
        if not parts:
            raise RuntimeError("图片转写模型未返回有效的穿搭字段")
        return "；".join(parts) + "。"

    @staticmethod
    def _extract_completion_text(resp: object) -> str:
        if resp is None:
            return ""
        for key in ("completion_text", "completion", "text", "content"):
            value = getattr(resp, key, None)
            if isinstance(value, str):
                text = value.strip()
                if text:
                    return text
        return ""

    async def _cleanup_session(self, sid: str):
        try:
            cid = await self.context.conversation_manager.get_curr_conversation_id(sid)
            if cid:
                await self.context.conversation_manager.delete_conversation(sid, cid)
        except Exception:
            pass

    # ---------- parse ----------
    def _extract_json_obj(self, text: str) -> dict | None:
        text = text.strip()
        text = re.sub(r"^```json\s*", "", text, flags=re.MULTILINE)
        text = re.sub(r"^```\s*", "", text, flags=re.MULTILINE)
        text = re.sub(r"```\s*$", "", text, flags=re.MULTILINE)

        start = text.find("{")
        if start == -1:
            return None

        brace = 0
        in_string = False
        escape = False

        for i, ch in enumerate(text[start:], start=start):
            if in_string:
                if escape:
                    escape = False
                elif ch == "\\":
                    escape = True
                elif ch == '"':
                    in_string = False
            else:
                if ch == '"':
                    in_string = True
                elif ch == "{":
                    brace += 1
                elif ch == "}":
                    brace -= 1
                    if brace == 0:
                        json_str = text[start : i + 1]
                        try:
                            data = json.loads(json_str)
                            return data if isinstance(data, dict) else None
                        except Exception:
                            return None

        return None

    def _validate_payload(
        self,
        payload: dict | None,
        ctx: ScheduleContext,
        *,
        enforce_style: bool = True,
        manual_extra: str = "",
    ) -> tuple[bool, str]:
        if not payload:
            return False, "未能解析出 JSON 对象"

        outfit = str(payload.get("outfit", "")).strip()
        schedule = str(payload.get("schedule", "")).strip()
        if not outfit:
            return False, "outfit 不能为空"
        if not schedule:
            return False, "schedule 不能为空"
        contradictory_hair = self._CONTRADICTORY_HAIR_RE.search(outfit)
        if contradictory_hair:
            return False, (
                f"outfit 与固定视觉身份冲突：检测到{contradictory_hair.group(0)}，"
                "必须保留奶油金色高双马尾"
            )

        # Only real FatFish peak weekdays need four ready-to-send reports.
        # Weekends are low-peak too; treating them like a weekday produced fake
        # school reports even when the service never enters a peak window.
        try:
            try:
                schedule_day = datetime.date.fromisoformat(ctx.date_str)
            except (TypeError, ValueError):
                schedule_day = datetime.datetime.strptime(ctx.date_str, "%Y年%m月%d日").date()
        except (TypeError, ValueError):
            schedule_day = datetime.date.today()
        if self._is_fat_fish_peak_day(schedule_day):
            reports = payload.get("peak_reports")
            if not isinstance(reports, dict):
                return False, "peak_reports 必须是对象"
            missing_reports = [
                slot for slot in ("09:00", "12:00", "14:00", "18:30")
                if not str(reports.get(slot, "")).strip()
            ]
            if missing_reports:
                return False, "peak_reports 缺少节点：" + ", ".join(missing_reports)
            report_errors = self._peak_report_errors(reports)
            if report_errors:
                return False, "peak_reports 不符合群聊播报要求：" + "；".join(report_errors)

        # Event reports are a secondary delivery channel.  A model occasionally
        # omitting them must not invalidate the schedule/outfit that the same
        # call generated; otherwise one optional broadcast can take the whole
        # nightly pipeline down and trigger another paid repair call.
        event_reports = payload.get("event_reports")
        if event_reports is None:
            event_reports = []
        if not isinstance(event_reports, list):
            event_reports = []
        schedule_times = set(re.findall(r"(?m)^\s*(\d{1,2}:\d{2})\s*[｜|]", schedule))
        for index, report in enumerate(event_reports[:3]):
            if not isinstance(report, dict):
                return False, f"event_reports[{index}] 必须是对象"
            report_time = str(report.get("time") or "").strip()
            report_text = str(report.get("text") or "").strip()
            if report_time not in schedule_times:
                return False, f"event_reports[{index}] time 必须来自日程"
            if str(report.get("offset") or "") not in {"before", "after"}:
                return False, f"event_reports[{index}] offset 只能是 before/after"
            if not 8 <= len(report_text) <= 60:
                return False, f"event_reports[{index}] text 应为 8-60 字"

        schedule_errors = self._schedule_completeness_errors(schedule, schedule_day)
        if schedule_errors:
            return False, "日程完整性未满足：" + "；".join(schedule_errors)

        requirement_errors = self._manual_requirement_errors(payload, manual_extra)
        if requirement_errors:
            return False, "用户补充要求未满足：" + "；".join(requirement_errors)

        required = (ctx.outfit_style or "").strip()
        if not enforce_style:
            return True, ""
        if not required:
            return True, ""

        model_style = str(payload.get("outfit_style", "")).strip()
        if model_style != required:
            return False, f'outfit_style 必须严格等于 "{required}"'

        if not re.match(
            rf"^\s*(?:风格|【风格】|\[风格\])\s*[:：]\s*{re.escape(required)}(?:\s|$)",
            outfit,
        ):
            return False, f'outfit 第一行必须以 "风格：{required}" 开头'

        return True, ""

    def _schedule_completeness_errors(
        self, schedule: str, schedule_day: datetime.date | None = None
    ) -> list[str]:
        """Keep the generated day usable as a continuous, concrete life log."""
        entries: list[tuple[int, str]] = []
        for line in str(schedule or "").splitlines():
            match = re.match(r"\s*(\d{1,2}):(\d{2})\s*[｜|]", line)
            if not match:
                continue
            hour, minute = int(match.group(1)), int(match.group(2))
            if hour <= 23 and minute <= 59:
                entries.append((hour * 60 + minute, line))

        errors: list[str] = []
        # 三餐加上早/午/晚的小事件自然会达到 11 条；这属于用户要求的
        # 正常丰满日程，不应被旧的十条上限误判为失败。
        if not 7 <= len(entries) <= 12:
            errors.append(f"带时间事项应为 7-12 条，实际为 {len(entries)} 条")

        meal_aliases = {
            "早餐": ("早餐", "早饭", "早午餐"),
            "午餐": ("午餐", "午饭"),
            "晚餐": ("晚餐", "晚饭"),
        }
        peak_day = schedule_day is None or self._is_fat_fish_peak_day(schedule_day)
        periods = self._fat_fish_peak_periods()
        # Workday meal windows derive from the actual FatFish pause periods:
        # breakfast before first peak, lunch in the first inter-peak trough,
        # dinner after the final peak.  A holiday has no imposed peak clock.
        if peak_day and len(periods) >= 2:
            meal_windows = {
                "早餐": (0, periods[0][0]),
                "午餐": (periods[0][1], periods[1][0]),
                "晚餐": (periods[-1][1], 24 * 60),
            }
        else:
            meal_windows = {meal: (0, 24 * 60) for meal in meal_aliases}
        for meal, aliases in meal_aliases.items():
            lower, upper = meal_windows[meal]
            if not any(
                any(alias in line for alias in aliases) and lower <= minute < upper
                for minute, line in entries
            ):
                errors.append(f"缺少大肥鱼窗口内的{meal}事项")

        if peak_day and len(periods) >= 2:
            low_peak_buckets = {
                "首段高峰前": sum(1 for minute, _ in entries if minute < periods[0][0]),
                "午间低峰": sum(
                    1 for minute, _ in entries if periods[0][1] <= minute < periods[1][0]
                ),
                "傍晚低峰": sum(1 for minute, _ in entries if minute >= periods[-1][1]),
            }
            expected = {"首段高峰前": (1, 3), "午间低峰": (1, 3), "傍晚低峰": (1, 5)}
            for label, count in low_peak_buckets.items():
                minimum, maximum = expected[label]
                if not minimum <= count <= maximum:
                    errors.append(f"{label}事项应为 {minimum}-{maximum} 条，实际为 {count} 条")
        return errors

    @staticmethod
    def _peak_report_errors(reports: dict) -> list[str]:
        """Reject visual diary prose masquerading as a group transition notice."""
        errors: list[str] = []
        group_markers = ("大家", "杂鱼", "笨蛋", "群里", "你们")
        diary_terms = (
            "领口", "吊带", "内衣", "内裤", "黑丝", "白丝", "丝袜",
            "锁骨", "胸", "臀", "大腿", "短裤", "裙摆", "皮肤", "身材", "妆容",
        )
        for slot in ("09:00", "12:00", "14:00", "18:30"):
            text = str(reports.get(slot, "")).strip()
            if not 15 <= len(text) <= 60:
                errors.append(f"{slot} 应为 15-60 字")
            if not any(marker in text for marker in group_markers):
                errors.append(f"{slot} 缺少面向群聊的称呼")
            if re.match(r"^\d{1,2}:\d{2}", text):
                errors.append(f"{slot} 不应以日程时间戳开头")
            if any(term in text for term in diary_terms):
                errors.append(f"{slot} 含日记式外貌或穿搭描写")
        return errors

    def _manual_requirement_errors(self, payload: dict, manual_extra: str) -> list[str]:
        manual_extra = self._normalize_extra(manual_extra)
        if not manual_extra:
            return []

        requirements = self._extract_manual_requirements(manual_extra)
        if not any(requirements.values()):
            return []

        outfit = self._normalize_requirement_text(str(payload.get("outfit", "")))
        schedule = self._normalize_requirement_text(str(payload.get("schedule", "")))
        any_text = f"{outfit}{schedule}"
        errors: list[str] = []

        missing_outfit = [
            term for term in requirements["required_outfit"] if term not in outfit
        ]
        if missing_outfit:
            errors.append("穿搭缺少 " + ", ".join(missing_outfit))

        missing_schedule = [
            term for term in requirements["required_schedule"] if term not in schedule
        ]
        if missing_schedule:
            errors.append("日程缺少 " + ", ".join(missing_schedule))

        missing_any = [
            term for term in requirements["required_any"] if term not in any_text
        ]
        if missing_any:
            errors.append("内容缺少 " + ", ".join(missing_any))

        forbidden_hits = [
            term
            for term in requirements["forbidden"]
            if self._has_unnegated_term(any_text, term)
        ]
        if forbidden_hits:
            errors.append("出现了用户要求避免的内容 " + ", ".join(forbidden_hits))

        return errors

    @classmethod
    def _has_unnegated_term(cls, text: str, term: str) -> bool:
        if term not in text:
            return False
        for match in re.finditer(re.escape(term), text):
            prefix = text[max(0, match.start() - 6) : match.start()]
            if cls._NEGATED_TERM_PREFIX_RE.search(prefix):
                continue
            return True
        return False

    def _build_style_repair_prompt(
        self, ctx: ScheduleContext, bad_text: str, reason: str
    ) -> str:
        required = (ctx.outfit_style or "").strip()
        return (
            "你之前的输出未通过校验，需要按要求重写。\n"
            f"校验原因：{reason}\n"
            f"必须使用穿搭风格：{required}\n\n"
            f"必须落实的衣柜方案：{ctx.outfit_plan}\n\n"
            f"{self._SCHEDULE_COMPLETENESS_CONTRACT}\n"
            "请只输出 JSON 对象本体，不要 Markdown，不要解释。\n"
            "输出 JSON 必须包含字段：outfit_style、outfit、schedule、attendance_plan、peak_reports、event_reports。\n"
            f'其中 outfit_style 必须严格等于 "{required}"；outfit 第一行必须以 "风格：{required}" 开头。\n\n'
            "你之前的输出（供参考，可能不合规）：\n"
            f"{bad_text}\n"
        )

    def _build_manual_repair_prompt(
        self, ctx: ScheduleContext, bad_text: str, reason: str, extra: str
    ) -> str:
        return (
            "你之前的输出未通过校验，需要按用户补充要求重写。\n"
            f"校验原因：{reason}\n"
            f"日期：{ctx.date_str} {ctx.weekday} {ctx.holiday}\n"
            f"用户补充要求（最高优先级）：{extra}\n\n"
            "必须遵循：\n"
            "- 用户补充要求高于随机创意池、穿搭风格、日程类型和历史日程。\n"
            "- 不得忽略、替换或弱化用户指定的具体穿搭、场景和活动。\n"
            f"{self._SCHEDULE_COMPLETENESS_CONTRACT}\n"
            "- 请只输出 JSON 对象本体，不要 Markdown，不要解释。\n"
            "- 输出 JSON 必须包含字段：outfit_style、outfit、schedule、attendance_plan、peak_reports、event_reports。\n\n"
            "你之前的输出（供参考，可能不合规）：\n"
            f"{bad_text}\n"
        )

    def _to_schedule_data(
        self,
        payload: dict,
        date_str: str,
        ctx: ScheduleContext,
        *,
        manual_extra: str = "",
        image_description: str = "",
    ) -> ScheduleData:
        outfit = str(payload.get("outfit", "")).strip() or "日常休闲装"
        schedule = self._sanitize_schedule(str(payload.get("schedule", "")).strip()) or "无"
        if manual_extra:
            outfit_style = "用户指定"
        elif image_description:
            outfit_style = "图片指定"
        else:
            outfit_style = str(payload.get("outfit_style", "")).strip() or (
                ctx.outfit_style or ""
            )
        raw_reports = payload.get("peak_reports", {})
        peak_reports: dict[str, str] = {}
        try:
            schedule_day = datetime.date.fromisoformat(date_str)
        except (TypeError, ValueError):
            schedule_day = datetime.date.today()
        # FatFish never broadcasts on weekends or statutory holidays.  Do not
        # retain arbitrary model prose there as dormant state that could leak
        # into another day after a later configuration change.
        if self._is_fat_fish_peak_day(schedule_day) and isinstance(raw_reports, dict):
            for slot in ("09:00", "12:00", "14:00", "18:30"):
                text = str(raw_reports.get(slot, "")).strip()
                if text:
                    peak_reports[slot] = text[:80]
        event_reports: list[dict] = []
        for index, report in enumerate(payload.get("event_reports") or []):
            if not isinstance(report, dict):
                continue
            event_reports.append({
                "id": str(report.get("id") or f"event_{index + 1}")[:48],
                "time": str(report.get("time") or "")[:5],
                "offset": str(report.get("offset") or "before"),
                "text": str(report.get("text") or "").strip()[:60],
            })
        return ScheduleData(
            date=date_str,
            outfit_style=outfit_style,
            outfit=outfit,
            schedule=schedule,
            attendance_plan=ctx.attendance_plan,
            peak_reports=peak_reports,
            event_reports=event_reports,
        )

    @staticmethod
    def _sanitize_schedule(schedule: str) -> str:
        """Keep observable schedule facts while dropping legacy inner narration."""
        cleaned: list[str] = []
        for raw_line in str(schedule or "").splitlines():
            line = raw_line.strip()
            if not line:
                continue
            # Remove only text that is explicitly framed as hidden narration.
            # Do not truncate the schedule columns: location, action and
            # observable detail are required by current-state injection and
            # by selfie background selection.
            line = re.sub(
                r"[（(][^）)]*(?:内心|心里|心想|暗自|默默觉得|其实很想)[^）)]*[）)]",
                "",
                line,
            )
            parts = re.split(r"\s*[｜|]\s*", line)
            kept: list[str] = []
            for part in parts[:4]:
                part = re.sub(
                    r"^(?:内心|心里|心想|暗自|默默觉得)\s*[:：]?\s*.*$",
                    "",
                    part.strip(),
                )
                if part:
                    kept.append(part)
            line = "｜".join(kept)
            cleaned.append(line.strip(" ，,；;"))
        return "\n".join(item for item in cleaned if item)

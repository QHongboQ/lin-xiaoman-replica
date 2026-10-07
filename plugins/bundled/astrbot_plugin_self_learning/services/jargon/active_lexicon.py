"""Daily, optional active vocabulary for reply generation."""
import asyncio
import json
import os
import re
import time
from pathlib import Path
from typing import Any, Dict, List, Optional

from astrbot.api import logger
try:
    from ...utils.json_utils import safe_parse_llm_json
except ImportError:
    from utils.json_utils import safe_parse_llm_json


class ActiveJargonLexicon:
    """One daily DeepSeek batch, then lexical matching with no reply-time LLM call."""
    _SEEDS = {
        "V我50": {
            "meaning": "“疯狂星期四 V 我 50”的简称：借肯德基周四促销梗，开玩笑让对方转 50 元或请客。",
            "triggers": ["星期四", "周四", "疯狂星期四", "肯德基", "请客", "打钱"],
        },
        "何意味": {
            "meaning": "“什么意思”的网络化说法，多用于困惑、反问或轻松吐槽。",
            "triggers": ["什么意思", "什么意义", "何意", "这啥意思", "啥意思"],
        },
    }

    def __init__(self, *, config: Any, db_manager: Any, llm_adapter: Any) -> None:
        self._config, self._db, self._llm = config, db_manager, llm_adapter
        self._path = Path(config.data_dir) / "active_jargon_lexicon.json"
        self._lock = asyncio.Lock()

    async def run_forever(self) -> None:
        await asyncio.sleep(8)
        while True:
            try:
                await self.refresh_if_due()
            except asyncio.CancelledError:
                raise
            except Exception as exc:
                logger.warning(f"[主动词库] 每日刷新失败: {exc}")
            await asyncio.sleep(600)

    async def refresh_if_due(self, force: bool = False) -> bool:
        if not getattr(self._config, "enable_active_jargon_output", False):
            return False
        async with self._lock:
            snapshot = self._load()
            interval = max(1, int(getattr(self._config, "active_jargon_refresh_hours", 24))) * 3600
            if not force and time.time() - float(snapshot.get("refreshed_at", 0) or 0) < interval:
                return False
            candidates = await self._collect_candidates()
            if not candidates:
                self._write({"version": 1, "refreshed_at": time.time(), "terms": []})
                return True
            response = await self._llm.generate_response(
                self._batch_prompt(candidates), temperature=0.1, model_type="filter"
            )
            terms = self._parse_response(response, candidates) or self._seed_terms(candidates)
            self._write({
                "version": 1, "refreshed_at": time.time(), "source": "daily_deepseek_batch",
                "terms": terms[:max(1, int(getattr(self._config, "active_jargon_candidate_limit", 20)))],
            })
            logger.info(f"[主动词库] 每日批量释义完成: {len(terms)} 条可选表达")
            return True

    async def build_injection(self, text: str) -> Optional[str]:
        if not getattr(self._config, "enable_active_jargon_output", False):
            return None
        snapshot = self._load()
        terms = snapshot.get("terms") if isinstance(snapshot, dict) else []
        if not isinstance(terms, list):
            return None
        normalized = str(text or "").casefold()
        matched = []
        for item in terms:
            if not isinstance(item, dict):
                continue
            triggers = item.get("triggers") or []
            if any(str(trigger).strip().casefold() in normalized for trigger in triggers if len(str(trigger).strip()) >= 2):
                matched.append(item)
        if not matched:
            return None
        limit = max(1, int(getattr(self._config, "active_jargon_inject_limit", 1)))
        lines = [
            "[可选网络表达]",
            "以下仅供最终回复自然选词。不是必须使用；最多采用一项；不要解释这份提示，也不要为了玩梗而强行套用。",
        ]
        for item in matched[:limit]:
            term = str(item.get("term") or "").strip()
            meaning = str(item.get("meaning") or "").strip()
            if term and meaning:
                lines.append(f"- 可选说法「{term}」：{meaning}")
        return "\n".join(lines) if len(lines) > 2 else None

    async def _collect_candidates(self) -> List[Dict[str, Any]]:
        rows = []
        if self._db and hasattr(self._db, "get_recent_jargon_list"):
            rows = await self._db.get_recent_jargon_list(
                limit=max(20, int(getattr(self._config, "active_jargon_candidate_limit", 20)) * 4),
                only_confirmed=None,
            )
        seen, result = set(), []
        for row in rows or []:
            term = str(row.get("content") or "").strip()
            key = term.casefold()
            if not term or len(term) > 32 or key in seen:
                continue
            seen.add(key)
            result.append({"term": term, "context": str(row.get("raw_content") or "")[:420]})
        for term, details in self._SEEDS.items():
            if term.casefold() not in seen:
                result.append({"term": term, "context": details["meaning"]})
        return result[:max(1, int(getattr(self._config, "active_jargon_candidate_limit", 20)))]

    def _batch_prompt(self, candidates: List[Dict[str, Any]]) -> str:
        return """你是中文网络用语编辑。请一次性整理候选词，输出严格 JSON，不要 Markdown：
{"terms":[{"term":"候选原词","active":true,"meaning":"简洁准确的含义和适用语境","triggers":["可从用户话里识别的2-6个中文短语"]}]}
规则：
1. 只保留公开、通用、轻松聊天可自然复用的网络用语。
2. 排除人名、群内私事、针对某人的辱骂、私人昵称、露骨性内容、含义不确定的词。
3. triggers 是“用户说了什么时，机器人可以考虑使用该词”的同义/场景提示，不要放单字。
4. 词条不是强制口头禅，释义中不得要求回复一定使用。
5. 不在候选内造新词。
候选：
""" + json.dumps(candidates, ensure_ascii=False)

    def _parse_response(self, response: Optional[str], candidates: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
        if not response:
            return []
        data = safe_parse_llm_json(str(response).strip())
        if not isinstance(data, dict) or not isinstance(data.get("terms"), list):
            return []
        allowed = {str(x["term"]).casefold(): str(x["term"]) for x in candidates}
        out, seen = [], set()
        for item in data["terms"]:
            if not isinstance(item, dict) or item.get("active") is not True:
                continue
            term = allowed.get(str(item.get("term") or "").strip().casefold())
            meaning = re.sub(r"\s+", " ", str(item.get("meaning") or "").strip())[:220]
            triggers = item.get("triggers") or []
            if not term or not meaning or term.casefold() in seen or not isinstance(triggers, list):
                continue
            clean = []
            for trigger in triggers:
                trigger = re.sub(r"\s+", " ", str(trigger).strip())[:32]
                if len(trigger) >= 2 and trigger not in clean:
                    clean.append(trigger)
            if clean:
                out.append({"term": term, "meaning": meaning, "triggers": clean[:8]})
                seen.add(term.casefold())
        return out

    def _seed_terms(self, candidates: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
        available = {str(x["term"]).casefold() for x in candidates}
        return [{"term": term, "meaning": data["meaning"], "triggers": data["triggers"]}
                for term, data in self._SEEDS.items() if term.casefold() in available]

    def _load(self) -> Dict[str, Any]:
        try:
            with self._path.open("r", encoding="utf-8") as handle:
                data = json.load(handle)
            return data if isinstance(data, dict) else {}
        except (OSError, ValueError):
            return {}

    def _write(self, data: Dict[str, Any]) -> None:
        self._path.parent.mkdir(parents=True, exist_ok=True)
        temporary = self._path.with_suffix(".tmp")
        with temporary.open("w", encoding="utf-8") as handle:
            json.dump(data, handle, ensure_ascii=False, indent=2)
        os.replace(temporary, self._path)

"""
alert.py
對應 Workflow: Event Engine → Alert / AI Report

1. AlertDispatcher: 依事件嚴重度決定是否要「告警」— 預設印到終端機，
   也可以填 webhook_url (Slack / LINE Notify / Discord... 等任何吃 JSON POST 的服務)。
2. generate_ai_report(): 把一段時間內的事件彙整成一份「事件摘要報告」。
   - 若環境變數 ANTHROPIC_API_KEY 存在且已安裝 anthropic SDK，會呼叫 Claude 生成
     一份精簡、口語化的中文摘要報告。
   - 否則自動退回「規則式模板報告」，不需要任何外部服務也能運作，
     確保 Dashboard 的「AI Report」按鈕在離線/無金鑰環境下依然堪用。
"""
from __future__ import annotations
import os
import json
import logging
from collections import Counter
from typing import List, Optional

import urllib.request

from .types import Event

logger = logging.getLogger(__name__)

SEVERITY_ORDER = {"info": 0, "warning": 1, "critical": 2}


class AlertDispatcher:
    def __init__(self, console: bool = True, webhook_url: Optional[str] = None, min_severity: str = "warning"):
        self.console = console
        self.webhook_url = webhook_url
        self.min_severity = min_severity

    def dispatch(self, event: Event):
        if SEVERITY_ORDER.get(event.severity, 0) < SEVERITY_ORDER.get(self.min_severity, 1):
            return

        if self.console:
            tag = {"info": "ℹ️", "warning": "⚠️", "critical": "🚨"}.get(event.severity, "•")
            print(f"{tag} [{event.severity.upper()}] {event.message}")

        if self.webhook_url:
            self._send_webhook(event)

    def _send_webhook(self, event: Event):
        payload = json.dumps(
            {
                "text": f"[{event.severity.upper()}] {event.message}",
                "event_type": event.event_type,
                "track_id": event.track_id,
                "zone": event.zone,
                "timestamp": event.timestamp,
            }
        ).encode("utf-8")
        req = urllib.request.Request(
            self.webhook_url, data=payload, headers={"Content-Type": "application/json"}
        )
        try:
            urllib.request.urlopen(req, timeout=5)
        except Exception as exc:  # noqa: BLE001
            logger.warning("Webhook 發送失敗: %s", exc)


def _template_report(events: List[dict]) -> str:
    """不依賴外部服務的規則式摘要，當作 AI Report 的離線備援。"""
    if not events:
        return "此區間內沒有偵測到需要留意的事件。"

    type_counts = Counter(e["event_type"] for e in events)
    critical = [e for e in events if e["severity"] == "critical"]

    zh_name = {
        "fall": "跌倒",
        "sudden_motion": "異常快速移動",
        "loitering": "徘徊",
        "roi_overcrowd": "區域擁擠",
        "global_overcrowd": "整體人數過多",
        "zone_enter": "進入區域",
        "zone_exit": "離開區域",
    }

    lines = ["【事件摘要報告】"]
    lines.append(f"本區間共記錄 {len(events)} 筆事件。")
    lines.append("事件類型統計：")
    for etype, cnt in type_counts.most_common():
        lines.append(f"  - {zh_name.get(etype, etype)}：{cnt} 次")

    if critical:
        lines.append("")
        lines.append(f"⚠️ 其中包含 {len(critical)} 筆「重大」等級事件，建議優先確認：")
        for e in critical[:5]:
            lines.append(f"  - {e['message']}")

    return "\n".join(lines)


def generate_ai_report(events: List[dict], model: str = "claude-sonnet-4-6") -> str:
    """產生 AI Report。優先嘗試呼叫 Claude API，失敗則退回模板摘要。"""
    api_key = os.environ.get("ANTHROPIC_API_KEY")
    if not api_key:
        return _template_report(events)

    try:
        import anthropic  # 延遲匯入，避免沒安裝時整個專案無法啟動

        client = anthropic.Anthropic(api_key=api_key)
        events_text = "\n".join(
            f"- [{e['severity']}] {e['message']} (zone={e.get('zone')})" for e in events[:100]
        )
        prompt = (
            "你是一個監控系統的事件分析助手。以下是最近偵測到的行為事件清單，"
            "請用繁體中文寫一份簡短的摘要報告（150字以內），"
            "指出整體狀況、是否有需要立即關注的重大事件，語氣專業、精簡：\n\n"
            f"{events_text or '（此區間沒有事件）'}"
        )
        resp = client.messages.create(
            model=model,
            max_tokens=500,
            messages=[{"role": "user", "content": prompt}],
        )
        text_blocks = [b.text for b in resp.content if getattr(b, "type", "") == "text"]
        return "\n".join(text_blocks) if text_blocks else _template_report(events)
    except Exception as exc:  # noqa: BLE001
        logger.warning("呼叫 Claude API 產生報告失敗，改用模板報告: %s", exc)
        return _template_report(events)

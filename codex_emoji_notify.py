#!/usr/bin/env python3
"""Custom notification script for Codex CLI completion hooks.

Usage examples:
  python3 codex_emoji_notify.py
  python3 codex_emoji_notify.py --title "Codex 완료" --message "응답이 완료되었습니다"
  python3 codex_emoji_notify.py --max-len 120 '{"last-assistant-message":"..."}'
"""

from __future__ import annotations

import argparse
import json
import platform
import subprocess
import sys


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Codex CLI 응답 완료 후 실행할 커스텀 알림 스크립트"
    )
    parser.add_argument("--emoji", default="🤖", help="기본 알림 이모지")
    parser.add_argument(
        "--success-emoji",
        default="🎉",
        help="성공 상태일 때 사용할 이모지",
    )
    parser.add_argument(
        "--error-emoji",
        default="❌",
        help="실패/에러 상태일 때 사용할 이모지",
    )
    parser.add_argument("--title", default="Codex 완료", help="알림 제목")
    parser.add_argument(
        "--message",
        default="응답이 완료되었습니다.",
        help="알림 본문",
    )
    parser.add_argument(
        "--max-len",
        type=int,
        default=80,
        help="알림 본문 최대 길이(초과 시 말줄임, 0 이하면 무제한)",
    )
    parser.add_argument(
        "payload",
        nargs="?",
        default=None,
        help="Codex notify 훅이 전달하는 JSON 문자열(선택)",
    )
    return parser.parse_args()


def applescript_quote(text: str) -> str:
    """Quote text for AppleScript string literals."""
    escaped = text.replace("\\", "\\\\").replace('"', '\\"')
    return f'"{escaped}"'


def notify_macos(title: str, message: str) -> bool:
    # osascript로 macOS 알림센터에 표시
    script = (
        f"display notification {applescript_quote(message)} "
        f"with title {applescript_quote(title)}"
    )
    try:
        result = subprocess.run(["osascript", "-e", script], capture_output=True, text=True)
    except OSError:
        return False
    return result.returncode == 0


def truncate_text(text: str, max_len: int) -> str:
    if max_len <= 0 or len(text) <= max_len:
        return text
    if max_len <= 3:
        return "." * max_len
    return text[: max_len - 3].rstrip() + "..."


def payload_has_error(payload: dict) -> bool:
    for key in ("error", "failed", "is_error", "is-error"):
        value = payload.get(key)
        if isinstance(value, bool):
            if value:
                return True
            continue
        if isinstance(value, str):
            normalized = value.strip().lower()
            if normalized in {"true", "1", "yes", "y", "error", "fail", "failed"}:
                return True
            continue
        if isinstance(value, (int, float)) and value != 0:
            return True
    status = str(payload.get("status", "")).lower()
    event = str(payload.get("event", "")).lower()
    return ("error" in status) or ("fail" in status) or ("error" in event) or ("fail" in event)


def pick_best_message(payload: dict, fallback: str) -> str:
    for key in ("last-assistant-message", "message", "summary", "output"):
        value = payload.get(key)
        if isinstance(value, str) and value.strip():
            return value.strip()
    return fallback


def pick_best_title(payload: dict, fallback: str) -> str:
    for key in ("title", "source", "event"):
        value = payload.get(key)
        if isinstance(value, str) and value.strip():
            return value.strip()
    return fallback


def main() -> int:
    args = parse_args()
    title = args.title
    message = args.message
    emoji = args.emoji

    # Codex가 전달한 JSON 페이로드가 있으면 마지막 어시스턴트 메시지를 우선 사용
    if args.payload:
        try:
            payload = json.loads(args.payload)
            if isinstance(payload, dict):
                message = pick_best_message(payload, message)
                title = pick_best_title(payload, title)
                emoji = args.error_emoji if payload_has_error(payload) else args.success_emoji
        except json.JSONDecodeError:
            # 페이로드 파싱 실패 시 기본/사용자 지정 메시지를 그대로 사용
            pass

    message = truncate_text(message, args.max_len)
    title = f"{emoji} {title}".strip()

    notified = False
    if platform.system() == "Darwin":
        notified = notify_macos(title, message)

    if not notified:
        # 폴백: 터미널 출력 + 벨
        print(f"\a{title}: {message}")

    return 0


if __name__ == "__main__":
    sys.exit(main())

"""Desktop GUI runtime process — keep-alive sentinel for the Tauri shell.

Tauri 桌面壳通过 ``uv run interview-agent --config <path>`` 启动本模块，
作为长驻子进程指示运行时状态。所有实际业务操作由 ``gui_runtime`` 模块
通过独立的 ``uv run python -c "..."`` 调用完成，本进程仅负责：

1. 校验配置文件
2. 检查知识库就绪状态
3. 阻塞等待直至收到 SIGTERM / SIGINT
"""

from __future__ import annotations

import argparse
import signal
import sys
import threading
from pathlib import Path

from interview_agent.config import DEFAULT_CONFIG_PATH, ConfigError, load_config
from interview_agent.storage import get_knowledge_base_status


def _build_offline_command(config_path: Path, database_path: Path, source_path: Path) -> str:
    return (
        "uv run python -m interview_agent.kb.build "
        f"--source {source_path} --config {config_path} --db {database_path}"
    )


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        prog="interview-agent",
        description="Interview Agent 桌面 GUI 运行时进程。",
    )
    parser.add_argument(
        "--config",
        default=str(DEFAULT_CONFIG_PATH),
        help=f"配置文件路径，默认值: {DEFAULT_CONFIG_PATH}",
    )
    args = parser.parse_args(argv)
    config_path = Path(args.config)

    try:
        config = load_config(config_path)
    except ConfigError as error:
        print(f"配置错误: {error}", file=sys.stderr)
        return 1

    database_path = Path(config.storage.database_path)
    knowledge_base_status = get_knowledge_base_status(database_path)
    if knowledge_base_status != "ready":
        print("知识库未就绪，请先执行离线构建：", file=sys.stderr)
        print(
            _build_offline_command(config_path, database_path, Path(config.knowledge_base.source)),
            file=sys.stderr,
        )
        return 1

    shutdown = threading.Event()

    def _signal_handler(*_args: object) -> None:
        shutdown.set()

    signal.signal(signal.SIGTERM, _signal_handler)
    signal.signal(signal.SIGINT, _signal_handler)

    shutdown.wait()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

# -*- coding: utf-8 -*-
"""全局配置:从环境变量 / .env 读取。

JUDGE_BACKEND 决定 Judge 用谁:
  - mock   : 内置规则桩,无需任何模型,本地即可端到端跑通(默认)
  - pingan : 平安内网大模型(双签名鉴权,需配齐下面的平安变量)
"""
from __future__ import annotations

from pathlib import Path

from pydantic_settings import BaseSettings, SettingsConfigDict

BASE_DIR = Path(__file__).resolve().parent.parent  # backend/
DATA_DIR = BASE_DIR / "data"


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=str(BASE_DIR / ".env"),
        env_file_encoding="utf-8",
        extra="ignore",
    )

    # 应用
    app_name: str = "Ark 快捷服务评估平台"
    judge_backend: str = "mock"  # mock | pingan
    judge_concurrency: int = 4   # 并发调用大模型的协程数
    log_level: str = "INFO"      # 设 DEBUG 可看到模型每条的原始返回

    # 平安大模型平台(OpenAI 接口,双签名鉴权)
    open_ai_url: str = ""
    rsa_pk: str = ""
    cre_id: str = ""
    open_api_code: str = ""
    llm_app_key: str = ""
    llm_app_secret: str = ""
    llm_scene_id: str = ""
    llm_timeout: int = 30
    llm_max_retries: int = 3

    @property
    def uploads_dir(self) -> Path:
        d = DATA_DIR / "uploads"
        d.mkdir(parents=True, exist_ok=True)
        return d

    @property
    def outputs_dir(self) -> Path:
        d = DATA_DIR / "outputs"
        d.mkdir(parents=True, exist_ok=True)
        return d

    @property
    def sample_dir(self) -> Path:
        return DATA_DIR / "sample"

    def pingan_ready(self) -> bool:
        """平安大模型所需变量是否齐全。"""
        required = [
            self.open_ai_url, self.rsa_pk, self.cre_id, self.open_api_code,
            self.llm_app_key, self.llm_app_secret, self.llm_scene_id,
        ]
        return all(required)


settings = Settings()

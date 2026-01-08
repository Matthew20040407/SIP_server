# Code by DHT@Matthew

import logging
import time

import httpx
from pydantic import BaseModel, field_serializer

from helper.llm_backends.models import LLMBackend


class PostChatMessageRequest(BaseModel):
    session_id: int | str
    user_id: int | str  # tg user ID or call ID
    message: str
    streaming: bool = False

    @field_serializer("user_id")
    def serialize_user_id(self, value: int) -> str:
        return str(value)

    @field_serializer("session_id")
    def serialize_session_id(self, value: int) -> str:
        return str(value)


class APIBackend(LLMBackend):
    def __init__(
        self,
        system_prompt: str | None = None,
        server_endpoint_url: str = "http://192.168.157.165:8004",
        timeout: float = 30.0,
        api_version: int = 1,
    ) -> None:
        self.logger = logging.getLogger("API_LLM")
        start_time = time.time()

        self.logger = logging.getLogger(__name__)
        self.timeout = timeout
        self.api_version = api_version
        self.server_endpoint_url = f"{server_endpoint_url}/api/v{api_version}"
        self.http_client = httpx.AsyncClient(timeout=self.timeout)

        init_time = time.time() - start_time
        self.logger.info(f"LLM initialized in {init_time:.2f}s")

        self.system_prompt = system_prompt

        self.past_key_values = None
        self.cached_token_count = 0

    async def stop(self):
        if self.http_client:
            await self.http_client.aclose()

    async def generate(
        self, messages: list[dict[str, str]], language: str = "zh", **kwargs
    ) -> str:
        self.logger.info(messages)
        user_id = kwargs.get("user_id")
        message = (
            messages[0]["content"]
            + f"/no_think\n您必須使用此語言進行輸出:{language} \n用戶提問:"
            + messages[-1]["content"]
        )

        if not self.http_client:
            raise RuntimeError("Client not started")

        if not user_id:
            raise ValueError("Missing user_id")
        try:
            request = PostChatMessageRequest(
                session_id=user_id,
                user_id=user_id,
                message=message if message else "",
            )
            res = await self.http_client.post(
                f"{self.server_endpoint_url}/chat",
                json=request.model_dump(mode="json"),
            )
            res.raise_for_status()
            self.logger.info(f"Chat response: {res.headers}")
            return res.json().get("response", "No response")

        except Exception as e:
            self.logger.error(f"Chat failed: {e}", exc_info=True)
            return "Sorry, something went wrong."

    def clear_history(self) -> None:
        self.history = [self.history[0]]
        self.past_key_values = None
        self.cached_token_count = 0

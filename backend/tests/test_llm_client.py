from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from backend.config.settings import get_settings
from backend.pipeline.llm_client import LLMClient


@pytest.mark.asyncio
async def test_chat_records_cost(tmp_path, monkeypatch) -> None:
    monkeypatch.chdir(tmp_path)
    monkeypatch.setenv("OPENAI_API_KEY", "test-key")
    get_settings.cache_clear()

    mock_usage = MagicMock(prompt_tokens=10, completion_tokens=20)
    mock_choice = MagicMock()
    mock_choice.message.content = "Hello"
    mock_response = MagicMock(choices=[mock_choice], usage=mock_usage)

    with patch("backend.pipeline.llm_client.AsyncOpenAI") as mock_openai_cls:
        mock_client = AsyncMock()
        mock_client.chat.completions.create = AsyncMock(return_value=mock_response)
        mock_openai_cls.return_value = mock_client

        client = LLMClient(provider="openai", model="gpt-4o-mini")
        result = await client.chat("session-1", [{"role": "user", "content": "Hi"}])

    assert result.content == "Hello"
    assert result.input_tokens == 10
    assert result.output_tokens == 20
    assert (tmp_path / "cost_log.jsonl").exists()
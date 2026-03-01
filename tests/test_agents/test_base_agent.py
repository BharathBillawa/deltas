"""
Tests for BaseAgent.

Tests LLM initialization, prompt creation, and fallback behavior.
"""

import pytest
from unittest.mock import patch, MagicMock

from src.agents.base_agent import BaseAgent
from langchain_core.prompts import ChatPromptTemplate


class TestBaseAgentInit:
    """Tests for BaseAgent initialization."""

    def test_creates_with_default_temperature(self):
        """Default temperature should be 0.3."""
        with patch.object(BaseAgent, '_initialize_llm', return_value=None):
            agent = BaseAgent()
            assert agent.temperature == 0.3

    def test_creates_with_custom_temperature(self):
        """Should accept custom temperature."""
        with patch.object(BaseAgent, '_initialize_llm', return_value=None):
            agent = BaseAgent(temperature=0.7)
            assert agent.temperature == 0.7

    def test_empty_reasoning_history(self):
        """Should start with empty reasoning history."""
        with patch.object(BaseAgent, '_initialize_llm', return_value=None):
            agent = BaseAgent()
            assert agent.reasoning_history == []

    def test_no_api_key_returns_none_llm(self):
        """Without API key, LLM should be None."""
        with patch('src.agents.base_agent.settings') as mock_settings:
            mock_settings.google_api_key = None
            agent = BaseAgent()
            assert agent.llm is None


class TestBaseAgentPrompt:
    """Tests for prompt creation."""

    def test_creates_chat_prompt_template(self):
        """Should create a ChatPromptTemplate."""
        with patch.object(BaseAgent, '_initialize_llm', return_value=None):
            agent = BaseAgent()
            prompt = agent._create_prompt("You are helpful.", "Analyze {input}")
            assert isinstance(prompt, ChatPromptTemplate)

    def test_prompt_has_two_messages(self):
        """Prompt should have system and human messages."""
        with patch.object(BaseAgent, '_initialize_llm', return_value=None):
            agent = BaseAgent()
            prompt = agent._create_prompt("System msg", "Human msg")
            assert len(prompt.messages) == 2


class TestBaseAgentInvoke:
    """Tests for LLM invocation and fallback."""

    def test_invoke_without_llm_returns_none(self):
        """Should return None when LLM is not available."""
        with patch.object(BaseAgent, '_initialize_llm', return_value=None):
            agent = BaseAgent()
            prompt = agent._create_prompt("System", "Hello {name}")
            result = agent._invoke_llm(prompt, {"name": "test"})
            assert result is None

    def test_invoke_failure_returns_none(self):
        """Should return None when LLM invocation fails."""
        with patch.object(BaseAgent, '_initialize_llm', return_value=None):
            agent = BaseAgent()
            # Simulate LLM that raises
            mock_llm = MagicMock()
            agent.llm = mock_llm
            mock_llm.__or__ = MagicMock(side_effect=Exception("API error"))
            prompt = agent._create_prompt("System", "Hello {name}")
            result = agent._invoke_llm(prompt, {"name": "test"})
            assert result is None

    def test_clear_reasoning_history(self):
        """Should clear reasoning history."""
        with patch.object(BaseAgent, '_initialize_llm', return_value=None):
            agent = BaseAgent()
            agent.reasoning_history = [{"test": "data"}]
            agent.clear_reasoning_history()
            assert agent.reasoning_history == []

    def test_get_reasoning_summary(self):
        """Should return reasoning history."""
        with patch.object(BaseAgent, '_initialize_llm', return_value=None):
            agent = BaseAgent()
            entry = {"timestamp": "2024-01-01", "agent": "Test", "response": "ok"}
            agent.reasoning_history = [entry]
            summary = agent.get_reasoning_summary()
            assert len(summary) == 1
            assert summary[0] == entry

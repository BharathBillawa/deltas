"""
Base Agent class for LLM-powered reasoning.

Provides common functionality for all agents.
"""

import logging
from typing import Optional, Dict, Any
from datetime import datetime

from langchain_google_genai import ChatGoogleGenerativeAI
from langchain_core.prompts import ChatPromptTemplate
from langchain_core.output_parsers import StrOutputParser

from src.config.settings import settings

logger = logging.getLogger(__name__)


class BaseAgent:
    """
    Base class for LLM-powered agents.

    Features:
    - LLM initialization with fallback
    - Common prompt patterns
    - Error handling
    - Reasoning explanation capture
    """

    def __init__(self, temperature: float = 0.3):
        """
        Initialize base agent.

        Args:
            temperature: LLM temperature (0.0 = deterministic, 1.0 = creative)
        """
        self.temperature = temperature
        self.llm = self._initialize_llm()
        self.reasoning_history: list[Dict[str, Any]] = []

    def _initialize_llm(self) -> Optional[ChatGoogleGenerativeAI]:
        """
        Initialize Gemini LLM with error handling.

        Returns:
            ChatGoogleGenerativeAI instance or None if initialization fails
        """
        try:
            if not settings.google_api_key:
                logger.warning("GOOGLE_API_KEY not configured. Agent will use fallback logic.")
                return None

            llm = ChatGoogleGenerativeAI(
                model="gemini-3-flash-preview",
                google_api_key=settings.google_api_key,
                temperature=self.temperature,
                convert_system_message_to_human=True,
            )

            logger.info(f"Initialized {self.__class__.__name__} with Gemini LLM")
            return llm

        except Exception as e:
            logger.error(f"Failed to initialize LLM: {e}. Will use fallback logic.")
            return None

    def _create_prompt(self, system: str, human: str) -> ChatPromptTemplate:
        """
        Create a chat prompt template.

        Args:
            system: System message (agent role/instructions)
            human: Human message template with variables

        Returns:
            ChatPromptTemplate
        """
        return ChatPromptTemplate.from_messages([
            ("system", system),
            ("human", human),
        ])

    def _invoke_llm(
        self,
        prompt_template: ChatPromptTemplate,
        variables: Dict[str, Any]
    ) -> Optional[str]:
        """
        Invoke LLM with prompt and variables.

        Args:
            prompt_template: ChatPromptTemplate
            variables: Variables to fill in template

        Returns:
            LLM response string or None if invocation fails
        """
        if not self.llm:
            logger.warning("LLM not available, using fallback logic")
            return None

        try:
            chain = prompt_template | self.llm | StrOutputParser()
            response = chain.invoke(variables)

            # Store reasoning
            self.reasoning_history.append({
                "timestamp": datetime.now().isoformat(),
                "agent": self.__class__.__name__,
                "variables": variables,
                "response": response
            })

            return response

        except Exception as e:
            logger.error(f"LLM invocation failed: {e}. Using fallback logic.")
            return None

    def get_reasoning_summary(self) -> list[Dict[str, Any]]:
        """
        Get reasoning history for this agent.

        Returns:
            List of reasoning entries with timestamps
        """
        return self.reasoning_history

    def clear_reasoning_history(self):
        """Clear reasoning history."""
        self.reasoning_history = []

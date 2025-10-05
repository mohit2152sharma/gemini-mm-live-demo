"""
Gemini client initialization and management.
"""

from typing import Optional

import google.genai as genai
from google.genai import types
from utils._logger import logger

from app.core.config import settings
from app.services.system_prompt import BaseSystemPrompt, HelpfulAssistantPrompt
from app.tools import AllTools


class GeminiClientManager:
    """Manages Gemini client initialization and configuration."""

    def __init__(self, system_prompt: Optional[BaseSystemPrompt] = None):
        self._client = None
        self._config = None
        self._system_prompt: BaseSystemPrompt = (
            system_prompt or HelpfulAssistantPrompt()
        )

    def initialize_client(self) -> genai.Client:
        """
        Initialize and return the Gemini client.

        Returns:
            genai.Client: Configured Gemini client

        Raises:
            ValueError: If configuration is invalid
            Exception: If client initialization fails
        """
        try:
            settings.validate_configuration()

            if settings.GOOGLE_GENAI_USE_VERTEXAI:
                self._client = genai.Client(
                    vertexai=True,
                    # http_options={"api_version": "v1beta"},
                    project=settings.GOOGLE_CLOUD_PROJECT_ID,
                    location=settings.GOOGLE_CLOUD_LOCATION,
                    # api_key=settings.GEMINI_API_KEY,
                )
                logger.info(
                    f"✅ Gemini client initialized using Vertex AI "
                    f"(Project: {settings.GOOGLE_CLOUD_PROJECT_ID}, "
                    f"Location: {settings.GOOGLE_CLOUD_LOCATION})"
                )
            else:
                self._client = genai.Client()
                print("✅ Gemini client initialized using API Key")

            return self._client

        except Exception as e:
            print(f"❌ Failed to initialize Gemini client: {e}")
            raise

    def get_live_config(self) -> types.LiveConnectConfig:
        """
        Get the LiveConnectConfig for Gemini Live API.

        Returns:
            types.LiveConnectConfig: Configuration for live connection
        """
        if self._config is None:
            self._config = self._create_live_config()
        return self._config

    def _create_live_config(self) -> types.LiveConnectConfig:
        """Create the live connection configuration."""
        tool_declarations = [tool.declaration for tool in AllTools.get_all()]

        return types.LiveConnectConfig(
            response_modalities=["AUDIO"],
            system_instruction=self._system_prompt.render(),
            speech_config=types.SpeechConfig(
                language_code=settings.LANGUAGE_CODE,
                voice_config=types.VoiceConfig(
                    prebuilt_voice_config=types.PrebuiltVoiceConfig(
                        voice_name=settings.VOICE_NAME
                    )
                ),
            ),
            input_audio_transcription={},
            output_audio_transcription={},
            session_resumption=types.SessionResumptionConfig(handle=None),
            context_window_compression=types.ContextWindowCompressionConfig(
                sliding_window=types.SlidingWindow(),
            ),
            realtime_input_config=types.RealtimeInputConfig(
                automatic_activity_detection=types.AutomaticActivityDetection(
                    disabled=settings.DISABLE_VAD,
                    start_of_speech_sensitivity=types.StartSensitivity.START_SENSITIVITY_LOW,
                    end_of_speech_sensitivity=types.EndSensitivity.END_SENSITIVITY_LOW,
                    prefix_padding_ms=100,
                    silence_duration_ms=1200,
                ),
                turn_coverage=types.TurnCoverage.TURN_INCLUDES_ALL_INPUT,
            ),
            tools=[types.Tool(function_declarations=tool_declarations)],
        )

    @property
    def client(self) -> genai.Client:
        """Get the initialized client."""
        if self._client is None:
            raise RuntimeError(
                "Client not initialized. Call initialize_client() first."
            )
        return self._client


# Global client manager instance
gemini_manager = GeminiClientManager()

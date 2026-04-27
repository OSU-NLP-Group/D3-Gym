"""OpenAI API backend."""

import backoff
from openai import (
    OpenAI,
    APIConnectionError,
    APITimeoutError,
    RateLimitError,
    InternalServerError,
)

_RETRYABLE = (APIConnectionError, APITimeoutError, RateLimitError, InternalServerError)


@backoff.on_exception(backoff.expo, _RETRYABLE)
def _chat(client, engine, msg, temperature, top_p, max_tokens=4096):
    kwargs = dict(model=engine, messages=msg, top_p=top_p,
                  frequency_penalty=0, presence_penalty=0)
    if engine.startswith("gpt-5"):
        kwargs["max_completion_tokens"] = max_tokens
    else:
        kwargs["temperature"] = temperature
        kwargs["max_tokens"] = max_tokens
    return client.chat.completions.create(**kwargs)


class OpenaiEngine:
    def __init__(self, llm_engine_name):
        self.client = OpenAI(max_retries=10, timeout=120.0)
        self.llm_engine_name = llm_engine_name

    def respond(self, user_input, temperature, top_p, max_tokens=4096):
        response = _chat(
            self.client, self.llm_engine_name,
            user_input, temperature, top_p, max_tokens,
        )
        choice = response.choices[0]
        return (
            choice.message.content,
            response.usage.prompt_tokens,
            response.usage.completion_tokens,
            choice.finish_reason,
        )

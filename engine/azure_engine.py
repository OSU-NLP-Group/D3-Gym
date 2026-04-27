"""Azure OpenAI API backend."""

from openai import AzureOpenAI


def _chat(client, engine, msg, temperature, top_p, max_tokens=20000):
    return client.chat.completions.create(
        model=engine, messages=msg,
        temperature=temperature, max_tokens=max_tokens,
        top_p=top_p, frequency_penalty=0, presence_penalty=0,
    )


def _chat_o3(client, engine, msg, max_tokens=20000):
    return client.beta.chat.completions.parse(
        model=engine, messages=msg, max_completion_tokens=max_tokens,
    )


class AzureEngine:
    def __init__(self, llm_engine_name, api_key, api_version, azure_endpoint):
        self.client = AzureOpenAI(
            api_key=api_key, api_version=api_version,
            azure_endpoint=azure_endpoint,
        )
        self.llm_engine_name = llm_engine_name

    def respond(self, user_input, temperature, top_p, max_tokens=20000):
        try:
            if any(tag in self.llm_engine_name for tag in ("o3", "o4")):
                response = _chat_o3(
                    self.client, self.llm_engine_name, user_input, max_tokens,
                )
            else:
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
        except Exception as e:
            print(f"ERROR: Can't invoke '{self.llm_engine_name}' on Azure. Reason: {e}")
            return "ERROR", 0, 0, None

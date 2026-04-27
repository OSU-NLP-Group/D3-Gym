"""
LLM Engine router — selects the appropriate backend based on model name prefix.

Supported backends:
  - Azure OpenAI   : model names starting with "azure_"
  - OpenAI         : model names starting with "gpt" or "o1"
  - vLLM           : model names starting with "vllm_"
  - AWS Bedrock    : everything else (default)
"""


class LLMEngine:
    def __init__(self, llm_engine_name, api_key=None, api_version=None,
                 azure_endpoint=None, port=8000):
        self.llm_engine_name = llm_engine_name
        self.engine = None
        self.port = port

        if llm_engine_name.startswith("azure_"):
            from engine.azure_engine import AzureEngine
            self.engine = AzureEngine(
                llm_engine_name.split("azure_", 1)[-1],
                api_key, api_version, azure_endpoint,
            )
        elif llm_engine_name.startswith("gpt") or llm_engine_name.startswith("o1"):
            from engine.openai_engine import OpenaiEngine
            self.engine = OpenaiEngine(llm_engine_name)
        elif llm_engine_name.startswith("vllm_"):
            from engine.vllm_engine import VLLMEngine
            self.engine = VLLMEngine(
                llm_engine_name.replace("vllm_", "", 1), port=port,
            )
        else:
            from engine.bedrock_engine import BedrockEngine
            self.engine = BedrockEngine(llm_engine_name)

    def respond(self, user_input, temperature, top_p=None, max_tokens=None):
        if max_tokens is None:
            from engine.bedrock_engine import BedrockEngine
            max_tokens = 8000 if isinstance(self.engine, BedrockEngine) else 4000
        return self.engine.respond(user_input, temperature, top_p, max_tokens)

    def respond_with_thinking(self, user_input, max_tokens=16000,
                              budget_tokens=8000, save_raw_response_path=None):
        if not hasattr(self.engine, "respond_with_thinking"):
            raise NotImplementedError(
                f"Engine {type(self.engine).__name__} does not support extended thinking"
            )
        return self.engine.respond_with_thinking(
            user_input, max_tokens=max_tokens, budget_tokens=budget_tokens,
            save_raw_response_path=save_raw_response_path,
        )

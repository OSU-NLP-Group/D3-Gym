"""vLLM OpenAI-compatible server backend."""

import time

import backoff
import requests


class VLLMEngine:
    def __init__(self, llm_engine_name, api_key="token-abc123",
                 base_url="http://localhost:8000/v1", port=8000, **kwargs):
        self.llm_engine_name = llm_engine_name
        self.base_url = base_url.replace("8000", str(port))
        self.headers = {"Content-Type": "application/json"}

    @backoff.on_exception(backoff.expo, requests.exceptions.RequestException, max_tries=3)
    def _send_request(self, endpoint, data):
        response = requests.post(
            f"{self.base_url}/{endpoint}",
            headers=self.headers, json=data, timeout=1200,
        )
        if response.status_code != 200:
            raise requests.exceptions.RequestException(
                f"Status {response.status_code}: {response.text}"
            )
        return response.json()

    def respond(self, user_input, temperature=0.7, top_p=0.9, max_tokens=6000):
        start = time.time()
        try:
            data = {
                "model": self.llm_engine_name,
                "messages": user_input,
                "temperature": temperature,
                "top_p": top_p,
                "max_tokens": max_tokens,
            }
            if "qwen3" in self.llm_engine_name.lower():
                data["chat_template_kwargs"] = {"enable_thinking": False}

            response = self._send_request("chat/completions", data)
            choice = response["choices"][0]
            usage = response.get("usage", {})
            return (
                choice["message"]["content"],
                usage.get("prompt_tokens", 0),
                usage.get("completion_tokens", 0),
                choice.get("finish_reason"),
            )
        except Exception as e:
            print(f"ERROR: Can't invoke '{self.llm_engine_name}' on vLLM. Reason: {e}")
            return "ERROR", 0, 0, None
        finally:
            print(f"vLLM request took {time.time() - start:.2f}s")

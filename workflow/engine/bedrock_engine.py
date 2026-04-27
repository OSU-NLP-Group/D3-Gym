"""AWS Bedrock Converse API backend."""

import json
import os

import boto3
from botocore.client import Config
from botocore.exceptions import ClientError


def bedrock_converse_engine(client, engine, msg, temperature, top_p, max_tokens=8192):
    inference_config = {"maxTokens": max_tokens, "temperature": temperature}
    if top_p is not None:
        inference_config["topP"] = top_p
    return client.converse(
        modelId=engine,
        messages=msg,
        inferenceConfig=inference_config,
    )


class BedrockEngine:
    def __init__(self, llm_engine_name):
        region = os.environ.get(
            "AWS_REGION", os.environ.get("AWS_DEFAULT_REGION", "us-west-2")
        )
        self.client = boto3.client(
            "bedrock-runtime",
            region_name=region,
            config=Config(retries={"total_max_attempts": 10}),
        )
        self.thinking_client = boto3.client(
            "bedrock-runtime",
            region_name=region,
            config=Config(
                retries={"total_max_attempts": 10},
                read_timeout=600,
            ),
        )
        self.llm_engine_name = llm_engine_name

    def respond(self, user_input, temperature, top_p, max_tokens=8192):
        conversation = [
            {"role": turn["role"], "content": [{"text": turn["content"]}]}
            for turn in user_input
        ]
        try:
            response = bedrock_converse_engine(
                self.client, self.llm_engine_name,
                conversation, temperature, top_p, max_tokens,
            )
        except (ClientError, Exception) as e:
            print(f"ERROR: Can't invoke '{self.llm_engine_name}'. Reason: {e}")
            return "ERROR", 0, 0, None

        return (
            response["output"]["message"]["content"][0]["text"],
            response["usage"]["inputTokens"],
            response["usage"]["outputTokens"],
            response.get("stopReason"),
        )

    def respond_with_thinking(self, user_input, max_tokens=16000,
                              budget_tokens=8000, save_raw_response_path=None):
        conversation = [
            {"role": turn["role"], "content": [{"text": turn["content"]}]}
            for turn in user_input
        ]
        inference_config = {"maxTokens": max_tokens}
        additional_fields = {
            "thinking": {"type": "enabled", "budget_tokens": budget_tokens}
        }
        try:
            response = self.thinking_client.converse(
                modelId=self.llm_engine_name,
                messages=conversation,
                inferenceConfig=inference_config,
                additionalModelRequestFields=additional_fields,
            )
        except (ClientError, Exception) as e:
            print(f"ERROR: Can't invoke '{self.llm_engine_name}' with thinking. Reason: {e}")
            return {
                "thinking": "", "answer": "ERROR",
                "input_tokens": 0, "output_tokens": 0,
                "stop_reason": None, "raw_response": None, "error": str(e),
            }

        raw_serializable = json.loads(json.dumps(response, default=str))
        if save_raw_response_path:
            with open(save_raw_response_path, "w") as f:
                json.dump(raw_serializable, f, indent=2, ensure_ascii=False)

        thinking_text, answer_text = "", ""
        for block in response["output"]["message"]["content"]:
            if "reasoningContent" in block:
                reasoning = block["reasoningContent"]
                if "reasoningText" in reasoning:
                    rt = reasoning["reasoningText"]
                    thinking_text += rt.get("text", "") if isinstance(rt, dict) else str(rt)
                elif "text" in reasoning:
                    thinking_text += reasoning["text"]
            elif "text" in block:
                answer_text += block["text"]

        return {
            "thinking": thinking_text,
            "answer": answer_text,
            "input_tokens": response["usage"]["inputTokens"],
            "output_tokens": response["usage"]["outputTokens"],
            "stop_reason": response.get("stopReason"),
            "raw_response": raw_serializable,
        }

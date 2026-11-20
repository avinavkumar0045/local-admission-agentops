import httpx
from datetime import datetime, timezone
from opentelemetry import trace
from src.config import OLLAMA_BASE_URL, QWEN_MODEL
from src.agentops.telemetry import tracer, tracker
from src.agent.prompts import build_prompt, FALLBACK_RESPONSE

class LocalQwenGenerator:
    def __init__(self):
        self.base_url = f"{OLLAMA_BASE_URL}/api/generate"
        self.model_name = QWEN_MODEL

    async def generate_response(self, query: str, context: list, trace_id: str) -> str:
        start_time = datetime.now(timezone.utc)
        
        with tracer.start_as_current_span("llm.generation") as gen_span:
            # OpenTelemetry GenAI Semantic Conventions (CNCF Standard)
            gen_span.set_attribute("gen_ai.system", "ollama")
            gen_span.set_attribute("gen_ai.operation.name", "chat")
            gen_span.set_attribute("gen_ai.request.model", self.model_name)
            gen_span.set_attribute("gen_ai.request.temperature", 0.2)
            gen_span.set_attribute("gen_ai.request.max_tokens", 100)
            
            # Backward-compatible attribute
            gen_span.set_attribute("model", self.model_name)
            
            with tracer.start_as_current_span("prompt.construction") as prompt_span:
                context_texts = "\n\n".join([c["content"] for c in context]) if context else "No direct context available in knowledge base."
                prompt = build_prompt(query=query, context_texts=context_texts)
                prompt_span.set_attribute("prompt_length", len(prompt))
                prompt_span.set_attribute("gen_ai.prompt.characters", len(prompt))
            
            payload = {
                "model": self.model_name,
                "prompt": prompt,
                "stream": False,
                "options": {
                    "num_predict": 100,
                    "temperature": 0.2
                }
            }
            
            try:
                async with httpx.AsyncClient(timeout=180.0) as client:
                    response = await client.post(self.base_url, json=payload)
                    response.raise_for_status()
                    result = response.json()
                    answer = result.get("response", "Error generating response.")
                    
                    # Token Accounting via GenAI Semantic Conventions
                    prompt_tokens = result.get("prompt_eval_count", len(prompt) // 4)
                    completion_tokens = result.get("eval_count", 0)
                    total_tokens = prompt_tokens + completion_tokens
                    duration_ms = (datetime.now(timezone.utc) - start_time).total_seconds() * 1000
                    
                    gen_span.set_attribute("gen_ai.response.model", result.get("model", self.model_name))
                    gen_span.set_attribute("gen_ai.client.token.usage.prompt", prompt_tokens)
                    gen_span.set_attribute("gen_ai.client.token.usage.completion", completion_tokens)
                    gen_span.set_attribute("gen_ai.client.token.usage.total", total_tokens)
                    gen_span.set_attribute("gen_ai.client.operation.duration_ms", duration_ms)
                    
                    # Backward-compatible attribute
                    gen_span.set_attribute("completion_tokens", completion_tokens)
                    
                    tracker.emit_span(trace_id, "llm_generation", start_time, datetime.now(timezone.utc), "success")
                    return answer
            except Exception as e:
                gen_span.set_attribute("failure_class", "LLM_INFERENCE_ERROR")
                gen_span.set_status(trace.Status(trace.StatusCode.ERROR, str(e)))
                tracker.emit_span(trace_id, "llm_generation", start_time, datetime.now(timezone.utc), "error", str(e))
                raise

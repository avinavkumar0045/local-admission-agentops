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
            gen_span.set_attribute("model", self.model_name)
            
            with tracer.start_as_current_span("prompt.construction") as prompt_span:
                if not context:
                    return FALLBACK_RESPONSE
                context_texts = "\n\n".join([c["content"] for c in context])
                prompt = build_prompt(query=query, context_texts=context_texts)
                prompt_span.set_attribute("prompt_length", len(prompt))
            
            payload = {
                "model": self.model_name,
                "prompt": prompt,
                "stream": False
            }
            
            try:
                async with httpx.AsyncClient(timeout=180.0) as client:
                    response = await client.post(self.base_url, json=payload)
                    response.raise_for_status()
                    result = response.json()
                    answer = result.get("response", "Error generating response.")
                    gen_span.set_attribute("completion_tokens", result.get("eval_count", 0))
                    
                    tracker.emit_span(trace_id, "llm_generation", start_time, datetime.now(timezone.utc), "success")
                    return answer
            except Exception as e:
                gen_span.set_attribute("failure_class", "LLM_INFERENCE_ERROR")
                gen_span.set_status(trace.Status(trace.StatusCode.ERROR, str(e)))
                tracker.emit_span(trace_id, "llm_generation", start_time, datetime.now(timezone.utc), "error", str(e))
                raise

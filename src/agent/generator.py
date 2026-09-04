"""
LLM Generation Module
Primary Responsibility: Manages communication with the local Qwen LLM via Ollama.
"""
import httpx
from datetime import datetime, timezone
from opentelemetry import trace
from src.config import OLLAMA_BASE_URL, QWEN_MODEL
from src.agentops.telemetry import tracer, tracker

class LocalQwenGenerator:
    def __init__(self):
        self.base_url = f"{OLLAMA_BASE_URL}/api/generate"
        self.model_name = QWEN_MODEL

    async def generate_response(self, query: str, context: list, trace_id: str) -> str:
        start_time = datetime.now(timezone.utc)
        
        with tracer.start_as_current_span("prompt.construction") as prompt_span:
            context_text = "\n\n".join([f"Source ({r['metadata']['source']}): {r['content']}" for r in context])
            prompt = f"""You are a helpful university admission assistant.
Use the following context to answer the user's question accurately. If the answer is not in the context, say "I don't know based on the provided policies."

Context:
{context_text}

Question:
{query}

Answer:"""
            prompt_span.set_attribute("prompt_version", "1.0")
            prompt_span.set_attribute("context_size", len(context))
            prompt_span.set_attribute("prompt_length", len(prompt))

        payload = {
            "model": self.model_name,
            "prompt": prompt,
            "stream": False
        }

        with tracer.start_as_current_span("llm.generation") as gen_span:
            gen_span.set_attribute("model_name", self.model_name)
            gen_span.set_attribute("temperature", 0.7) # default ollama
            
            try:
                async with httpx.AsyncClient(timeout=120.0) as client:
                    response = await client.post(self.base_url, json=payload)
                    response.raise_for_status()
                    result = response.json()
                    answer = result.get("response", "")
                    
                    tracker.emit_span(
                        trace_id=trace_id,
                        span_type="llm_generation",
                        start_time=start_time,
                        end_time=datetime.now(timezone.utc),
                        status="success",
                        metadata={"prompt_length": len(prompt), "model": self.model_name}
                    )
                    return answer
                    
            except httpx.ReadTimeout as e:
                gen_span.set_attribute("failure_class", "LLM_TIMEOUT")
                gen_span.set_status(trace.Status(trace.StatusCode.ERROR))
                tracker.emit_span(trace_id, "llm_generation", start_time, datetime.now(timezone.utc), "failure", str(e))
                raise e
            except Exception as e:
                gen_span.set_attribute("failure_class", "LLM_ERROR")
                gen_span.set_status(trace.Status(trace.StatusCode.ERROR))
                tracker.emit_span(trace_id, "llm_generation", start_time, datetime.now(timezone.utc), "failure", str(e))
                raise e

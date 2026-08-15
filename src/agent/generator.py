"""
LLM Generation Module
Primary Responsibility: Manages communication with the local Qwen LLM via Ollama.
Why it exists: To encapsulate model inference logic and ensure LLM latency and prompt sizes are traced via AgentOps.
"""
import httpx
from datetime import datetime
from src.config import OLLAMA_BASE_URL, QWEN_MODEL
from src.agentops.telemetry import tracker

class LocalQwenGenerator:
    def __init__(self):
        # httpx is chosen for lightweight, asynchronous, and modular HTTP requests.
        self.base_url = f"{OLLAMA_BASE_URL}/api/generate"
        self.model_name = QWEN_MODEL

    async def generate_response(self, query: str, context: list, trace_id: str) -> str:
        start_time = datetime.now()
        
        # Build prompt using retrieved context chunks
        context_text = "\n\n".join([f"Source ({r['metadata']['source']}): {r['content']}" for r in context])
        
        prompt = f"""You are a helpful university admission assistant.
Use the following context to answer the user's question accurately. If the answer is not in the context, say "I don't know based on the provided policies."

Context:
{context_text}

Question:
{query}

Answer:"""

        payload = {
            "model": self.model_name,
            "prompt": prompt,
            "stream": False
        }

        try:
            # Using httpx for non-blocking, fast local requests
            async with httpx.AsyncClient(timeout=120.0) as client:
                response = await client.post(self.base_url, json=payload)
                response.raise_for_status()
                result = response.json()
                answer = result.get("response", "")
                
                tracker.emit_span(
                    trace_id=trace_id,
                    span_type="llm_generation",
                    start_time=start_time,
                    end_time=datetime.now(),
                    status="success",
                    metadata={"prompt_length": len(prompt), "model": self.model_name}
                )
                return answer
                
        except Exception as e:
            tracker.emit_span(
                trace_id=trace_id,
                span_type="llm_generation",
                start_time=start_time,
                end_time=datetime.now(),
                status="failure",
                error_msg=str(e)
            )
            raise e

"""
FastAPI Orchestrator
Primary Responsibility: Exposes the HTTP endpoints for the admission assistant.
Why it exists: To act as the entry point for frontend UIs, orchestrating the retriever, generator, and master traces.
"""
import uuid
from datetime import datetime, timezone
from fastapi import FastAPI, HTTPException
from pydantic import BaseModel

from src.agent.retriever import FAISSRetriever
from src.agent.generator import LocalQwenGenerator
from src.agentops.telemetry import tracker

app = FastAPI(title="AgentOps Admission API")

# Initialize modular components
retriever = FAISSRetriever()
generator = LocalQwenGenerator()

class QueryRequest(BaseModel):
    query: str

class QueryResponse(BaseModel):
    trace_id: str
    answer: str
    context: list

@app.post("/query", response_model=QueryResponse)
async def handle_query(request: QueryRequest):
    trace_id = str(uuid.uuid4())
    trace_start = datetime.now(timezone.utc)
    
    try:
        # 1. Retrieve Context
        context = retriever.retrieve(query=request.query, trace_id=trace_id)
        
        # 2. Generate Answer
        answer = await generator.generate_response(
            query=request.query, 
            context=context, 
            trace_id=trace_id
        )
        
        # Emit root span for full query lifecycle
        tracker.emit_span(
            trace_id=trace_id,
            span_type="full_query_lifecycle",
            start_time=trace_start,
            end_time=datetime.now(timezone.utc),
            status="success",
            metadata={"query": request.query}
        )
        
        # Returning exact chunks for Phase 6 Explainability View
        return QueryResponse(
            trace_id=trace_id,
            answer=answer,
            context=context 
        )
        
    except Exception as e:
        tracker.emit_span(
            trace_id=trace_id,
            span_type="full_query_lifecycle",
            start_time=trace_start,
            end_time=datetime.now(timezone.utc),
            status="failure",
            error_msg=str(e),
            metadata={"query": request.query}
        )
        raise HTTPException(status_code=500, detail="Internal Server Error during processing.")

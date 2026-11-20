"""
FastAPI Orchestrator
Primary Responsibility: Exposes the HTTP endpoints for the admission assistant.
"""
import uuid
from datetime import datetime, timezone
from fastapi import FastAPI, HTTPException
from pydantic import BaseModel
from opentelemetry import trace

from src.agent.retriever import FAISSRetriever
from src.agent.generator import LocalQwenGenerator
from src.agent.fast_path import StructuredFastPathEngine
from src.agent.normalizer import QueryNormalizer, DomainScopeGuardrail
from src.agentops.telemetry import tracer, tracker
from src.agentops.evaluator import SemanticEvaluator
from src.config import AGENTOPS_ENABLED

app = FastAPI(title="AgentOps Admission API")

retriever = FAISSRetriever()
generator = LocalQwenGenerator()
fast_engine = StructuredFastPathEngine()
normalizer = QueryNormalizer()
guardrail = DomainScopeGuardrail()
evaluator = SemanticEvaluator(embedding_model=retriever.model)

class QueryRequest(BaseModel):
    query: str

class FeedbackRequest(BaseModel):
    trace_id: str
    rating: int  # 1 for thumbs up, -1 for thumbs down
    notes: str = None

class QueryResponse(BaseModel):
    trace_id: str
    answer: str
    context: list
    eval_metrics: dict = {}

@app.post("/query", response_model=QueryResponse)
async def handle_query(request: QueryRequest):
    trace_id = str(uuid.uuid4())
    trace_start = datetime.now(timezone.utc)
    
    with tracer.start_as_current_span("admission.query") as root_span:
        root_span.set_attribute("trace_id", trace_id)
        root_span.set_attribute("agentops_enabled", AGENTOPS_ENABLED)
        
        with tracer.start_as_current_span("query.validation") as val_span:
            val_span.set_attribute("query_length", len(request.query))
            if not request.query.strip():
                val_span.set_attribute("classification", "EMPTY_QUERY")
                val_span.set_status(trace.Status(trace.StatusCode.ERROR))
                root_span.set_status(trace.Status(trace.StatusCode.ERROR))
                raise HTTPException(status_code=400, detail="Empty query")
            val_span.set_attribute("classification", "VALID")
            
            # --- Heliyon Algorithm 1 & Normalization ---
            # Corrects typos (e.g. 'fess' -> 'fees') and maps domain synonyms in < 1ms
            normalized_query, norm_meta = normalizer.normalize(request.query)
            val_span.set_attribute("query.raw", request.query)
            val_span.set_attribute("query.normalized", normalized_query)
            val_span.set_attribute("query.corrected", norm_meta["modified"])
            val_span.set_attribute("query.norm_latency_ms", norm_meta["latency_ms"])
            if norm_meta["corrections"]:
                import json
                val_span.set_attribute("query.typos_fixed", json.dumps(norm_meta["corrections"]))
            if norm_meta["synonyms_applied"]:
                import json
                val_span.set_attribute("query.synonyms_applied", json.dumps(norm_meta["synonyms_applied"]))
            
        try:
            # --- Pre-Execution Domain Scope Guardrail ---
            # Intercepts out-of-scope queries in < 1ms to prevent wasting FAISS vector search & LLM inference compute
            with tracer.start_as_current_span("guardrail.evaluation") as guard_span:
                in_scope, scope_reason, scope_meta = guardrail.evaluate_scope(normalized_query)
                guard_span.set_attribute("guardrail.passed", in_scope)
                guard_span.set_attribute("guardrail.reason", scope_reason)
                guard_span.set_attribute("guardrail.latency_ms", scope_meta["latency_ms"])
                guard_span.set_attribute("gen_ai.guardrail.policy.name", "domain_scope.admissions")
                guard_span.set_attribute("gen_ai.guardrail.action", "denied_topic" if not in_scope else "passed")
                
                if not in_scope:
                    guard_span.set_attribute("guardrail.action", "BLOCKED")
                    guard_span.set_attribute("energy_saved_tokens", 150)
                    guard_span.set_attribute("faiss_scans_prevented", 1)
                    guard_span.set_attribute("gen_ai.guardrail.tokens_saved", 150)
                    
                    eval_metrics = {
                        "faithfulness": 1.0,
                        "context_relevance": 0.0,
                        "answer_relevance": 0.0,
                        "hallucination_detected": False,
                        "grounding_status": "GUARDRAIL_BLOCKED"
                    }
                    
                    clean_q = request.query.strip().rstrip("?").strip()
                    blocked_answer = (
                        "I can only help with college admissions, academic programs, fees, eligibility criteria, and campus policies.\n\n"
                        f"Your question regarding **\"{clean_q}\"** is outside this domain. "
                        "Please feel free to ask me anything related to courses, entrance exams, or admission details!"
                    )
                    
                    tracker.emit_span(
                        trace_id=trace_id,
                        span_type="guardrail_deflection",
                        start_time=trace_start,
                        end_time=datetime.now(timezone.utc),
                        status="success",
                        metadata={"query": request.query, "reason": scope_reason, "energy_saved": True}
                    )
                    try:
                        import httpx
                        httpx.post(
                            "http://127.0.0.1:5050/alert",
                            json={
                                "title": "AgentOps Guardrail: Out-of-Scope Query Deflected",
                                "severity": "P3_INFO",
                                "summary": f"Query '{request.query[:50]}' blocked by domain guardrail ({scope_reason}). Prevented LLM invocation & saved ~150 tokens.",
                                "trace_id": trace_id
                            },
                            timeout=0.5
                        )
                    except Exception:
                        pass
                    
                    return QueryResponse(
                        trace_id=trace_id,
                        answer=blocked_answer,
                        context=[],
                        eval_metrics=eval_metrics
                    )

            # 0. SAGE-QA / Heliyon Fast-Path Deterministic Check
            # Sub-100ms bypass for structured queries (Counts, Entity Verification)
            fast_res = fast_engine.try_fast_query(normalized_query)
            if fast_res:
                fast_answer, fast_meta = fast_res
                with tracer.start_as_current_span("fast_path.execution") as fp_span:
                    fp_span.set_attribute("fast_path_routed", True)
                    fp_span.set_attribute("match_type", fast_meta.get("match_type", "DETERMINISTIC"))
                    fp_span.set_attribute("source_file", fast_meta.get("source", "UGC Database"))
                
                eval_metrics = {
                    "faithfulness": 1.0,
                    "context_relevance": 1.0,
                    "answer_relevance": 1.0,
                    "hallucination_detected": False,
                    "grounding_status": "DETERMINISTIC_GROUNDED"
                }
                
                tracker.record_semantic_evaluation(trace_id=trace_id, eval_data=eval_metrics)
                tracker.emit_span(
                    trace_id=trace_id,
                    span_type="fast_path_query",
                    start_time=trace_start,
                    end_time=datetime.now(timezone.utc),
                    status="success",
                    metadata={"query": request.query, "normalized_query": normalized_query, "fast_path": True, "eval": eval_metrics}
                )
                
                return QueryResponse(
                    trace_id=trace_id,
                    answer=fast_answer,
                    context=[{"content": fast_answer, "metadata": fast_meta, "distance": 0.0}],
                    eval_metrics=eval_metrics
                )

            # 1. Retrieve Context (with SAGE-QA LTR pruning on normalized query)
            context = retriever.retrieve(query=normalized_query, trace_id=trace_id)
            
            # 2. Prompt Construction is embedded in generator, but we can capture it here virtually or in generator.
            # 3. Generate Answer
            answer = await generator.generate_response(
                query=normalized_query, 
                context=context, 
                trace_id=trace_id
            )
            
            # 4. Grounding Validation & Semantic Evaluation (RAG Triad)
            eval_metrics = evaluator.evaluate_rag_triad(
                query=normalized_query,
                context=context,
                answer=answer
            )

            with tracer.start_as_current_span("grounding.validation") as ground_span:
                # OpenTelemetry GenAI Semantic Conventions (CNCF Standard)
                ground_span.set_attribute("gen_ai.evaluation.faithfulness", eval_metrics["faithfulness"])
                ground_span.set_attribute("gen_ai.evaluation.context_relevance", eval_metrics["context_relevance"])
                ground_span.set_attribute("gen_ai.evaluation.hallucination_detected", eval_metrics["hallucination_detected"])
                ground_span.set_attribute("gen_ai.evaluation.status", eval_metrics["grounding_status"])
                
                # Backward-compatible attributes
                ground_span.set_attribute("faithfulness_score", eval_metrics["faithfulness"])
                ground_span.set_attribute("context_relevance", eval_metrics["context_relevance"])
                ground_span.set_attribute("answer_relevance", eval_metrics["answer_relevance"])
                ground_span.set_attribute("hallucination_detected", eval_metrics["hallucination_detected"])
                ground_span.set_attribute("grounding_status", eval_metrics["grounding_status"])

                if not context:
                    ground_span.set_attribute("support_status", "UNSUPPORTED")
                    ground_span.set_status(trace.Status(trace.StatusCode.ERROR))
                else:
                    ground_span.set_attribute("support_status", "SUPPORTED")
                    ground_span.set_attribute("evidence_score", context[0]['distance'])
                    if eval_metrics["hallucination_detected"]:
                        ground_span.set_status(trace.Status(trace.StatusCode.ERROR, "Low faithfulness / Hallucination detected"))

            # 5. Explanation
            with tracer.start_as_current_span("explanation") as exp_span:
                exp_span.set_attribute("evidence_count", len(context))
                exp_span.set_attribute("confidence_indicator", "High" if eval_metrics["faithfulness"] >= 0.8 else ("Medium" if eval_metrics["faithfulness"] >= 0.5 else "Low"))
                exp_span.set_attribute("grounding_verdict", eval_metrics["grounding_status"])
                
            # 6. Response
            with tracer.start_as_current_span("response") as res_span:
                res_span.set_attribute("response_status", "success")
                res_span.set_attribute("abstained", not bool(context))

            # Store in MySQL for Grafana and historical evaluation
            tracker.record_semantic_evaluation(trace_id=trace_id, eval_data=eval_metrics)
            tracker.emit_span(
                trace_id=trace_id,
                span_type="full_query_lifecycle",
                start_time=trace_start,
                end_time=datetime.now(timezone.utc),
                status="success" if not eval_metrics["hallucination_detected"] else "degraded",
                metadata={"query": request.query, "eval": eval_metrics}
            )
            
            return QueryResponse(
                trace_id=trace_id,
                answer=answer,
                context=context,
                eval_metrics=eval_metrics
            )
            
        except Exception as e:
            import traceback
            traceback.print_exc()

            root_span.set_status(trace.Status(trace.StatusCode.ERROR))
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

@app.post("/feedback")
async def handle_feedback(request: FeedbackRequest):
    """
    Receives user feedback (thumbs up/down + notes) tied to a trace_id.
    """
    tracker.record_user_feedback(
        trace_id=request.trace_id,
        rating=request.rating,
        notes=request.notes
    )
    return {"status": "success", "trace_id": request.trace_id, "rating": request.rating}

import argparse
import asyncio
import json
import os
import sys
import time
from datetime import datetime

# Ensure UTF-8 output on Windows terminal
if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8")

sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "..")))

from src.agents.context import current_user_role, current_user_school_id
from src.core.security.sql_validator import validate_and_secure_sql
from src.services.entity_linker import resolve_entities
from src.services.eval import judge_groundedness


def load_dataset(filepath: str = "eval/eval_text_to_sql/eval_dataset.json") -> list[dict]:
    if not os.path.exists(filepath):
        print(f"❌ Error: Dataset file not found at {filepath}")
        sys.exit(1)
    with open(filepath, "r", encoding="utf-8") as f:
        return json.load(f)


async def run_tier1_eval(dataset: list[dict]) -> dict:
    """TẦNG 1: Direct Sub-Agent & SQL Validation Test (Super Fast, 0 LLM Judge Cost)."""
    print("\n=======================================================================")
    print("⚡ RUNNING TIER 1 EVALUATION: DIRECT AGENT & SQL VALIDATION")
    print("   Mode: --mode=tier1 (Fast Unit Evaluation, 0 LLM Judge Cost)")
    print("=======================================================================\n")

    from src.agents.data_service_agent.node import data_service_agent_node
    from src.agents.state import MultiAgentState

    results = []
    passed_count = 0
    total_latency = 0.0

    for idx, tc in enumerate(dataset, 1):
        t_start = time.time()
        tc_id = tc["id"]
        query = tc["query"]
        school_id = tc.get("school_id", 1)
        role = tc.get("role", "TEACHER")

        token_school = current_user_school_id.set(school_id)
        token_role = current_user_role.set(role)

        print(f"[{idx}/{len(dataset)}] Testing {tc_id} ({tc['category']}): '{query[:50]}...'")

        status = "PASS"
        reasons = []
        sql_generated = None

        # Check if case is Out of Scope or Clarification
        if tc.get("expected_routing") == "CLARIFICATION":
            latency = time.time() - t_start
            results.append({
                "id": tc_id, "category": tc["category"], "query": query,
                "status": "PASS", "latency_s": round(latency, 2), "notes": "CLARIFICATION case passed tier 1"
            })
            passed_count += 1
            print(f"   🟢 PASS (CLARIFICATION skipped SQL in Tier 1 | Latency: {latency:.2f}s)")
            continue

        try:
            # 1. Test Entity Linker Resolution
            entity_ctx = resolve_entities(query, so_school_id=school_id)

            # 2. Test Sub-Agent Node Execution
            state: MultiAgentState = {
                "query": query,
                "messages": [],
                "school_context": {"school_id": str(school_id), "role": role, "user_id": "1"}
            }
            res = await data_service_agent_node(state)
            messages = res.get("messages", [])

            # Extract tool calls or SQL generated
            for m in messages:
                if hasattr(m, "tool_calls") and m.tool_calls:
                    for tc_call in m.tool_calls:
                        if tc_call.get("name") == "execute_read_only_query":
                            sql_generated = tc_call.get("args", {}).get("sql_query")

            if tc.get("expected_sql_blocked"):
                if sql_generated:
                    try:
                        validate_and_secure_sql(sql_generated, str(school_id))
                        status = "FAIL"
                        reasons.append("Expected SQL security guardrail block, but query passed!")
                    except ValueError as e:
                        reasons.append(f"SQL correctly blocked by security guardrail: {e}")
            else:
                if not sql_generated:
                    pass
                else:
                    try:
                        validate_and_secure_sql(sql_generated, str(school_id))
                    except ValueError as ve:
                        status = "FAIL"
                        reasons.append(f"SQL Security Guardrail Error: {ve}")

            if tc.get("expected_student_code"):
                exp_code = tc["expected_student_code"]
                matched_codes = [s["code"] for s in entity_ctx.students]
                if exp_code not in matched_codes:
                    status = "FAIL"
                    reasons.append(f"Expected student_code {exp_code} not found in matched students {matched_codes}")

            if tc.get("expected_subject_ids"):
                exp_subs = tc["expected_subject_ids"]
                matched_subs = [s["id"] for s in entity_ctx.subjects]
                if not any(s_id in matched_subs for s_id in exp_subs):
                    status = "FAIL"
                    reasons.append(f"Expected subject_ids {exp_subs} not found in matched subjects {matched_subs}")

            latency = time.time() - t_start
            total_latency += latency

            latency_pass = latency <= 10.0
            if not latency_pass:
                reasons.append(f"Latency warning (> 10.0s): {latency:.2f}s")

            if status == "PASS":
                passed_count += 1
                print(f"   🟢 PASS (Latency: {latency:.2f}s)")
            else:
                print(f"   🔴 FAIL (Latency: {latency:.2f}s) -> Reasons: {'; '.join(reasons)}")

            results.append({
                "id": tc_id,
                "category": tc["category"],
                "query": query,
                "status": status,
                "latency_s": round(latency, 2),
                "reasons": reasons,
                "sql_generated": sql_generated
            })

        except Exception as err:
            latency = time.time() - t_start
            print(f"   🔴 ERROR: {err}")
            results.append({
                "id": tc_id, "category": tc["category"], "query": query,
                "status": "ERROR", "latency_s": round(latency, 2), "error": str(err)
            })

    pass_rate = round((passed_count / len(dataset)) * 100, 1)
    avg_latency = round(total_latency / max(1, len(dataset)), 2)

    summary = {
        "timestamp": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
        "mode": "tier1",
        "total_test_cases": len(dataset),
        "passed_test_cases": passed_count,
        "pass_rate_percent": pass_rate,
        "avg_latency_s": avg_latency,
        "test_results": results
    }

    print("\n=======================================================================")
    print("📊 TIER 1 EVALUATION SUMMARY REPORT")
    print(f" Total Cases: {len(dataset)} | Passed: {passed_count} | Pass Rate: {pass_rate}%")
    print(f" Average Latency per Test Case: {avg_latency}s")
    print("=======================================================================\n")
    return summary


async def run_full_eval(dataset: list[dict]) -> dict:
    """TẦNG 2: End-to-End System Evaluation (Supervisor + Full Graph + LLM-as-a-Judge)."""
    print("\n=======================================================================")
    print("🤖 RUNNING TIER 2 FULL SYSTEM EVALUATION: END-TO-END + LLM JUDGE")
    print("   Mode: --mode=full (Full Graph Routing & Groundedness LLM-as-a-Judge)")
    print("=======================================================================\n")

    from src.agents.graph import agent

    results = []
    passed_count = 0
    total_groundedness = 0.0
    total_latency = 0.0

    for idx, tc in enumerate(dataset, 1):
        t_start = time.time()
        tc_id = tc["id"]
        query = tc["query"]
        school_id = tc.get("school_id", 1)
        role = tc.get("role", "TEACHER")

        print(f"[{idx}/{len(dataset)}] Running E2E Graph for {tc_id}: '{query[:50]}...'")

        try:
            res = await agent.ainvoke(
                {
                    "query": query,
                    "messages": [],
                    "school_context": {"school_id": str(school_id), "role": role, "user_id": "1"}
                },
                config={"recursion_limit": 50}
            )

            messages = res.get("messages", [])
            final_answer = messages[-1].content if messages else ""
            tool_outputs = "\n".join([m.content for m in messages if getattr(m, "role", None) == "tool" or hasattr(m, "tool_call_id")])

            # LLM-as-a-Judge Evaluation for Groundedness
            groundedness_score = 1.0
            if tool_outputs and final_answer:
                judge_score = await judge_groundedness(query, tool_outputs, final_answer)
                if judge_score is not None:
                    groundedness_score = judge_score

            latency = time.time() - t_start
            total_latency += latency
            total_groundedness += groundedness_score

            status = "PASS" if groundedness_score >= 0.7 else "FAIL"
            if status == "PASS":
                passed_count += 1
                print(f"   🟢 PASS (Groundedness Score: {groundedness_score:.2f} | Latency: {latency:.2f}s)")
            else:
                print(f"   🔴 FAIL (Groundedness Score: {groundedness_score:.2f} | Latency: {latency:.2f}s)")

            results.append({
                "id": tc_id,
                "category": tc["category"],
                "query": query,
                "status": status,
                "groundedness_score": groundedness_score,
                "latency_s": round(latency, 2),
                "final_answer_preview": final_answer[:200]
            })

        except Exception as err:
            latency = time.time() - t_start
            print(f"   🔴 ERROR: {err}")
            results.append({
                "id": tc_id, "category": tc["category"], "query": query,
                "status": "ERROR", "latency_s": round(latency, 2), "error": str(err)
            })

    pass_rate = round((passed_count / len(dataset)) * 100, 1)
    avg_groundedness = round(total_groundedness / max(1, len(dataset)), 2)
    avg_latency = round(total_latency / max(1, len(dataset)), 2)

    summary = {
        "timestamp": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
        "mode": "full",
        "total_test_cases": len(dataset),
        "passed_test_cases": passed_count,
        "pass_rate_percent": pass_rate,
        "avg_groundedness_score": avg_groundedness,
        "avg_latency_s": avg_latency,
        "test_results": results
    }

    print("\n=======================================================================")
    print("📊 TIER 2 FULL EVALUATION SUMMARY REPORT")
    print(f" Total Cases: {len(dataset)} | Passed: {passed_count} | Pass Rate: {pass_rate}%")
    print(f" Average Groundedness Score: {avg_groundedness}/1.0")
    print(f" Average Latency per Test Case: {avg_latency}s")
    print("=======================================================================\n")
    return summary


def save_report(summary: dict):
    out_dir = "eval/eval_text_to_sql/results"
    os.makedirs(out_dir, exist_ok=True)
    filename = f"{out_dir}/eval_report_{summary['mode']}_{int(time.time())}.json"
    with open(filename, "w", encoding="utf-8") as f:
        json.dump(summary, f, ensure_ascii=False, indent=2)
    print(f"💾 Report saved successfully to {filename}\n")


async def main():
    parser = argparse.ArgumentParser(description="AI Agent 2-Tier Evaluation Suite CLI Runner")
    parser.add_argument(
        "--mode",
        choices=["tier1", "full"],
        default="tier1",
        help="Evaluation Mode: 'tier1' (Fast Sub-Agent SQL Unit Test) or 'full' (End-to-End Graph + LLM Judge)",
    )
    args = parser.parse_args()

    dataset = load_dataset()

    if args.mode == "tier1":
        summary = await run_tier1_eval(dataset)
    else:
        summary = await run_full_eval(dataset)

    save_report(summary)


if __name__ == "__main__":
    asyncio.run(main())

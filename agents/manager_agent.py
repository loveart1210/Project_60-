"""
Manager Agent – Orchestrates the entire multi-agent summarization workflow.

Workflow:
  Phase 1 – Planning Loop:
    Planner → Planner-Observation → Planner-Reflection
    (loop until Reflection decides "finalize" or max iterations)

  Phase 2 – Execution Loop:
    For each step in the finalized roadmap:
      Execution → Exec-Observation → Exec-Reflection
      (retry if needed, then proceed to next step)
"""

from __future__ import annotations

import json
from typing import Any, Dict, List, Optional

from agents.base_agent import BaseAgent
from agents.planner_agent import PlannerAgent
from agents.planner_observation_agent import PlannerObservationAgent
from agents.planner_reflection_agent import PlannerReflectionAgent
from agents.execution_agent import ExecutionAgent
from agents.execution_observation_agent import ExecutionObservationAgent
from agents.execution_reflection_agent import ExecutionReflectionAgent
from session_manager import SessionManager
from llm_loader import LLMManager
from debug_logger import DebugLogger
import vn_tools
import config


class ManagerAgent(BaseAgent):

    def __init__(self) -> None:
        super().__init__(
            name="Manager Agent",
            role_description=(
                "Agent quản lý toàn bộ tiến trình tóm tắt văn bản tiếng Việt. "
                "Điều phối Planning loop và Execution loop."
            ),
        )
        # Sub-agents
        self.planner = PlannerAgent()
        self.planner_obs = PlannerObservationAgent()
        self.planner_ref = PlannerReflectionAgent()
        self.executor = ExecutionAgent()
        self.exec_obs = ExecutionObservationAgent()
        self.exec_ref = ExecutionReflectionAgent()
        # State
        self.session = SessionManager()

    def run(self, context: Dict[str, Any]) -> Dict[str, Any]:
        """Not used directly – use run_workflow instead."""
        return self.run_workflow(context["input_text"], context["style"])

    # ==================================================================
    # Main entry point
    # ==================================================================

    def run_workflow(self, input_text: str, style: str, resume: bool = False) -> Dict[str, Any]:
        """Run the full summarization workflow. 
        If resume=True, attempts to load state from sessions.json.
        """
        # --- Initialize Debug Logger ---
        debug = DebugLogger()
        debug.reset()  # Clean slate for each run

        if resume and self.session.load_existing():
            sid = self.session.session["session_id"]
            print(f"\n{'='*60}")
            print(f"  RESUMING Session: {sid}  |  Style: {style}")
            print(f"{'='*60}\n")
            input_text = self.session.session.get("input_text", input_text)
        else:
            # Initialise brand new session
            sid = self.session.create_session(input_text, style)
            # Store input text in session for full persistence
            self.session.session["input_text"] = input_text
            self.session._save_session()
            print(f"\n{'='*60}")
            print(f"  NEW Session: {sid}  |  Style: {style}")
            print(f"{'='*60}\n")

        # Pre-compute text stats
        word_count = vn_tools.count_words(input_text)
        sentences = vn_tools.split_sentences(input_text)
        compression = vn_tools.compute_compression_target(word_count)

        base_context: Dict[str, Any] = {
            "input_text": input_text,
            "style": style,
            "word_count": word_count,
            "sentences": sentences,
            "compression": compression,
        }

        try:
            # Determine start phase
            current_phase = self.session.session.get("current_phase", "planning")

            # Phase 1 – Planning
            roadmap = self.session.get_latest_roadmap()
            if not roadmap or current_phase == "planning":
                print("\n" + "="*60)
                print("  PHASE 1: PLANNING")
                print("="*60)
                # Ensure agent model is loaded for planning
                self.llm.load_agent_model()
                roadmap = self._run_planning_loop(base_context)
                self.session.update_phase("execution")
            else:
                print(f"\n✅ Roadmap already finalized (Iteration {self.session.session.get('iteration_count')}). Skipping Planning.")

            # Phase 2 – Execution
            print("\n" + "="*60)
            print("  PHASE 2: EXECUTION")
            print("="*60)

            final_output = self._run_execution_loop(base_context, roadmap)

            # Save output
            self.session.save_output(final_output)
            self.session.add_history("manager", "workflow_complete", "Hoàn thành toàn bộ workflow")

            debug.log_step(
                step_name="workflow_complete",
                agent_name="Manager Agent",
                phase="workflow",
                output_data=final_output,
            )

            print("\n" + "="*60)
            print("  WORKFLOW COMPLETE")
            print("="*60)

            return final_output
        finally:
            # Always save debug log, even on error
            debug.save()

    # ==================================================================
    # Phase 1 – Planning Loop
    # ==================================================================

    def _run_planning_loop(self, base_context: Dict[str, Any]) -> Dict[str, Any]:
        revision_instructions = ""
        roadmap = None
        debug = DebugLogger()

        for iteration in range(1, config.MAX_PLANNING_ITERATIONS + 1):
            version_key = f"v{iteration}"
            print(f"\n--- Planning iteration {iteration} ---")

            # Step 1: Planner creates/revises roadmap
            print(f"  [Planner] Building roadmap {version_key} ...")
            planner_ctx = {
                **base_context,
                "tools": ["word_tokenize", "sent_tokenize", "chunk_text", "summarize_chunk", "verify_claim"],
                "revision_instructions": revision_instructions,
            }
            roadmap = self.planner.run(planner_ctx)
            debug.log_step(
                step_name=f"planning_iter{iteration}_planner",
                agent_name="Planner Agent",
                phase="planning",
                input_summary=f"iteration={iteration}, revision='{revision_instructions[:100]}'",
                output_data=roadmap,
            )
            self.session.save_roadmap_version(version_key, roadmap)
            self.session.add_history(
                "planner", "create_roadmap",
                f"Roadmap {version_key} created",
                {"version": version_key},
            )
            print(f"  [Planner] Roadmap {version_key} created ✓")

            # Step 2: Planner-Observation analyses roadmap
            print(f"  [Planner-Observation] Analyzing roadmap ...")
            obs_ctx = {"roadmap": roadmap, "input_text": base_context["input_text"]}
            observation = self.planner_obs.run(obs_ctx)
            debug.log_step(
                step_name=f"planning_iter{iteration}_observation",
                agent_name="Planner-Observation Agent",
                phase="planning",
                input_summary=f"roadmap_keys={list(roadmap.keys()) if isinstance(roadmap, dict) else 'not_dict'}",
                output_data=observation,
            )
            self.session.add_history(
                "planner_observation", "analyze_roadmap",
                f"Observation for {version_key} complete",
            )
            print(f"  [Planner-Observation] Analysis complete ✓")

            # Step 3: Planner-Reflection evaluates
            print(f"  [Planner-Reflection] Evaluating ...")
            ref_result = self.planner_ref.run({"observation": observation})
            debug.log_step(
                step_name=f"planning_iter{iteration}_reflection",
                agent_name="Planner-Reflection Agent",
                phase="planning",
                input_summary=f"observation_keys={list(observation.keys()) if isinstance(observation, dict) else 'not_dict'}",
                output_data=ref_result,
            )
            reflection = ref_result.get("reflection", ref_result)
            decision = reflection.get("decision", "finalize")
            confidence = reflection.get("coverage_score", 0.8)

            self.session.set_decision(decision, confidence)
            self.session.add_history(
                "planner_reflection", "evaluate_roadmap",
                f"Decision: {decision} (confidence: {confidence})",
                {"reflection": reflection},
            )
            print(f"  [Planner-Reflection] Decision: {decision} (confidence: {confidence})")

            if decision == "finalize":
                print(f"\n  ✅ Roadmap finalized at {version_key}")
                self.session.finalize_roadmap(roadmap)
                break
            elif decision == "revise":
                revision_instructions = reflection.get("revision_instructions", "Sửa đổi roadmap.")
                print(f"  🔄 Revising roadmap: {revision_instructions[:80]}...")
            elif decision == "redo":
                revision_instructions = "Làm lại roadmap từ đầu. " + reflection.get("revision_instructions", "")
                print(f"  🔁 Redoing roadmap entirely")
        else:
            # Max iterations reached – finalize what we have
            print(f"\n  ⚠️ Max planning iterations reached. Finalizing current roadmap.")
            self.session.finalize_roadmap(roadmap)

        return roadmap

    # ==================================================================
    # Phase 2 – Execution Loop
    # ==================================================================

    def _run_execution_loop(
        self, base_context: Dict[str, Any], roadmap: Dict[str, Any]
    ) -> Dict[str, Any]:
        """Execute each step in the roadmap with observation/reflection."""
        debug = DebugLogger()

        tasks = self._extract_tasks(roadmap)
        tasks = self._ensure_required_steps(tasks)
        total_steps = len(tasks)
        print(f"\n  Total execution steps: {total_steps}")

        # Accumulated state across steps
        state: Dict[str, Any] = {
            "sentences": base_context["sentences"],
            "chunks": None,
            "chunk_summaries": None,
            "merged_summary": None,
            "refined_summary": None,
            "verification_report": None,
            "edited_summary": None,
            "key_points": None,
        }
        trace: List[Dict[str, Any]] = []

        # Restore state from persistence if resuming
        if self.session.data_store:
            self._update_state_from_data_store(state)
            print("  [Manager] State restored from session data store ✓")

        for step_idx, task in enumerate(tasks, start=1):
            step_id = task.get("step_id", f"step_{step_idx}")
            
            # Check if step already completed in previous runs
            if any(e["step_id"] == step_id and e["status"] == "completed" for e in self.session.execution_log):
                print(f"\n⏩ Skipping Step {step_idx}/{total_steps}: {task.get('name')} (Already completed)")
                continue

            print(f"\n--- Execution step {step_idx}/{total_steps}: {task.get('name', 'unknown')} ---")

            retries = 0
            retry_feedback = ""  # Feedback from Reflection Agent for retry attempts
            while retries <= config.MAX_EXECUTION_RETRIES:
                # Execute step
                print(f"  [Execution] Running step (attempt {retries + 1}) ...")
                exec_ctx = {
                    **base_context,
                    "current_step": task,
                    "failed_steps": self.session.get_failed_steps(),
                    "retry_feedback": retry_feedback,  # Pass reflection feedback
                    **state,
                }
                step_output = self.executor.run(exec_ctx)

                # --- Debug Log: Execution step output ---
                debug.log_step(
                    step_name=f"exec_step{step_idx}_{task.get('name', 'unknown')}",
                    agent_name="Execution Agent",
                    phase="execution",
                    input_summary=f"step_id={step_id}, attempt={retries+1}",
                    output_data=step_output,
                )

                # Update accumulated state
                self._update_state(state, step_output)

                status = step_output.get("status", "completed")
                if status == "failed":
                    self.session.log_execution_step(
                        task.get("step_id", f"step_{step_idx}"),
                        "failed",
                        step_output.get("error", "Unknown error"),
                        error=step_output.get("error"),
                    )
                    print(f"  [Execution] Step failed: {step_output.get('error')}")
                    retries += 1
                    continue

                self.session.log_execution_step(
                    task.get("step_id", f"step_{step_idx}"),
                    "completed",
                    step_output.get("action", "unknown"),
                )
                self.session.add_history(
                    "execution", step_output.get("action", "unknown"),
                    f"Step {step_idx} completed",
                )
                print(f"  [Execution] Step completed ✓")

                # Resting GPU after potentially heavy summarization before next reasoning
                self.llm.unload()

                action_name = step_output.get("action", "")
                purely_analytical_actions = ["split_sentences", "chunking", "identify_key_points", "verify"]
                
                if action_name in purely_analytical_actions:
                    print(f"  [Auto-Skip] Bỏ qua Observation & Reflection cho thao tác: {action_name}")
                    decision = "next_step"
                    reflection = {"decision": "next_step", "feedback": "", "factual_consistency": 1.0, "coverage_completeness": 1.0}
                else:
                    # Observation
                    print(f"  [Exec-Observation] Analyzing output ...")
                    self.llm.load_agent_model()
                    obs = self.exec_obs.run({
                        "step_output": step_output,
                        "input_text": base_context["input_text"],
                        "style": base_context["style"],
                    })
                    debug.log_step(
                        step_name=f"exec_step{step_idx}_observation",
                        agent_name="Execution-Observation Agent",
                        phase="execution",
                        input_summary=f"step_id={step_id}, action={step_output.get('action')}",
                        output_data=obs,
                    )
                    self.session.add_history(
                        "execution_observation", "analyze_step",
                        f"Observation for step {step_idx} complete",
                    )
                    print(f"  [Exec-Observation] Analysis complete ✓")

                    # Reflection
                    print(f"  [Exec-Reflection] Evaluating ...")
                    ref_result = self.exec_ref.run({
                        "observation": obs,
                        "current_step_idx": step_idx,
                        "total_steps": total_steps,
                    })
                    debug.log_step(
                        step_name=f"exec_step{step_idx}_reflection",
                        agent_name="Execution-Reflection Agent",
                        phase="execution",
                        input_summary=f"step_id={step_id}, step={step_idx}/{total_steps}",
                        output_data=ref_result,
                    )
                    reflection = ref_result.get("execution_reflection", ref_result)
                    decision = reflection.get("decision", "next_step")

                    self.session.add_history(
                        "execution_reflection", "evaluate_step",
                        f"Decision: {decision}",
                        {"reflection": reflection},
                    )
                    print(f"  [Exec-Reflection] Decision: {decision}")

                # Build trace entry
                trace.append({
                    "agent": "execution",
                    "action": step_output.get("action", "unknown"),
                    "step_id": task.get("step_id", f"step_{step_idx}"),
                    "evidence": f"Step {step_idx}: {task.get('name', '')}",
                    "reflection_scores": {
                        "factual_consistency": reflection.get("factual_consistency"),
                        "coverage_completeness": reflection.get("coverage_completeness"),
                    },
                })

                if decision == "retry":
                    retries += 1
                    # Capture feedback so ExecutionAgent knows what to fix
                    retry_feedback = reflection.get("feedback", "")
                    print(f"  🔄 Retrying step {step_idx} (attempt {retries + 1})")
                    if retry_feedback:
                        print(f"  📝 Feedback: {retry_feedback[:120]}")
                    continue
                elif decision == "finish":
                    print(f"\n  ✅ Execution finished (decided by Reflection)")
                    break
                else:  # next_step
                    break

        # Assemble final output
        return self._build_final_output(base_context, state, trace)

    # ==================================================================
    # Helpers
    # ==================================================================

    def _extract_tasks(self, roadmap: Dict[str, Any]) -> List[Dict[str, Any]]:
        """Extract the task list from a roadmap dict (handles varying schemas)."""
        # Try common keys where the LLM might place the task list
        if "roadmap" in roadmap:
            rm = roadmap["roadmap"]
            if isinstance(rm, dict) and "tasks" in rm:
                return rm["tasks"]
            if isinstance(rm, list):
                return rm
        if "tasks" in roadmap:
            return roadmap["tasks"]
        # Fall back: return a default task list
        return self._default_task_list()

    @staticmethod
    def _ensure_required_steps(tasks: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
        """Guarantee that verify_claim and edit_summary steps always exist.

        The Planner LLM (7B) frequently omits these critical steps.
        Instead of relying on prompt engineering alone, we hard-check
        and append them if missing.  This is the Manager's responsibility.
        """
        # Collect all tool names already present (normalised)
        existing_tools = set()
        for t in tasks:
            raw_tool = t.get("tool", "")
            if isinstance(raw_tool, str):
                existing_tools.add(raw_tool.lower())

        # Determine the next step_id number
        max_step_num = 0
        for t in tasks:
            sid = t.get("step_id", "")
            if sid.startswith("step_"):
                try:
                    max_step_num = max(max_step_num, int(sid.split("_")[1]))
                except (ValueError, IndexError):
                    pass

        added = []

        # --- verify_claim ---
        if not any("verify_claim" in tool for tool in existing_tools):
            max_step_num += 1
            tasks.append({
                "step_id": f"step_{max_step_num}",
                "name": "Kiểm chứng (verification)",
                "description": "Đối chiếu các claims trong bản tóm tắt với văn bản gốc",
                "tool": "verify_claim",
                "expected_output": "Báo cáo kiểm chứng",
            })
            added.append("verify_claim")

        # --- edit_summary ---
        if not any("edit" in tool for tool in existing_tools):
            max_step_num += 1
            tasks.append({
                "step_id": f"step_{max_step_num}",
                "name": "Hiệu chỉnh phong cách (editing)",
                "description": "Chỉnh sửa phong cách cuối cùng theo yêu cầu",
                "tool": "edit_summary",
                "expected_output": "Bản tóm tắt hoàn chỉnh",
            })
            added.append("edit_summary")

        if added:
            print(f"  [Manager] ⚠️ Planner thiếu bước quan trọng → Đã tự động thêm: {added}")

        return tasks

    @staticmethod
    def _default_task_list() -> List[Dict[str, Any]]:
        """Fallback roadmap if LLM output couldn't be parsed properly."""
        return [
            {"step_id": "step_1", "name": "Tách câu (sentence splitting)", "description": "Tách văn bản thành các câu riêng biệt", "tool": "sent_tokenize", "expected_output": "Danh sách câu với ID"},
            {"step_id": "step_2", "name": "Xác định ý chính", "description": "Phân tích và xác định các ý chính, entity quan trọng", "tool": "LLM", "expected_output": "Danh sách ý chính"},
            {"step_id": "step_3", "name": "Chia đoạn (chunking)", "description": "Nhóm các câu thành chunks", "tool": "chunk_text", "expected_output": "Danh sách chunks"},
            {"step_id": "step_4", "name": "Tóm tắt từng chunk", "description": "Tóm tắt abstractive cho mỗi chunk", "tool": "summarize_chunk", "expected_output": "Danh sách chunk summaries"},
            {"step_id": "step_5", "name": "Gộp tóm tắt (merge)", "description": "Gộp các chunk summaries thành một bản nháp", "tool": "LLM", "expected_output": "Bản nháp tóm tắt"},
            {"step_id": "step_6", "name": "Tinh chỉnh toàn cục (global refinement)", "description": "Tinh chỉnh bản nháp để mạch lạc", "tool": "LLM", "expected_output": "Bản tóm tắt tinh chỉnh"},
            {"step_id": "step_7", "name": "Kiểm chứng (verification)", "description": "Đối chiếu claims với văn bản gốc", "tool": "verify_claim", "expected_output": "Báo cáo kiểm chứng"},
            {"step_id": "step_8", "name": "Hiệu chỉnh phong cách (editing)", "description": "Chỉnh sửa phong cách cuối cùng", "tool": "edit_summary", "expected_output": "Bản tóm tắt hoàn chỉnh"},
        ]

    def _update_state(self, state: Dict[str, Any], output: Dict[str, Any]) -> None:
        """Merge step output into the accumulated state and persist to sessions.json."""
        mappings = {
            "sentences": "sentences",
            "chunks": "chunks",
            "chunk_summaries": "chunk_summaries",
            "merged_summary": "merged_summary",
            "refined_summary": "refined_summary",
            "verification_report": "verification_report",
            "edited_summary": "edited_summary",
            "key_points": "key_points",
        }
        for key, state_key in mappings.items():
            if key in output and output[key] is not None:
                new_val = output[key]
                state[state_key] = new_val
                # Persist immediately to sessions.json (Source of Truth)
                self.session.update_data_store(state_key, new_val)

    def _update_state_from_data_store(self, state: Dict[str, Any]) -> None:
        """Restore state from session.json data store."""
        mappings = [
            "sentences", "chunks", "chunk_summaries", "merged_summary", 
            "refined_summary", "verification_report", "edited_summary", "key_points"
        ]
        for key in mappings:
            val = self.session.get_data(key)
            if val is not None:
                state[key] = val

    def _build_final_output(
        self,
        base_context: Dict[str, Any],
        state: Dict[str, Any],
        trace: List[Dict[str, Any]],
    ) -> Dict[str, Any]:
        """Assemble the final JSON output."""
        final_summary = (
            state.get("edited_summary")
            or state.get("refined_summary")
            or state.get("merged_summary")
            or ""
        )

        # Build verification_report in the required schema
        verification = state.get("verification_report", [])
        if isinstance(verification, dict):
            verification = verification.get("verification_report", [])

        output = {
            "summary": final_summary,
            "style": base_context["style"],
            "word_count": vn_tools.count_words(final_summary),
            "trace": trace,
            "verification_report": verification,
            "intermediate_outputs": {
                "outline": state.get("key_points"),
                "draft_summary": state.get("merged_summary"),
                "verification": verification,
                "edited_summary": state.get("edited_summary"),
            },
        }
        return output

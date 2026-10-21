"""Oracle v2 safeguards: synthetic evidence only, no models/servers/database."""
import copy
import json
from pathlib import Path
import tempfile
import time
import unittest
from unittest.mock import patch
from urllib.parse import unquote

import admin_feedback_gate as gate
import admin_feedback_queue as workflow
from task_queue import Job


def evidence():
    cases=copy.deepcopy(json.loads(gate.CASES.read_text()))+gate.oracle_requests()
    for case in cases:
        case.setdefault("status",400)
        case.setdefault("body",{"fixture":"observed original response"})
        if case["name"]==gate.KNOWN_ORIGINAL_500["name"]:
            case.update(status=500,body=copy.deepcopy(gate.KNOWN_ORIGINAL_500["body"]))
        case["input_rows"]=[]
    return dict(status="passed",oracle_version=gate.ORACLE_VERSION,case_sha256=gate.digest(gate.CASES),
                spring_jar_sha256="a"*64,original_snapshot_sha256="b"*64,oracle_cases=cases,
                results=[{"case":case["name"],"passed":True} for case in cases])


class OracleTests(unittest.TestCase):
    def test_expansion_preserves_18_cases_and_has_no_guessed_expectations(self):
        baseline=gate.digest(gate.CASES)
        probes=gate.oracle_requests()
        self.assertEqual(len(json.loads(gate.CASES.read_text())),18)
        self.assertEqual(len(probes),88)
        self.assertEqual(len({p["name"] for p in probes}),88)
        self.assertTrue(all("status" not in p and "body" not in p for p in probes))
        paths=[unquote(p["path"]) for p in probes]
        for token in ("+0x1","+#1","-0x1","-#1","１","١","\u2003","\u00a0","2147483648","9223372036854775808","page=0&size=abc"):
            self.assertTrue(any(token in path for path in paths),token)
        self.assertEqual(gate.digest(gate.CASES),baseline)

    def test_evidence_requires_complete_ordered_original_bound_results(self):
        source=evidence()
        self.assertEqual(len(gate.validate_oracle(source)),106)
        variants=[]
        for key in ("spring_jar_sha256","original_snapshot_sha256","case_sha256","oracle_version","status"):
            variant=copy.deepcopy(source);variant[key]="invalid";variants.append(variant)
        variant=copy.deepcopy(source);variant["oracle_cases"].pop();variants.append(variant)
        variant=copy.deepcopy(source);variant["oracle_cases"][0]["body"]={};variants.append(variant)
        variant=copy.deepcopy(source);variant["oracle_cases"][20]["path"]+="x";variants.append(variant)
        variant=copy.deepcopy(source);variant["results"].reverse();variants.append(variant)
        variant=copy.deepcopy(source);variant["oracle_cases"][20]["status"]=500;variants.append(variant)
        for variant in variants:
            with self.subTest(),self.assertRaises(ValueError):gate.validate_oracle(variant)

    def test_only_observed_original_overflow_allows_exact_sanitized_500(self):
        probe=next(p for p in gate.oracle_requests() if p["name"]=="v2-page-17")
        body=gate.KNOWN_ORIGINAL_500["body"]
        self.assertTrue(gate.original_contract(probe,500,body))
        self.assertFalse(gate.original_contract(probe,503,body))
        self.assertFalse(gate.original_contract(probe,500,{**body,"detail":"unexpected"}))
        self.assertFalse(gate.original_contract({**probe,"path":"/unexpected"},500,body))
        self.assertFalse(gate.original_contract({**probe,"name":"other"},500,body))
        source=evidence();case=next(c for c in source["oracle_cases"] if c["name"]=="v2-page-17")
        case["body"]={}
        with self.assertRaises(ValueError):gate.validate_oracle(source)

    def test_oracle_waits_shared_db_lock_before_any_runtime_work(self):
        with tempfile.TemporaryDirectory() as directory:
            root=Path(directory)
            self.assertTrue(gate.sample_gate._GATE_LOCK.acquire(timeout=1))
            try:
                with patch.object(gate.sample_gate,"ROOT",root),patch.object(gate,"_run") as runtime:
                    result=gate.run_oracle(root/"oracle",timeout_seconds=.04)
                self.assertEqual(result["status"],"blocked")
                self.assertEqual(result["reason"],"lock-timeout")
                runtime.assert_not_called()
            finally:gate.sample_gate._GATE_LOCK.release()

    def make_experiment(self,root,version="v2"):
        return workflow.Experiment(root/"experiment",3,10,contract_version=version)

    def test_v2_blocks_model_dispatch_until_original_evidence_exists(self):
        with tempfile.TemporaryDirectory() as directory:
            experiment=self.make_experiment(Path(directory))
            with patch.object(workflow,"CliAgent") as model,self.assertRaisesRegex(ValueError,"evidence required"):
                experiment.agent(Job("test-list","agent"),time.monotonic()+5)
            model.assert_not_called()

    def test_author_receives_immutable_observed_evidence_before_writing(self):
        with tempfile.TemporaryDirectory() as directory:
            root=Path(directory);experiment=self.make_experiment(root)
            artifact=root/"oracle.json";artifact.write_text(json.dumps(evidence()))
            experiment.bind_oracle(artifact)
            captured={}
            def model(*args,**kwargs):
                def invoke(role,worker,prompt,output):
                    captured.update(prompt=prompt,evidence=(worker/"original-http-evidence.json").read_bytes())
                    return {"status":"revise"},{}
                return invoke
            with patch.object(workflow,"CliAgent",side_effect=model):
                experiment.agent(Job("test-list","agent"),time.monotonic()+5)
            self.assertEqual(captured["evidence"],artifact.read_bytes())
            self.assertIn("BEFORE writing",captured["prompt"])
            self.assertIn("+0x1",captured["prompt"])
            experiment.oracle_path.write_text("{}")
            with self.assertRaisesRegex(ValueError,"baseline changed"):experiment.integrity()

    def test_failed_oracle_starts_no_queue_and_deducts_time(self):
        with tempfile.TemporaryDirectory() as directory:
            experiment=self.make_experiment(Path(directory))
            with patch.object(gate,"run_oracle",return_value={"status":"blocked"}),patch.object(workflow,"TaskQueue") as queue:
                result=experiment.run()
                self.assertEqual(result["status"],"blocked")
                self.assertEqual(result["tasks"],{})
                self.assertEqual(json.loads((experiment.directory/"preflight-result.json").read_text()),result)
            queue.assert_not_called()
            self.assertLess(experiment.timeout,10)

    def test_compact_projection_reconstructs_every_canonical_case_exactly(self):
        source=evidence()
        for index,case in enumerate(source["oracle_cases"]):
            case["input_rows"]=[{"id":1,"content":"synthetic "+case.get("fixture","baseline")}]
        covered=[]
        for feature in ("list","detail"):
            summary=workflow.compact_oracle(source,feature,"a"*64)
            self.assertEqual(summary["canonical_sha256"],"a"*64)
            self.assertLessEqual(len(summary["fixtures"]),2)
            for case in summary["cases"]:
                original=source["oracle_cases"][case["canonical_index"]]
                for key in ("name","path","principal","status"):
                    self.assertEqual(case[key],original[key])
                self.assertEqual(summary["responses"][case["response_ref"]],original["body"])
                self.assertEqual(summary["fixtures"][case["fixture"]]["input_rows"],original["input_rows"])
                covered.append(case["canonical_index"])
        self.assertEqual(sorted(covered),list(range(106)))
        source["oracle_cases"][1]["input_rows"]=[{"id":999}]
        with self.assertRaisesRegex(ValueError,"inconsistent"):
            workflow.compact_oracle(source,"list","a"*64)

    def test_timeout_is_observable_and_never_imports_untrusted_partial_source(self):
        with tempfile.TemporaryDirectory() as directory:
            experiment=self.make_experiment(Path(directory),version="v1")
            def invoke(role,worker,prompt,output):
                output.mkdir()
                (output/"events.jsonl").write_text(json.dumps({"type":"thread.started","thread_id":"synthetic-session"})+"\n")
                (worker/"feedback_list.rs").write_text("partial untrusted implementation")
                raise RuntimeError("Agent time limit exceeded")
            with patch.object(workflow,"CliAgent",return_value=invoke) as transport:
                result=experiment.agent(Job("implement-list","agent"),time.monotonic()+1000)
                second=experiment.agent(Job("test-list","agent"),time.monotonic()+1000)
            self.assertEqual(transport.call_count,1)
            self.assertEqual(transport.call_args.kwargs["timeout"],240)
            self.assertEqual(result["reason"],"model_timeout")
            metadata=result["identity"]
            self.assertEqual(metadata["status"],"timeout")
            self.assertEqual(metadata["session_id"],"synthetic-session")
            self.assertEqual(metadata["budget_seconds"],240)
            self.assertEqual(metadata["max_attempts"],1)
            self.assertIn("requested_model",metadata)
            self.assertIn("executable",metadata)
            self.assertFalse(metadata["artifact_imported"])
            self.assertEqual(json.loads((Path(result["evidence"])/"execution-result.json").read_text()),metadata)
            self.assertEqual((experiment.candidate/"src/feedback_list.rs").read_text(),workflow.STUBS["list"])
            self.assertEqual(second["reason"],"model_backend_unavailable")

    def test_configured_call_timeout_is_capped_by_whole_deadline(self):
        with tempfile.TemporaryDirectory() as directory:
            experiment=workflow.Experiment(Path(directory)/"run",1,900,agent_timeout=300)
            with patch.object(workflow,"CliAgent",side_effect=RuntimeError("failure")) as transport:
                experiment.agent(Job("test-list","agent"),time.monotonic()+.5)
            self.assertGreater(transport.call_args.kwargs["timeout"],0)
            self.assertLessEqual(transport.call_args.kwargs["timeout"],.5)
        for invalid in (0,-1,301,float("nan")):
            with self.assertRaises(ValueError):
                workflow.Experiment(Path("unused-no-write"),1,900,agent_timeout=invalid)

    def test_response_transport_strict_schema_and_readonly_permission(self):
        with tempfile.TemporaryDirectory() as directory:
            root=Path(directory);worker=root/"worker";worker.mkdir()
            source='#![forbid(unsafe_code)]\npub fn example() {}\n'
            def capture(command,prompt,events,timeout,env):
                schema=json.loads((root/"output/schema.json").read_text())
                self.assertFalse(schema["additionalProperties"])
                self.assertIn("rust_source",schema["required"])
                permission=next(item for item in command if item.startswith("permissions.daynomy_role="))
                self.assertNotIn('"write"',permission)
                self.assertIn("inline input",prompt)
                Path(events).write_text(json.dumps({"type":"thread.started","thread_id":"fixture-session"})+"\n")
                (root/"output/result.json").write_text(json.dumps(dict(status="implemented",summary="complete",findings=[],questions=[],rust_source=source)))
                return 0
            with patch.object(workflow,"capture",side_effect=capture):
                result,identity=workflow.ResponseArtifactAgent(timeout=10,max_attempts=1)("implementer",worker,"inline input",root/"output")
            self.assertEqual(result["rust_source"],source)
            self.assertEqual(identity["artifact_mode"],"response")
            self.assertEqual(list(worker.iterdir()),[])

    def test_response_mode_validates_and_installs_only_expected_owned_source(self):
        with tempfile.TemporaryDirectory() as directory:
            experiment=workflow.Experiment(Path(directory)/"run",1,900,artifact_mode="response")
            source='#![forbid(unsafe_code)]\npub fn list(_: &str, _: &serde_json::Value) -> (u16, serde_json::Value) { (400, serde_json::json!({})) }\n'
            def invoke(role,worker,prompt,output):
                self.assertIn("INLINE INPUT reference.txt",prompt)
                self.assertIn("do not edit files",prompt)
                self.assertEqual((worker/"feedback_list.rs").read_text(),workflow.STUBS["list"])
                return dict(status="implemented",summary="complete",findings=[],questions=[],rust_source=source),{}
            original_detail=(experiment.candidate/"src/feedback_detail.rs").read_text()
            criteria=(experiment.directory/"criteria.json").read_bytes()
            with patch.object(workflow,"ResponseArtifactAgent",return_value=invoke) as response,patch.object(workflow,"CliAgent") as files:
                result=experiment.agent(Job("implement-list","agent"),time.monotonic()+20)
            self.assertEqual(result["status"],"completed")
            files.assert_not_called();self.assertEqual(response.call_count,1)
            self.assertEqual((experiment.candidate/"src/feedback_list.rs").read_text(),source)
            self.assertEqual((experiment.candidate/"src/feedback_detail.rs").read_text(),original_detail)
            self.assertEqual((experiment.directory/"criteria.json").read_bytes(),criteria)

    def test_response_rejects_worker_mutation_or_invalid_source_before_import(self):
        for mutation in (False,True):
            with self.subTest(mutation=mutation),tempfile.TemporaryDirectory() as directory:
                experiment=workflow.Experiment(Path(directory)/"run",1,900,artifact_mode="response")
                def invoke(role,worker,prompt,output):
                    if mutation:(worker/"feedback_list.rs").write_text("unexpected model write")
                    return dict(status="implemented",summary="bad",findings=[],questions=[],rust_source="incomplete"),{}
                with patch.object(workflow,"ResponseArtifactAgent",return_value=invoke),self.assertRaises(ValueError):
                    experiment.agent(Job("implement-list","agent"),time.monotonic()+20)
                self.assertEqual((experiment.candidate/"src/feedback_list.rs").read_text(),workflow.STUBS["list"])
                self.assertEqual(experiment.generated,{})

    def test_response_test_author_freezes_validated_assertion_module(self):
        with tempfile.TemporaryDirectory() as directory:
            experiment=workflow.Experiment(Path(directory)/"run",1,900,artifact_mode="response")
            source='#![forbid(unsafe_code)]\n#[path="../src/feedback_list.rs"] mod subject;\n'+''.join(f'#[test] fn case_{i}() {{ assert_eq!(1,1); }}\n' for i in range(3))
            invoke=lambda *args: (dict(status="tests_written",summary="complete",findings=[],questions=[],rust_source=source),{})
            with patch.object(workflow,"ResponseArtifactAgent",return_value=invoke):
                result=experiment.agent(Job("test-list","agent"),time.monotonic()+20)
            self.assertEqual(result["status"],"completed")
            self.assertEqual(experiment.frozen_tests["tests/feedback_list_contract.rs"],workflow.digest(experiment.candidate/"tests/feedback_list_contract.rs"))

    def test_response_transport_rejects_extra_fields_and_malformed_json(self):
        for payload in ('not json',json.dumps(dict(status="implemented",summary="x",findings=[],questions=[],rust_source="x",path="outside.rs"))):
            with self.subTest(payload=payload),tempfile.TemporaryDirectory() as directory:
                root=Path(directory)
                def capture(command,prompt,events,timeout,env):
                    (root/"output/result.json").write_text(payload)
                    return 0
                with patch.object(workflow,"capture",side_effect=capture),self.assertRaises(RuntimeError):
                    workflow.ResponseArtifactAgent(max_attempts=1)("implementer",root,"inline",root/"output")

    def test_response_option_keeps_reviewer_on_existing_readonly_transport(self):
        with tempfile.TemporaryDirectory() as directory:
            experiment=workflow.Experiment(Path(directory)/"run",1,900,artifact_mode="response")
            (experiment.directory/"verification.json").write_text("{}")
            result=dict(status="revise",summary="need evidence",findings=["TEST_REVISION missing coverage"],questions=[])
            with patch.object(workflow,"CliAgent",return_value=lambda *args:(result,{})) as files,patch.object(workflow,"ResponseArtifactAgent") as response:
                experiment.agent(Job("review-list","agent"),time.monotonic()+20)
            response.assert_not_called();self.assertEqual(files.call_count,1)

    def test_direct_response_timeout_always_records_observable_metadata(self):
        with tempfile.TemporaryDirectory() as directory:
            root=Path(directory);output=root/"output"
            def capture(command,prompt,events,timeout,env):
                Path(events).write_text('not-json\n'+json.dumps({"type":"thread.started","thread_id":"synthetic-session"})+'\n')
                raise RuntimeError("Agent time limit exceeded")
            with patch.object(workflow,"capture",side_effect=capture),self.assertRaises(RuntimeError):
                workflow.ResponseArtifactAgent(timeout=23,model="fixture-model",reasoning_effort="high",executable="fixture-codex")("implementer",root,"private source",output)
            metadata=json.loads((output/"execution-result.json").read_text())
            self.assertEqual(metadata,json.loads((output/"identity.json").read_text()))
            self.assertEqual(metadata["status"],"timeout")
            self.assertEqual(metadata["session_id"],"synthetic-session")
            self.assertEqual(metadata["requested_model"],"fixture-model")
            self.assertEqual(metadata["requested_reasoning_effort"],"high")
            self.assertEqual(metadata["executable"],"fixture-codex")
            self.assertEqual(metadata["budget_seconds"],23)
            self.assertGreaterEqual(metadata["elapsed_seconds"],0)
            self.assertIsNone(metadata["usage"])
            self.assertFalse(metadata["artifact_imported"])
            self.assertNotIn("private source",json.dumps(metadata))

    def test_direct_response_every_transport_failure_records_metadata_without_source(self):
        for failure in ("missing","malformed","invalid-verdict","bad-session","exit-code","spawn-error"):
            with self.subTest(failure=failure),tempfile.TemporaryDirectory() as directory:
                root=Path(directory);output=root/"output"
                def capture(command,prompt,events,timeout,env):
                    if failure=="spawn-error":raise OSError("private source must not leak")
                    Path(events).write_text(json.dumps({"type":"turn.completed","usage":{"input_tokens":7,"output_tokens":2,"private":"private source"}})+'\n')
                    if failure!="missing":
                        result=dict(status="implemented",summary="ok",findings=[],questions=[],rust_source="private source")
                        if failure=="invalid-verdict":result["status"]="approve"
                        (output/"result.json").write_text("private source" if failure=="malformed" else json.dumps(result))
                    return 1 if failure=="exit-code" else 0
                with patch.object(workflow,"capture",side_effect=capture),self.assertRaises(RuntimeError):
                    workflow.ResponseArtifactAgent(timeout=11)("implementer",root,"private source",output)
                metadata=json.loads((output/"execution-result.json").read_text())
                self.assertEqual(metadata["status"],"transport_failed")
                self.assertFalse(metadata["artifact_imported"])
                self.assertNotIn("private source",json.dumps(metadata))
                self.assertIn("requested_model",metadata)
                self.assertIn("requested_reasoning_effort",metadata)
                if failure!="spawn-error":self.assertEqual(metadata["usage"],{"input_tokens":7,"output_tokens":2})

    def test_parent_callback_preserves_direct_response_failure_usage(self):
        with tempfile.TemporaryDirectory() as directory:
            experiment=workflow.Experiment(Path(directory)/"run",1,900,artifact_mode="response")
            def capture(command,prompt,events,timeout,env):
                Path(events).write_text(json.dumps({"type":"turn.completed","usage":{"input_tokens":9}})+'\n')
                return 1
            with patch.object(workflow,"capture",side_effect=capture):
                result=experiment.agent(Job("implement-list","agent"),time.monotonic()+20)
            self.assertEqual(result["identity"]["usage"],{"input_tokens":9})
            self.assertEqual(result["identity"]["failure_type"],"RuntimeError")
            self.assertEqual(result["reason"],"model_transport_failed")

    def test_response_mode_timeout_keeps_existing_failure_metadata_and_latch(self):
        with tempfile.TemporaryDirectory() as directory:
            experiment=workflow.Experiment(Path(directory)/"run",1,900,artifact_mode="response")
            with patch.object(workflow,"ResponseArtifactAgent",side_effect=RuntimeError("Agent time limit exceeded")) as transport:
                result=experiment.agent(Job("implement-list","agent"),time.monotonic()+20)
            self.assertEqual(result["reason"],"model_timeout")
            self.assertEqual(result["identity"]["artifact_mode"],"response")
            self.assertFalse(result["identity"]["artifact_imported"])
            self.assertTrue(experiment.backend_failed.is_set())
            self.assertEqual(transport.call_count,1)

    def test_recovery_binding_retains_parent_evidence_hash(self):
        with tempfile.TemporaryDirectory() as directory:
            root=Path(directory);source=root/"parent-evidence.json";source.write_text(json.dumps(evidence()))
            experiment=self.make_experiment(root)
            expected=gate.digest(source)
            experiment.bind_oracle(source,expected)
            criteria=json.loads((experiment.directory/"criteria.json").read_text())
            self.assertEqual(criteria["oracle_sha256"],expected)
            self.assertEqual(criteria["case_sha256"],gate.digest(gate.CASES))
            source.write_text("{}")
            with self.assertRaisesRegex(ValueError,"evidence changed"):experiment.bind_oracle(source,expected)

if __name__=="__main__":unittest.main()

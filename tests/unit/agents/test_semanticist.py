"""Tests for Semanticist: ContextWindowBudget, generate_purpose_statement, cluster_into_domains, answer_day_one_questions, run_semanticist."""

from src.agents.semanticist import (
    DAY_ONE_QUESTIONS,
    ContextWindowBudget,
    answer_day_one_questions,
    cluster_into_domains,
    generate_purpose_statement,
    run_semanticist,
)


class TestContextWindowBudget:
    def test_estimate_tokens(self):
        budget = ContextWindowBudget(limit=1000)
        assert budget.estimate_tokens("hello") >= 1
        assert budget.estimate_tokens("x" * 400) == 100

    def test_would_exceed_and_remaining(self):
        budget = ContextWindowBudget(limit=100)
        assert budget.remaining() == 100
        assert not budget.would_exceed(50)
        budget.add_usage(60)
        assert budget.remaining() == 40
        assert budget.would_exceed(50)

    def test_add_usage(self):
        budget = ContextWindowBudget(limit=1000)
        budget.add_usage(100)
        assert budget.remaining() == 900


class TestGeneratePurposeStatement:
    def test_returns_placeholder_when_no_code(self):
        def noop_llm(prompt: str, model: str, max_tokens: int) -> str:
            return "Some purpose."
        budget = ContextWindowBudget(limit=10_000)
        purpose, drift = generate_purpose_statement(
            __file__, "fake/path.py", "", "python", noop_llm, budget
        )
        assert purpose == "No content."
        assert drift is False

    def test_uses_llm_response_and_updates_budget(self):
        def fixed_llm(prompt: str, model: str, max_tokens: int) -> str:
            return "This module handles authentication."
        budget = ContextWindowBudget(limit=10_000)
        code = "def login(): pass"
        purpose, drift = generate_purpose_statement(
            __file__, "auth.py", code, "python", fixed_llm, budget
        )
        assert "authentication" in purpose
        assert drift is False
        assert budget.remaining() < 10_000

    def test_no_drift_without_docstring(self):
        def fixed_llm(prompt: str, model: str, max_tokens: int) -> str:
            return "Data loader."
        budget = ContextWindowBudget(limit=10_000)
        code = "x = 1  # no docstring"
        purpose, drift = generate_purpose_statement(
            __file__, "mod.py", code, "python", fixed_llm, budget
        )
        assert drift is False


class TestClusterIntoDomains:
    def test_assigns_domain_cluster_to_nodes_with_purpose(self):
        from src.graph.knowledge_graph import KnowledgeGraph

        kg = KnowledgeGraph()
        for path in ["a.py", "b.py", "c.py"]:
            kg.add_module_node({"path": path, "language": "python", "purpose_statement": f"Purpose for {path}."})
        # Deterministic embedding: same text -> same vector would break k-means; use different dims
        def embed(texts):
            import hashlib
            out = []
            for t in texts:
                h = hashlib.sha256(t.encode()).digest()
                out.append([(int(h[i % len(h)]) - 128) / 128.0 for i in range(32)])
            return out
        labels = cluster_into_domains(kg, embed, k=2)
        assert len(labels) >= 1
        # All three modules should have domain_cluster set
        for path in ["a.py", "b.py", "c.py"]:
            assert kg.module_graph.has_node(path)
            assert kg.module_graph.nodes[path].get("domain_cluster") is not None

    def test_skips_nodes_without_purpose(self):
        from src.graph.knowledge_graph import KnowledgeGraph

        kg = KnowledgeGraph()
        kg.add_module_node({"path": "empty.py", "language": "python"})  # no purpose_statement
        def embed(texts):
            return [[0.1] * 32 for _ in texts]
        cluster_into_domains(kg, embed, k=1)
        assert kg.module_graph.nodes["empty.py"].get("domain_cluster") is None


class TestAnswerDayOneQuestions:
    def test_returns_five_entries(self):
        from src.graph.knowledge_graph import KnowledgeGraph

        kg = KnowledgeGraph()
        budget = ContextWindowBudget(limit=100_000)
        def stub_llm(prompt: str, model: str, max_tokens: int) -> str:
            return "1.\nANSWER: Ingestion path is X.\nCITATIONS: src/ingest.py:10\n2.\nANSWER: Outputs are A, B.\nCITATIONS: out.csv"
        results = answer_day_one_questions(kg, stub_llm, budget)
        assert len(results) == 5
        assert all("question" in r and "answer" in r and "citations" in r for r in results)
        assert results[0]["question"] == DAY_ONE_QUESTIONS[0]

    def test_parses_answer_and_citations(self):
        from src.graph.knowledge_graph import KnowledgeGraph

        kg = KnowledgeGraph()
        budget = ContextWindowBudget(limit=100_000)
        def fixed_llm(prompt: str, model: str, max_tokens: int) -> str:
            return """1.
ANSWER: Primary ingestion is via Kafka in src/ingest/kafka_consumer.py.
CITATIONS: src/ingest/kafka_consumer.py:42
2.
ANSWER: Critical outputs: warehouse table, API.
CITATIONS: lib/api.py:1
"""
        results = answer_day_one_questions(kg, fixed_llm, budget)
        assert "Kafka" in results[0]["answer"] or "ingestion" in results[0]["answer"].lower()
        assert any("kafka_consumer" in c or "src/" in c for c in results[0]["citations"])

    def test_budget_exceeded_returns_skipped(self):
        from src.graph.knowledge_graph import KnowledgeGraph

        kg = KnowledgeGraph()
        budget = ContextWindowBudget(limit=10)  # tiny
        def noop(prompt: str, model: str, max_tokens: int) -> str:
            return "x"
        results = answer_day_one_questions(kg, noop, budget)
        assert all(r["answer"] == "Skipped (budget)." for r in results)


class TestRunSemanticist:
    def test_skip_flags_return_placeholders(self, tmp_path):
        from src.graph.knowledge_graph import KnowledgeGraph

        kg = KnowledgeGraph()
        kg.add_module_node({"path": "src/foo.py", "language": "python"})
        day_one, drift = run_semanticist(
            tmp_path, kg,
            skip_purpose=True, skip_cluster=True, skip_day_one=True,
        )
        assert len(day_one) == 5
        assert all(r["answer"] == "(skipped)" for r in day_one)
        assert drift == []

    def test_purpose_and_drift_with_mock_llm(self, tmp_path):
        from src.graph.knowledge_graph import KnowledgeGraph

        (tmp_path / "src").mkdir()
        (tmp_path / "src" / "bar.py").write_text('"""Old doc."""\ndef do(): pass')
        kg = KnowledgeGraph()
        kg.add_module_node({"path": "src/bar.py", "language": "python"})
        def mock_llm(prompt: str, model: str, max_tokens: int) -> str:
            return "This module does something different from the docstring."
        day_one, drift = run_semanticist(
            tmp_path, kg,
            llm_completion=mock_llm,
            skip_cluster=True,
            skip_day_one=True,
        )
        assert kg.module_graph.nodes["src/bar.py"].get("purpose_statement") is not None
        # Docstring says "Old doc", purpose says "different" -> may or may not be flagged drift by _contradicts
        assert len(day_one) == 5

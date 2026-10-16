"""Isolated, incremental, local-only development evaluation. Never touches the live library."""

import argparse
import json
import platform
import tempfile
from datetime import UTC, datetime
from pathlib import Path
from statistics import mean

from knowledgebridge.answer_generator import OllamaGenerator
from knowledgebridge.answering import ask
from knowledgebridge.config import load_settings
from knowledgebridge.embedding_adapter import OllamaEmbedder
from knowledgebridge.evaluation import (
    EvaluationDataset,
    answer_metrics,
    citation_score,
    digest,
    relevant_passages,
    retrieval_score,
)
from knowledgebridge.index_repository import IndexRepository
from knowledgebridge.ingestion import ingest
from knowledgebridge.library import LibraryManager
from knowledgebridge.models import KnowledgeCollection
from knowledgebridge.offline import OfflineGuard
from knowledgebridge.retriever import retrieve

ROOT = Path(__file__).resolve().parents[1]


def evaluate(args: argparse.Namespace, data_dir: Path) -> None:
    settings = load_settings(ROOT / "config/knowledgebridge.yaml")
    if args.timeout is not None:
        settings.generation.timeout_seconds = args.timeout
    guard = OfflineGuard(settings.retrieval.port)
    guard.install()
    dataset = EvaluationDataset.model_validate_json(args.dataset.read_text())
    collection = KnowledgeCollection(title="FleetOps Demo — isolated Milestone 5 evaluation")
    manifest = json.loads((ROOT / "samples/fleetops_demo/manifest.json").read_text())
    imports = []
    source_hashes = {}
    for source in manifest["documents"]:
        path = ROOT / "samples/fleetops_demo" / source["filename"]
        data = path.read_bytes()
        source_hashes[source["filename"]] = __import__("hashlib").sha256(data).hexdigest()
        collection, result = ingest(
            collection, data, source["filename"], settings, version=source["version"]
        )
        imports.append({"filename": source["filename"], "accepted": result.accepted})
    if not all(row["accepted"] for row in imports):
        raise RuntimeError("Sample processing failed; evaluation cannot proceed")
    dataset.checked(collection)
    cases = dataset.questions
    if args.case_ids:
        ids = set(args.case_ids.split(","))
        if ids - {case.id for case in cases}:
            raise ValueError("Unknown requested evaluation IDs")
        cases = [case for case in cases if case.id in ids]
    repository = IndexRepository(data_dir)
    embedder = OllamaEmbedder(settings.retrieval)
    index = repository.build(collection, embedder, settings.retrieval)
    manager = LibraryManager(repository)
    result = {
        "schema_version": "m5-evaluation-1",
        "started_at": datetime.now(UTC).isoformat(),
        "complete": False,
        "provenance": dataset.provenance,
        "human_authored": dataset.human_authored,
        "dataset_digest": digest(dataset.model_dump(mode="json")),
        "source_sha256": source_hashes,
        "settings": settings.model_dump(mode="json"),
        "platform": platform.platform(),
        "python": platform.python_version(),
        "embedding_identity": index.identity.model_dump(mode="json"),
        "generation_identity": None,
        "collection_id": collection.collection_id,
        "generation": index.generation,
        "passages": index.passage_count,
        "processing": {
            "accepted": sum(row["accepted"] for row in imports),
            "attempted": len(imports),
            "success_rate": sum(row["accepted"] for row in imports) / len(imports),
        },
        "planned_cases": [case.id for case in cases],
        "retrieval": [],
        "answers": [],
    }

    def save() -> None:
        result["offline_verification"] = {
            "scope": "Python socket audit events in this evaluator; not an OS air-gap or separate Ollama process",
            "allowed_loopback_connections": guard.allowed_connections,
            "blocked_external_events": guard.blocked_events,
        }
        temporary = args.output.with_suffix(args.output.suffix + ".tmp")
        temporary.write_text(json.dumps(result, indent=2) + "\n")
        temporary.replace(args.output)

    save()
    for case in cases:
        modes = {}
        relevant = relevant_passages(collection, case)
        for mode in ("keyword", "semantic", "hybrid"):
            report = retrieve(
                repository,
                collection.collection_id,
                case.question,
                mode,
                settings.retrieval,
                embedder if mode != "keyword" else None,
            )
            modes[mode] = retrieval_score(report, relevant, settings.retrieval.top_k)
        result["retrieval"].append({"id": case.id, "category": case.category, "modes": modes})
        save()
        print(f"{case.id}: retrieval completed", flush=True)
    result["retrieval_metrics"] = {}
    for mode in ("keyword", "semantic", "hybrid"):
        scores = [
            row["modes"][mode]
            for row in result["retrieval"]
            if row["modes"][mode]["recall_at_k"] is not None
        ]
        result["retrieval_metrics"][mode] = {
            "k": settings.retrieval.top_k,
            "targeted_cases": len(scores),
            "macro_recall_at_k": mean(row["recall_at_k"] for row in scores) if scores else None,
            "target_hit_rate_at_k": mean(row["hit_at_k"] for row in scores) if scores else None,
        }
    if args.answers:
        generator = OllamaGenerator(settings.retrieval, settings.generation)
        result["generation_identity"] = generator.identity().model_dump(mode="json")
        for case in cases:
            answer = ask(
                repository, collection.collection_id, case.question, settings, embedder, generator
            )
            result["answers"].append(
                {
                    "id": case.id,
                    "category": case.category,
                    "question": case.question,
                    "expected_status": case.expected_status,
                    "status": answer.status,
                    "status_matches": answer.status == case.expected_status,
                    "answer_digest": digest(answer.model_dump(mode="json")),
                    **citation_score(manager, collection.collection_id, answer),
                    "answer": answer.model_dump(mode="json"),
                }
            )
            result["answer_metrics"] = answer_metrics(result["answers"])
            save()
            print(
                f"{case.id}: {answer.status} / {answer.reason} / {answer.elapsed_ms}ms", flush=True
            )
    result["complete"] = True
    result["finished_at"] = datetime.now(UTC).isoformat()
    save()
    print(
        json.dumps(
            {k: result[k] for k in ("processing", "retrieval_metrics", "offline_verification")},
            indent=2,
        )
    )


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--dataset", type=Path, default=ROOT / "samples/fleetops_demo/evaluation_questions.json"
    )
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument(
        "--answers", action="store_true", help="Run generation in addition to retrieval"
    )
    parser.add_argument("--case-ids", help="Comma-separated case IDs; omitted means all cases")
    parser.add_argument(
        "--timeout",
        type=int,
        choices=range(1, 301),
        metavar="1..300",
        help="Explicit per-generation-request budget override; recorded in report",
    )
    args = parser.parse_args()
    if args.output.exists():
        parser.error("Output exists. Use a new path to preserve prior evaluation evidence.")
    args.output.parent.mkdir(parents=True, exist_ok=True)
    with tempfile.TemporaryDirectory(prefix="knowledgebridge-m5-") as temporary:
        evaluate(args, Path(temporary))

"""Reproducible local demo probe; fixture questions are AI-authored, not a benchmark."""

import json
from pathlib import Path

from knowledgebridge.config import load_settings
from knowledgebridge.embedding_adapter import OllamaEmbedder
from knowledgebridge.index_repository import IndexRepository
from knowledgebridge.ingestion import ingest
from knowledgebridge.models import KnowledgeCollection
from knowledgebridge.retriever import retrieve

ROOT = Path(__file__).resolve().parents[1]


def evaluate(data_dir: Path, output: Path) -> None:
    settings = load_settings(ROOT / "config/knowledgebridge.yaml")
    embedder = OllamaEmbedder(settings.retrieval)
    collection = KnowledgeCollection(title="FleetOps Demo — retrieval evaluation")
    manifest = json.loads((ROOT / "samples/fleetops_demo/manifest.json").read_text())
    for source in manifest["documents"]:
        collection, result = ingest(
            collection,
            (ROOT / "samples/fleetops_demo" / source["filename"]).read_bytes(),
            source["filename"],
            settings,
            version=source["version"],
        )
        if not result.accepted:
            raise RuntimeError("Fictional sample import failed")
    repository = IndexRepository(data_dir)
    index = repository.build(collection, embedder, settings.retrieval)
    questions = json.loads((ROOT / "samples/fleetops_demo/retrieval_questions.json").read_text())[
        "questions"
    ]
    outcomes = []
    for question in questions:
        methods = {}
        for mode in ("keyword", "semantic", "hybrid"):
            report = retrieve(
                repository,
                collection.collection_id,
                question["question"],
                mode,
                settings.retrieval,
                embedder if mode != "keyword" else None,
            )
            matched = [
                h
                for h in report.hits
                if any(
                    target["filename"] == h.filename and target["contains"] in h.passage.text
                    for target in question["targets"]
                )
            ]
            methods[mode] = {
                "target_found_at_5": bool(matched) if question["targets"] else None,
                "passage_ids": [h.passage.passage_id for h in report.hits],
                "elapsed_ms": report.elapsed_ms,
            }
        outcomes.append(
            {"id": question["id"], "category": question["category"], "results": methods}
        )
    supported = [o for o, q in zip(outcomes, questions, strict=True) if q["targets"]]
    result = {
        "model": index.identity.model_dump(mode="json"),
        "generation": index.generation,
        "collection_id": collection.collection_id,
        "passages": index.passage_count,
        "question_count": len(questions),
        "targeted_question_count": len(supported),
        "top_k": settings.retrieval.top_k,
        "candidate_count": settings.retrieval.candidate_count,
        "rrf_k": settings.retrieval.rrf_k,
        "note": "AI-authored development probes, not independent human-authored evaluation or answer support measurement. Unsupported queries intentionally have no success target; retrieval is not abstention.",
        "target_hit_rate_at_5": {
            mode: sum(o["results"][mode]["target_found_at_5"] for o in supported) / len(supported)
            for mode in ("keyword", "semantic", "hybrid")
        },
        "outcomes": outcomes,
    }
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(json.dumps(result, indent=2))
    print(json.dumps({k: v for k, v in result.items() if k != "outcomes"}, indent=2))


if __name__ == "__main__":
    import argparse

    parser = argparse.ArgumentParser()
    parser.add_argument("--data-dir", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    evaluate(args.data_dir, args.output)

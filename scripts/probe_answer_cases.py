"""Targeted policy regression probes against the fictional demo only."""

import argparse
import json
from pathlib import Path

from evaluate_answers import QUESTIONS

from knowledgebridge.answer_generator import OllamaGenerator
from knowledgebridge.answering import ask
from knowledgebridge.config import load_settings
from knowledgebridge.embedding_adapter import OllamaEmbedder
from knowledgebridge.index_repository import IndexRepository

ROOT = Path(__file__).resolve().parents[1]

if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--data-dir", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--cases", default="0,5,6")
    args = parser.parse_args()
    settings = load_settings(ROOT / "config/knowledgebridge.yaml")
    repo = IndexRepository(args.data_dir)
    collection = next(c for c, _ in repo.catalog() if c.title == "FleetOps Demo — fictional")
    results = []
    for index in [int(i) for i in args.cases.split(",")]:
        category, question, expected = QUESTIONS[index]
        answer = ask(
            repo,
            collection.collection_id,
            question,
            settings,
            OllamaEmbedder(settings.retrieval),
            OllamaGenerator(settings.retrieval, settings.generation),
        )
        results.append(
            {
                "case": index,
                "category": category,
                "question": question,
                "expected_status": expected,
                "status_matches": answer.status == expected,
                "answer": answer.model_dump(mode="json"),
            }
        )
        args.output.write_text(
            json.dumps(
                {
                    "provenance": "AI-authored development probes; independent human evaluation pending.",
                    "results": results,
                },
                indent=2,
            )
        )
        print(f"{index}: {answer.status} / {answer.reason}, {answer.elapsed_ms}ms", flush=True)

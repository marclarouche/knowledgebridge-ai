"""Create an unfilled review worksheet or score reviews bound to exact recorded outputs."""

import argparse
import json
from pathlib import Path

from knowledgebridge.answer_models import AnswerRecord
from knowledgebridge.evaluation import HumanReview, human_support_metrics

if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--evaluation", type=Path, required=True)
    parser.add_argument("--reviews", type=Path, help="Completed independent human reviews JSON")
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    if args.output.exists():
        parser.error("Output exists; choose a new path")
    evaluation = json.loads(args.evaluation.read_text())
    if not evaluation.get("complete"):
        parser.error("Evaluation run is incomplete")
    rows = evaluation["answers"]
    answers = {row["id"]: AnswerRecord.model_validate(row["answer"]) for row in rows}
    if len(answers) != len(rows):
        parser.error("Duplicate answer IDs")
    if args.reviews:
        reviews = [HumanReview.model_validate(row) for row in json.loads(args.reviews.read_text())]
        result = human_support_metrics(answers, reviews)
    else:
        result = [
            {
                "case_id": row["id"],
                "answer_digest": row["answer_digest"],
                "reviewer": "",
                "verdict": "",
                "rationale": "",
            }
            for row in rows
        ]
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(result, indent=2) + "\n")
    print(
        "Review scores saved."
        if args.reviews
        else "Unfilled worksheet saved. No human review claimed."
    )

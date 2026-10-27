import argparse
import json
from pathlib import Path
from . import store
from .corpus import build_index


def main():
    parser = argparse.ArgumentParser(prog="labelguard")
    subs = parser.add_subparsers(dest="command", required=True)
    index = subs.add_parser("index", help="Idempotently parse, chunk, embed and index the pinned corpus")
    index.add_argument("--force", action="store_true")
    subs.add_parser("init-db")
    schema = subs.add_parser("contracts")
    schema.add_argument("--output", default="docs/contracts")
    evaluation = subs.add_parser("evaluate")
    evaluation.add_argument("--output", default="output/evaluation/results.json")
    args = parser.parse_args()
    if args.command == "index":
        print(json.dumps(build_index(args.force), indent=2))
    elif args.command == "init-db":
        store.init_db()
        print("State store ready")
    elif args.command == "contracts":
        from .api import export_openapi
        from .models import LabelRequest, Recommendation, Feedback

        root = Path(args.output)
        root.mkdir(parents=True, exist_ok=True)
        for name, model in [
            ("request", LabelRequest),
            ("recommendation", Recommendation),
            ("feedback", Feedback),
        ]:
            (root / f"{name}.schema.json").write_text(
                json.dumps(model.model_json_schema(), indent=2), encoding="utf-8"
            )
        export_openapi(root / "openapi.json")
        print("Published contracts in", root)
    elif args.command == "evaluate":
        from .evaluation import run_evaluation

        run_evaluation(args.output)


if __name__ == "__main__":
    main()

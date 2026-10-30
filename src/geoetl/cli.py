"""Command-line entry point: ``geoetl run pipeline.yml``."""

from __future__ import annotations

import argparse
import logging
import sys

from geoetl.config import ConfigError, load_config
from geoetl.pipeline import Pipeline, QAGateFailed
from geoetl.transform import available_transforms


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(prog="geoetl", description=__doc__)
    sub = parser.add_subparsers(dest="command", required=True)

    run_p = sub.add_parser("run", help="run a pipeline config")
    run_p.add_argument("config", help="path to pipeline YAML")
    run_p.add_argument("--qa-report", help="write the QA report (markdown) here")
    run_p.add_argument("-v", "--verbose", action="store_true")

    val_p = sub.add_parser("validate", help="validate a config without running it")
    val_p.add_argument("config")

    sub.add_parser("transforms", help="list available transform ops")

    args = parser.parse_args(argv)
    logging.basicConfig(
        level=logging.DEBUG if getattr(args, "verbose", False) else logging.INFO,
        format="%(levelname)s %(name)s: %(message)s",
    )

    if args.command == "transforms":
        print("\n".join(available_transforms()))
        return 0

    try:
        config = load_config(args.config)
    except ConfigError as exc:
        print(exc, file=sys.stderr)
        return 2

    if args.command == "validate":
        print(f"{args.config}: OK ({config.name})")
        return 0

    try:
        result = Pipeline(config).run(qa_report_path=args.qa_report)
    except QAGateFailed as exc:
        print(exc, file=sys.stderr)
        print(exc.report.to_markdown(), file=sys.stderr)
        return 3

    print(
        f"{config.name}: {result.rows_in} -> {result.rows_out} rows "
        f"({result.quarantined} quarantined) -> {result.destination} "
        f"in {result.elapsed_s:.2f}s"
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

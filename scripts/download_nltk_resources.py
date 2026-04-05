from __future__ import annotations

import argparse
import sys
from pathlib import Path

ROOT_DIR = Path(__file__).resolve().parents[1]
if str(ROOT_DIR) not in sys.path:
    sys.path.insert(0, str(ROOT_DIR))

from pipelines.tfidf_randomforest.preprocessing import download_nltk_resources  # noqa: E402


def build_argument_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Download NLTK resources required for TF-IDF lemmatization.")
    parser.add_argument("--download-dir", default=None, help="Optional custom NLTK data directory.")
    parser.add_argument("--quiet", action="store_true", help="Reduce NLTK downloader output.")
    return parser


def main() -> None:
    args = build_argument_parser().parse_args()
    results = download_nltk_resources(download_dir=args.download_dir, quiet=args.quiet)

    print("NLTK resource download results")
    for package_name, success in results.items():
        print(f"{package_name}: {'ok' if success else 'failed'}")

    if not all(results.values()):
        raise SystemExit("Some NLTK resources failed to download.")


if __name__ == "__main__":
    main()

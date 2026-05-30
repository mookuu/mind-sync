import sys

from smoke_all import build_parser, run_smoke


def main():
    parser = build_parser()
    parser.description = "mind-sync auth smoke check (delegates to smoke_all)"
    args = parser.parse_args()
    args.mode = "auth"
    args.skip_sync = True
    print(run_smoke(args))
    return 0


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except Exception as exc:
        print(f"smoke failed: {exc}", file=sys.stderr)
        raise SystemExit(1)

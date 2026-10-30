from nomo.cli import main

if __name__ == "__main__":
    import sys

    try:
        sys.exit(main())
    except Exception as exc:
        print("nomo: " + str(exc), file=sys.stderr)
        sys.exit(1)

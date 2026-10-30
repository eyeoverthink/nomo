"""NoMo command line."""

import argparse
import json
import sys
import time

from nomo import absorb, agent, doctor, dream, evolve, ledger, replicate, runbox, tools


def _print(obj):
    if isinstance(obj, str):
        print(obj)
    else:
        print(json.dumps(obj, indent=2, ensure_ascii=False, default=str))


def _configure_stdio():
    for stream in (sys.stdout, sys.stderr):
        reconfigure = getattr(stream, "reconfigure", None)
        if reconfigure is None:
            continue
        try:
            reconfigure(encoding="utf-8", errors="replace")
        except Exception:
            pass


def main(argv=None):
    _configure_stdio()
    parser = argparse.ArgumentParser(prog="nomo", description="NoMo, a local file-backed agent.")
    sub = parser.add_subparsers(dest="cmd", required=True)

    sub.add_parser("status", help="Show the models and memory this process will use.")
    setup = sub.add_parser("setup", help="Show which public models to pull.")
    setup.add_argument("--pull", action="store_true", help="Pull the missing public Ollama models.")
    setup.add_argument("--with-needle", action="store_true", help="Create .venv and install the Needle 3 tool router.")
    sub.add_parser("models", help="List local tags and the tags NoMo skips.")
    ask = sub.add_parser("ask")
    ask.add_argument("text")
    sub.add_parser("chat")
    dream_cmd = sub.add_parser("dream", help="Explore a small tree, replay it, and promote a policy.")
    dream_cmd.add_argument("goal", nargs="?", default="")
    dream_cmd.add_argument("--branches", type=int, default=2)
    dream_cmd.add_argument("--refine", type=int, default=1)
    dream_cmd.add_argument("--rounds", type=int, default=1)
    evo = sub.add_parser("evolve", help="Architect, critic, and executor. Execution needs NOMO_ALLOW_RUN=1.")
    evo.add_argument("task")
    evo.add_argument("--rounds", type=int, default=2)
    absorb_cmd = sub.add_parser("absorb", help="Save one public page into the vault.")
    absorb_cmd.add_argument("url")
    par = sub.add_parser("parallel")
    par.add_argument("goal")
    choice = sub.add_parser("choose")
    choice.add_argument("question")
    choice.add_argument("options", nargs="+")
    child = sub.add_parser("replicate")
    child.add_argument("name")
    watch = sub.add_parser("watch")
    watch.add_argument("--max", type=int, default=1)
    watch.add_argument("--every", type=int, default=1800, help="Seconds between dream passes.")
    sub.add_parser("journal")
    run = sub.add_parser("run", help="Run one local command. Requires NOMO_ALLOW_RUN=1.")
    run.add_argument("argv", nargs=argparse.REMAINDER)

    args = parser.parse_args(argv)
    if args.cmd == "status":
        _print(tools.status())
        _print(ledger.verify())
        return 0
    if args.cmd == "setup":
        if args.with_needle:
            _print(doctor.install_needle())
        if args.pull:
            _print(doctor.pull_missing())
        _print(doctor.report())
        return 0
    if args.cmd == "models":
        from nomo import ollama_client, select

        models = ollama_client.inventory(refresh=True)
        _print(
            {
                "route": ollama_client.route_model(),
                "reason": ollama_client.reason_model(),
                "embed": ollama_client.embed_model(),
                "local": [item["name"] for item in models if select.is_auto(item)],
                "skipped": [item["name"] for item in models if not select.is_auto(item)],
            }
        )
        return 0
    if args.cmd == "ask":
        _print(agent.ask(args.text)["reply"])
        return 0
    if args.cmd == "chat":
        print("NoMo. Empty line exits. Memory is the vault.")
        while True:
            try:
                line = input("you> ").strip()
            except EOFError:
                return 0
            if not line:
                return 0
            print(agent.ask(line)["reply"])
            print()
        return 0
    if args.cmd == "dream":
        _print(dream.run(args.goal, branches=args.branches, refine=args.refine, rounds=args.rounds))
        return 0
    if args.cmd == "evolve":
        _print(evolve.run(args.task, rounds=args.rounds))
        return 0
    if args.cmd == "absorb":
        _print(absorb.fetch(args.url))
        return 0
    if args.cmd == "parallel":
        _print(agent.parallel(args.goal))
        return 0
    if args.cmd == "choose":
        _print(agent.choose(args.question, args.options))
        return 0
    if args.cmd == "replicate":
        _print(replicate.run(args.name))
        return 0
    if args.cmd == "watch":
        cycles = max(1, min(args.max, 24))
        for index in range(cycles):
            _print(dream.run())
            if index + 1 < cycles:
                time.sleep(max(30, args.every))
        return 0
    if args.cmd == "journal":
        _print(ledger.recent(20))
        return 0
    if args.cmd == "run":
        argv = list(args.argv)
        if argv and argv[0] == "--":
            argv = argv[1:]
        if not argv:
            print("nomo: give a command after run.", file=sys.stderr)
            return 2
        try:
            result = runbox.execute(argv)
        except PermissionError as exc:
            print("nomo: " + str(exc), file=sys.stderr)
            return 2
        ledger.append("run", " ".join(argv)[:200], {"code": result["code"]})
        if result["stdout"]:
            print(result["stdout"], end="" if result["stdout"].endswith("\n") else "\n")
        if result["stderr"]:
            print(result["stderr"], file=sys.stderr, end="" if result["stderr"].endswith("\n") else "\n")
        return result["code"]
    return 1

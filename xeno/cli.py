import argparse
import json
import os
import secrets
from datetime import UTC, datetime
from pathlib import Path


def main():
    parser = argparse.ArgumentParser(prog="xeno")
    commands = parser.add_subparsers(dest="command", required=True)
    demo = commands.add_parser("demo", help="Run one complete headless episode through the API")
    demo.add_argument("--config", type=Path, help="Private episode JSON; defaults to built-in demo")
    demo.add_argument(
        "--policy", choices=("passive", "random", "fixed", "adaptive"), default="adaptive"
    )
    demo.add_argument("--output", type=Path)
    benchmark = commands.add_parser(
        "benchmark", help="Compare four policies on development fixtures"
    )
    benchmark.add_argument("--seeds", type=int, default=2)
    benchmark.add_argument("--output", type=Path)
    replay = commands.add_parser("replay", help="Inspect a recorded public observation stream")
    replay.add_argument("path", type=Path)
    commands.add_parser("verify", help="Run the independent analytic BDF fixture")
    serve = commands.add_parser("serve", help="Start the loopback API for a future Unreal client")
    serve.add_argument("--port", type=int, default=8766)
    serve.add_argument("--data-dir", type=Path, default=Path("runs/local"))
    studio = commands.add_parser("scene-studio", help="Local prompt-to-Unreal scenario studio")
    studio.add_argument("--port", type=int, default=8770)
    studio.add_argument("--workspace", type=Path, default=Path.cwd())
    scene = commands.add_parser("scene-plan", help="Create a scene with GPT-6 Luna through Codex")
    scene.add_argument("prompt")
    scene.add_argument("--scenario", default="auto")
    scene.add_argument("--output", type=Path, default=Path("runs/scenario-plan"))
    well = commands.add_parser(
        "well-prepare", help="Prepare one verified The Well reference replay"
    )
    well.add_argument("--workspace", type=Path, default=Path.cwd())
    args = parser.parse_args()
    stamp = datetime.now(UTC).strftime("%Y%m%dT%H%M%S%fZ")
    if args.command == "well-prepare":
        from xeno.scenes.well import prepare_reference

        result = prepare_reference(args.workspace.resolve())
        print(
            json.dumps(
                {
                    key: result[key]
                    for key in ("dataset", "source_sha256", "nx", "ny", "density_range")
                }
            )
        )
        return
    if args.command == "scene-studio":
        import uvicorn

        from xeno.scenes.studio import create_studio

        uvicorn.run(
            create_studio(args.workspace), host="127.0.0.1", port=args.port, access_log=False
        )
        return
    if args.command == "scene-plan":
        from xeno.scenes.models import PlanRequest
        from xeno.scenes.planner import plan_scene

        result = plan_scene(PlanRequest(prompt=args.prompt, scenario=args.scenario), args.output)
        print(result.model_dump_json(indent=2))
        return
    if args.command == "serve":
        import uvicorn

        from xeno.service.app import create_app

        args.data_dir.mkdir(parents=True, exist_ok=True)
        credentials = args.data_dir / "credentials.private.json"
        token = os.environ.get("XENO_ADMIN_TOKEN")
        if not token:
            if credentials.exists():
                token = json.loads(credentials.read_text(encoding="utf-8"))["admin_token"]
            else:
                token = secrets.token_urlsafe(32)
                credentials.write_text(json.dumps({"admin_token": token}), encoding="utf-8")
        print(f"Local API: http://127.0.0.1:{args.port}/docs")
        print(f"Private credentials file (if generated): {credentials.resolve()}")
        (args.data_dir / "service.pid").write_text(str(os.getpid()), encoding="ascii")
        uvicorn.run(
            create_app(args.data_dir / "xeno.sqlite3", token),
            host="127.0.0.1",
            port=args.port,
            access_log=False,
        )
        return
    if args.command == "verify":
        from xeno.simulation.core import reversible_fixture

        result = reversible_fixture()
    else:
        from xeno.evaluation import runner

        if args.command == "demo":
            from xeno.service.schemas import EpisodeConfig

            config = (
                EpisodeConfig.model_validate_json(args.config.read_text(encoding="utf-8"))
                if args.config
                else EpisodeConfig()
            )
            output = args.output or Path("runs") / f"demo-{stamp}"
            result = runner.demo(output, config, args.policy)
            print(f"Run saved: {output.resolve()}")
        elif args.command == "benchmark":
            output = args.output or Path("runs") / f"benchmark-{stamp}"
            result = runner.benchmark(output, args.seeds)
            print(f"Comparison saved: {output.resolve()}")
        else:
            result = runner.replay(args.path)
    print(json.dumps(result, indent=2, allow_nan=False))


if __name__ == "__main__":
    main()

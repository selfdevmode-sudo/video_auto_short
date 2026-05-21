"""faceless — command line interface.

Usage:
  faceless ideas "<niche or theme>"      brainstorm video ideas
  faceless script "<title>"              write a script (creates a project)
  faceless voice  <project_folder>       generate the voiceover
  faceless build  <project_folder>       captions + assemble final.mp4
  faceless upload <project_folder>       (optional) upload as private draft
  faceless auto   "<title>"              run script→voice→build in one go
  faceless list                          show all projects and their stage

Run `faceless` with no args for this help.
"""
from __future__ import annotations

import sys
from pathlib import Path

from .common import C, Project, die, load_config, ok, say
from .stages import assemble, ideate, script, upload, voice


def _help():
    print(__doc__)


def main(argv: list[str] | None = None) -> None:
    argv = argv if argv is not None else sys.argv[1:]
    if not argv or argv[0] in ("-h", "--help", "help"):
        _help()
        return

    cmd = argv[0]
    args = argv[1:]
    cfg = load_config()

    if cmd == "ideas":
        if not args:
            die('Give me a niche, e.g.  faceless ideas "how databases work"')
        ideate.run(cfg, " ".join(args))

    elif cmd == "script":
        if not args:
            die('Give me a title, e.g.  faceless script "Why your wifi is slow"')
        title = " ".join(args)
        proj = Project.create(cfg["output"]["dir"], title)
        script.run(cfg, proj)

    elif cmd == "voice":
        if not args:
            die("Give me a project folder, e.g.  faceless voice ./videos/2026...-title")
        voice.run(cfg, Project.open(args[0]))

    elif cmd == "build":
        if not args:
            die("Give me a project folder, e.g.  faceless build ./videos/2026...-title")
        assemble.run(cfg, Project.open(args[0]))

    elif cmd == "upload":
        if not args:
            die("Give me a project folder, e.g.  faceless upload ./videos/2026...-title")
        upload.run(cfg, Project.open(args[0]))

    elif cmd == "auto":
        # script -> voice -> build, pausing for review BEFORE voiceover
        if not args:
            die('Give me a title, e.g.  faceless auto "Why your wifi is slow"')
        title = " ".join(args)
        proj = Project.create(cfg["output"]["dir"], title)
        script.run(cfg, proj)
        print()
        say(f"{C.BOLD}Review gate.{C.END} Edit the script above if you want, then press Enter to continue (Ctrl-C to stop here).")
        try:
            input()
        except KeyboardInterrupt:
            print()
            ok("Stopped. Resume any time with: faceless voice " + str(proj.root))
            return
        voice.run(cfg, proj)
        assemble.run(cfg, proj)

    elif cmd == "list":
        root = Path(cfg["output"]["dir"])
        if not root.exists():
            say("No projects yet. Start with: faceless ideas \"<your niche>\"")
            return
        projs = sorted(p for p in root.iterdir() if p.is_dir())
        if not projs:
            say("No projects yet.")
            return
        for p in projs:
            stage = Project.open(str(p)).read_state().get("stage", "?")
            print(f"  {C.GREY}{stage:>10}{C.END}  {p.name}")

    else:
        die(f"Unknown command '{cmd}'. Run `faceless` for help.")


if __name__ == "__main__":
    main()

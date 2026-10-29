"""Prepare a NEW E0/E1 retry batch profile; never launch training or touch old runs."""
import argparse
from datetime import datetime
import json
from pathlib import Path
import re

ROOT = Path(__file__).resolve().parents[1]


def write_program_config(folder):
    folder = folder.resolve()
    properties = {
        "minifls.launch.workspace": ROOT.as_posix(),
        "spring.datasource.url": "jdbc:sqlite:"+(folder / "minifls.db").as_posix(),
        "minifls.audit.config": (folder / "reproducibility-audit.json").as_posix(),
        "minifls.matched.config": (folder / "fairness-matched-lambda.json").as_posix(),
        "minifls.audit.output": (folder / "e0").as_posix(),
        "minifls.matched.output": (folder / "e1").as_posix(),
        "minifls.launch.enabled": "true",
        "minifls.worker.max-attempts": "4",
    }
    # A single argument works even when the IDE/Gradle launcher does not split
    # an entire arguments string. Forward slashes avoid .properties escapes.
    profile = folder / "application-retry.properties"
    text = "\n".join(f"{key}={value}" for key, value in properties.items())+"\n"
    escaped = []
    for char in text:
        if ord(char) < 128:
            escaped.append(char)
        else:
            units = char.encode("utf-16-be")
            escaped.extend(f"\\u{int.from_bytes(units[i:i+2], 'big'):04x}" for i in range(0, len(units), 2))
    profile.write_text("".join(escaped), encoding="ascii")
    argument = "--spring.config.additional-location="+profile.as_uri()
    (folder / "program-arguments.txt").write_text(argument+"\n", encoding="utf-8")
    return argument


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--name", default=datetime.now().strftime("%Y%m%d-%H%M%S"))
    args = parser.parse_args()
    if not re.fullmatch(r"[A-Za-z0-9_-]{1,60}", args.name):
        parser.error("Name must contain only letters, digits, '_' and '-'")
    folder = ROOT / "artifacts/research" / ("retry-"+args.name)
    audit = json.loads((ROOT / "configurations/reproducibility-audit.json").read_text(encoding="utf-8"))
    matched = json.loads((ROOT / "configurations/fairness-matched-lambda.json").read_text(encoding="utf-8"))
    matched["auditReportPath"] = (folder / "e0/reproducibility-audit.json").relative_to(ROOT).as_posix()
    folder.mkdir(parents=True, exist_ok=False)
    for name, config in (("reproducibility-audit.json", audit), ("fairness-matched-lambda.json", matched)):
        (folder / name).write_text(json.dumps(config, indent=2)+"\n", encoding="utf-8")
    settings = {
        "MINIFLS_WORKSPACE": str(ROOT),
        "MINIFLS_DATABASE": str(folder / "minifls.db"),
        "MINIFLS_AUDIT_CONFIG": str(folder / "reproducibility-audit.json"),
        "MINIFLS_MATCHED_CONFIG": str(folder / "fairness-matched-lambda.json"),
        "MINIFLS_AUDIT_OUTPUT": str(folder / "e0"),
        "MINIFLS_MATCHED_OUTPUT": str(folder / "e1"),
        "MINIFLS_LAUNCH_ENABLED": "true",
        "MINIFLS_WORKER_MAX_ATTEMPTS": "4",
    }
    lines = "\n".join(f"{key}={value}" for key, value in settings.items())+"\n"
    (folder / "run.env").write_text(lines, encoding="utf-8")
    write_program_config(folder)
    print("Prepared config ONLY; no experiment has started.")
    print(f"Copy these environment settings into your IDE Run Configuration ({folder / 'run.env'}):")
    print(lines)
    print(f"Alternatively, paste the single line from {folder / 'program-arguments.txt'} into IDE Program arguments.")
    print("Restart the updated Python worker and rebuild Java before starting this new batch.")


if __name__ == "__main__":
    main()

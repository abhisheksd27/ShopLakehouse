"""Build from a clean local context, excluding external-drive metadata and secrets."""

import argparse
import shutil
import subprocess
import tempfile
from pathlib import Path

parser = argparse.ArgumentParser()
parser.add_argument("--airflow", action="store_true")
parser.add_argument("--minio", action="store_true")
parser.add_argument("--cloud", action="store_true")
args = parser.parse_args()
root = Path(__file__).resolve().parents[1]
allowed = [
    "Dockerfile",
    "pyproject.toml",
    "README.md",
    "src",
    "config",
    "sql",
    "dbt",
    "scripts",
    "dags",
    "docker",
]
with tempfile.TemporaryDirectory(prefix="shoplakehouse-build-") as temporary:
    context = Path(temporary)
    for entry in allowed:
        base = root / entry
        paths = base.rglob("*") if base.is_dir() else [base]
        for path in paths:
            relative = path.relative_to(root)
            if not path.is_file() or any(
                part.startswith("._")
                or part in {"__pycache__", "target", "logs", "dbt_packages", ".terraform"}
                for part in relative.parts
            ):
                continue
            destination = context / relative
            destination.parent.mkdir(parents=True, exist_ok=True)
            shutil.copyfile(path, destination)
    tag = "shoplakehouse-airflow:dev" if args.airflow else "shoplakehouse:dev"
    dockerfile = "docker/airflow.Dockerfile" if args.airflow else "Dockerfile"
    if args.minio:
        tag = "shoplakehouse-minio:dev"
        dockerfile = "docker/minio.Dockerfile"
    command = ["docker", "build", "-t", tag, "-f", str(context / dockerfile)]
    if args.cloud:
        command.extend(["--build-arg", "INSTALL_CLOUD=true"])
    command.append(str(context))
    subprocess.run(command, check=True)

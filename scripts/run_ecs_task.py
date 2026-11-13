"""Run a reviewed ECS task using terraform outputs; never prints secret values."""

import argparse
import json
import subprocess
from pathlib import Path

import boto3

parser = argparse.ArgumentParser()
parser.add_argument("--environment", choices=["dev", "prod"], default="dev")
parser.add_argument("--task", choices=["worker", "bootstrap", "airflow-init"], default="worker")
parser.add_argument("command", nargs="*")
args = parser.parse_args()
root = Path(__file__).resolve().parents[1]
output = subprocess.check_output(
    [
        "terraform",
        f"-chdir={root/'infra/environments'/args.environment}",
        "output",
        "-json",
        "deployment",
    ],
    text=True,
)
deployment = json.loads(output)
task_key = {
    "worker": "worker_task",
    "bootstrap": "bootstrap_task",
    "airflow-init": "airflow_init_task",
}[args.task]
container = {"worker": "pipeline", "bootstrap": "bootstrap", "airflow-init": "airflow"}[args.task]
client = boto3.client("ecs")
request = {
    "cluster": deployment["cluster"],
    "taskDefinition": deployment[task_key],
    "launchType": "FARGATE",
    "networkConfiguration": {
        "awsvpcConfiguration": {
            "subnets": deployment["task_subnets"],
            "securityGroups": [deployment["task_security_group"]],
            "assignPublicIp": "ENABLED" if deployment["assign_public_ip"] else "DISABLED",
        }
    },
}
if args.command:
    request["overrides"] = {"containerOverrides": [{"name": container, "command": args.command}]}
result = client.run_task(**request)
if result.get("failures"):
    raise RuntimeError("ECS task placement failed")
arn = result["tasks"][0]["taskArn"]
print(f"Started {arn}")
client.get_waiter("tasks_stopped").wait(
    cluster=deployment["cluster"], tasks=[arn], WaiterConfig={"Delay": 15, "MaxAttempts": 240}
)
task = client.describe_tasks(cluster=deployment["cluster"], tasks=[arn])["tasks"][0]
codes = [item.get("exitCode", 1) for item in task["containers"]]
if any(codes):
    raise SystemExit("Task failed; inspect its CloudWatch log stream")
print("Task completed successfully")

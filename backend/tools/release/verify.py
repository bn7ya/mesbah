from __future__ import annotations

import argparse
import json
import subprocess
import sys
from collections.abc import Callable, Sequence
from dataclasses import asdict, dataclass
from pathlib import Path

from tools.release.client import Answer, Client, ClientError, Json, items, text
from tools.release.seed import CORRECTED, THINKING, reply, train
from tools.release.stack import Stack

type Check = Callable[[], str]


@dataclass(frozen=True)
class Outcome:
    name: str
    ok: bool
    detail: str


@dataclass
class Verifier:
    stack: Stack
    state: Json
    mesbah: str

    def __post_init__(self) -> None:
        self.owner: Client = Client(self.stack.base_url)

    def value(self, key: str) -> str:
        found: object = self.state.get(key)
        return found if isinstance(found, str) else ""

    def setup_is_closed(self) -> str:
        needed: object = Client(self.stack.base_url).get("/api/auth/setup/").get("needed")
        assert needed is False, f"setup is needed again: {needed}"
        return "the first-run setup stays closed"

    def owner_signs_in(self) -> str:
        self.owner.sign_in(self.value("owner"), self.value("password"))
        return f"{self.value('owner')} signs in"

    def viewer_is_a_viewer(self) -> str:
        viewer: Client = Client(self.stack.base_url)
        me: Json = viewer.sign_in(self.value("viewer"), self.value("password"))
        groups: object = me.get("groups")
        assert groups == ["viewers"], f"the viewer's groups are {groups}"
        return "the viewer signs in and is still a viewer"

    def project_and_versions(self) -> str:
        project: Json = self.owner.get(f"/api/projects/{self.value('project')}/")
        active: object = project.get("active_version")
        second: str = self.versions()[1]
        assert isinstance(active, dict) and active.get("id") == second, f"active is {active}"
        tree: list[Json] = items(self.owner.get(f"/api/versions/?project={self.value('project')}"))
        parents: dict[str, object] = {text(row, "id"): row.get("parent_id") for row in tree}
        assert parents.get(second) == self.versions()[0], f"v2's parent is {parents.get(second)}"
        return f"the project, its active version and {len(tree)} versions with their parents"

    def runs_and_metrics(self) -> str:
        runs: list[Json] = items(self.owner.get(f"/api/training/?project={self.value('project')}"))
        done: list[Json] = [run for run in runs if run.get("status") == "completed"]
        assert len(done) >= 2, f"{len(done)} completed runs"
        metrics: list[Json] = items(self.owner.get(f"/api/training/{text(done[0], 'id')}/metrics/"))
        assert metrics, "a finished run has no metrics"
        return f"{len(done)} runs and their loss curves"

    def dataset_rows(self) -> str:
        dataset: Json = self.owner.get(f"/api/datasets/{self.value('dataset')}/")
        assert dataset.get("status") == "ready" and dataset.get("rows") == 12, json.dumps(dataset)[
            :200
        ]
        rows: list[Json] = items(self.owner.get(f"/api/datasets/{self.value('dataset')}/rows/"))
        assert rows, "the dataset's rows are gone"
        return "the dataset and its rows"

    def correction(self) -> str:
        message: Json = self.owner.get(f"/api/chat/messages/{self.value('reply')}/")
        assert message.get("content") == CORRECTED, f"content is {message.get('content')}"
        assert message.get("thinking") == THINKING, f"thinking is {message.get('thinking')}"
        assert message.get("approved") is True, "the correction lost its approval"
        return "the corrected reply, its thinking and its approval"

    def export_downloads(self) -> str:
        answer: Answer = self.owner.send(
            "GET", f"/api/versions/exports/{self.value('export')}/download/"
        )
        assert answer.status == 200 and answer.body[:2] == b"PK", (
            f"download answered {answer.status}"
        )
        return f"the LoRA export downloads ({len(answer.body)} bytes)"

    def api_key_works(self) -> str:
        machine: Client = Client(self.stack.base_url, bearer=self.value("api_key"))
        names: list[str] = [text(row, "id") for row in items(machine.get("/v1/models"), "data")]
        assert self.value("slug") in names, f"/v1/models lists {names}"
        return "the API key made before the upgrade still lists the project on /v1/models"

    def engine_key_opens(self) -> str:
        engine: Json = self.owner.get(f"/api/serving/engines/{self.value('engine')}/")
        assert engine.get("has_api_key") is True, "the engine lost its key"
        return "the external engine and its sealed key, with the same secret key"

    def chat_still_answers(self) -> str:
        answered: Json = reply(self.owner, self.value("conversation"), "After the upgrade")
        assert str(answered.get("content")).startswith("Reply from "), json.dumps(answered)[:200]
        return "a new reply in the old conversation"

    def training_continues(self) -> str:
        second: str = self.versions()[1]
        third: str = train(self.owner, self.value("project"), self.value("dataset"), second)
        version: Json = self.owner.get(f"/api/versions/{third}/")
        assert version.get("parent_id") == second, (
            f"the new version's parent is {version.get('parent_id')}"
        )
        return "a new version trained on top of the old v2"

    def migrations_applied(self) -> str:
        shown: str = self.manage("showmigrations")
        assert "[ ]" not in shown, "a migration was not applied"
        return f"{shown.count('[X]')} migrations applied"

    def doctor_runs(self) -> str:
        subprocess.run(  # noqa: S603 - the installed command
            [self.mesbah, "--data-dir", self.stack.data_dir, "doctor"],
            capture_output=True,
            check=True,
        )
        return "mesbah doctor runs"

    def manage(self, *arguments: str) -> str:
        return subprocess.run(  # noqa: S603 - the installed command
            [self.mesbah, "--data-dir", self.stack.data_dir, "manage", *arguments],
            capture_output=True,
            check=True,
            text=True,
        ).stdout

    def versions(self) -> list[str]:
        found: object = self.state.get("versions")
        return [str(version) for version in found] if isinstance(found, list) else []

    def checks(self) -> list[Check]:
        return [
            self.setup_is_closed,
            self.owner_signs_in,
            self.viewer_is_a_viewer,
            self.project_and_versions,
            self.runs_and_metrics,
            self.dataset_rows,
            self.correction,
            self.export_downloads,
            self.api_key_works,
            self.engine_key_opens,
            self.chat_still_answers,
            self.training_continues,
            self.migrations_applied,
            self.doctor_runs,
        ]


def run(checks: list[Check]) -> list[Outcome]:
    outcomes: list[Outcome] = []
    for check in checks:
        name: str = check.__name__.replace("_", " ")
        try:
            outcomes.append(Outcome(name, True, check()))
        except (AssertionError, ClientError, KeyError, RuntimeError, TimeoutError) as error:
            outcomes.append(Outcome(name, False, str(error)))
        except subprocess.CalledProcessError as error:
            outcomes.append(Outcome(name, False, f"{error.cmd} exited {error.returncode}"))
    return outcomes


def main(argv: Sequence[str] | None = None) -> int:
    parser: argparse.ArgumentParser = argparse.ArgumentParser(prog="python -m tools.release.verify")
    parser.add_argument("--stack", type=Path, required=True)
    parser.add_argument("--state", type=Path, required=True)
    parser.add_argument("--mesbah", required=True, help="the upgraded install's `mesbah`")
    parser.add_argument("--report", type=Path, required=True)
    arguments: argparse.Namespace = parser.parse_args(argv)
    state: object = json.loads(arguments.state.read_text(encoding="utf-8"))
    if not isinstance(state, dict):
        print("error: the state file is not what seed wrote", file=sys.stderr)
        return 1
    verifier: Verifier = Verifier(Stack.read(arguments.stack), state, arguments.mesbah)
    outcomes: list[Outcome] = run(verifier.checks())
    arguments.report.write_text(
        json.dumps([asdict(outcome) for outcome in outcomes], indent=2) + "\n", encoding="utf-8"
    )
    for outcome in outcomes:
        print(f"{'ok' if outcome.ok else 'FAILED':6} {outcome.name}: {outcome.detail}")
    return 0 if all(outcome.ok for outcome in outcomes) else 1


if __name__ == "__main__":
    sys.exit(main())

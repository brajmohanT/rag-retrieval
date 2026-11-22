"""Load a project config and resolve its paths against the repository root."""

from pathlib import Path

import yaml

ROOT = Path(__file__).resolve().parents[2]
DEFAULT_CONFIG = ROOT / "configs" / "vidore_hr.yaml"


def load_config(path=DEFAULT_CONFIG):
    config = yaml.safe_load(Path(path).read_text())
    config["dataset"]["data_dir"] = ROOT / config["dataset"]["data_dir"]
    config["artifacts_dir"] = ROOT / config["artifacts_dir"]
    config["evaluation"]["partitions_file"] = ROOT / config["evaluation"]["partitions_file"]
    return config

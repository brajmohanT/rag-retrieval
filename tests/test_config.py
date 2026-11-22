from evidence_atlas.config import ROOT, load_config


def test_default_config_resolves_paths_from_repo_root():
    config = load_config()
    assert config["dataset"]["repo_id"] == "vidore/vidore_v3_hr"
    assert config["dataset"]["data_dir"] == ROOT / "data/vidore_v3_hr"
    assert config["artifacts_dir"] == ROOT / "artifacts"

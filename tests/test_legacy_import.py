import asyncio
import csv
import json
from pathlib import Path

from prismora_lab.backends.mock import MockBackend
from prismora_lab.legacy import import_legacy_campaign
from prismora_lab.store import LabStore


FIELDS = [
    "test_id", "conversation", "turn", "mode", "language", "model_id",
    "prompt", "input_kind", "filter_nonword", "top_n", "temperature",
    "num_completion_tokens", "prepend_bos", "enable_thinking",
]


def _request(text: str):
    return {
        "backend": "mock",
        "model": {"alias": "M", "model_id": "qwen3.6-27b"},
        "prompt_id": "source",
        "chat": [{"role": "user", "content": text}],
        "factors": {},
        "repeat": 1,
        "generation": {"temperature": 0, "max_new_tokens": 12, "prepend_bos": True, "enable_thinking": False},
        "readout": {"types": ["LOGIT_LENS", "JACOBIAN_LENS"], "top_k": 8, "filter_nonword_tokens": True},
        "intervention": None,
    }


def test_legacy_import_preserves_exact_file_bytes_and_reconstructs_chain(tmp_path):
    protocol = tmp_path / "protocol.csv"
    raw_dir = tmp_path / "raw"
    raw_dir.mkdir()
    rows = [
        {
            "test_id": "chain__r1__t1", "conversation": "chain__r1", "turn": "1", "mode": "chain",
            "language": "fr", "model_id": "qwen3.6-27b", "prompt": "Bonjour",
            "input_kind": "chat", "filter_nonword": "true", "top_n": "8", "temperature": "0",
            "num_completion_tokens": "12", "prepend_bos": "true", "enable_thinking": "false",
        },
        {
            "test_id": "chain__r1__t2", "conversation": "chain__r1", "turn": "2", "mode": "chain",
            "language": "fr", "model_id": "qwen3.6-27b", "prompt": "Continue",
            "input_kind": "chat", "filter_nonword": "true", "top_n": "8", "temperature": "0",
            "num_completion_tokens": "12", "prepend_bos": "true", "enable_thinking": "false",
        },
    ]
    with protocol.open("w", newline="", encoding="utf-8") as handle:
        writer = csv.DictWriter(handle, fieldnames=FIELDS)
        writer.writeheader()
        writer.writerows(rows)

    source_bytes = {}
    for row in rows:
        result = asyncio.run(MockBackend().run(_request(row["prompt"]))).value
        # Deliberately pretty-print to prove source bytes, not canonical JSON, are archived.
        data = (json.dumps(result, ensure_ascii=False, indent=2) + "\n").encode("utf-8")
        path = raw_dir / f"qwen3.6-27b__{row['test_id']}.json"
        path.write_bytes(data)
        source_bytes[row["test_id"]] = data

    store = LabStore(tmp_path / "lab")
    report = import_legacy_campaign(
        protocol_path=protocol,
        raw_dir=raw_dir,
        store=store,
        experiment_prefix="legacy-test",
    )
    assert report["stored_artifacts"] == 2
    assert report["missing"] == []
    experiment_id = report["experiments"][0]["experiment_id"]
    artifacts = [store.get_run(run_id, experiment_id) for run_id in report["experiments"][0]["run_ids"]]
    by_test = {artifact["provenance"]["environment"]["legacy_test_id"]: artifact for artifact in artifacts}
    for test_id, expected in source_bytes.items():
        artifact = by_test[test_id]
        archived = store.root / artifact["raw"]["relative_path"]
        assert archived.read_bytes() == expected
    second = by_test["chain__r1__t2"]
    assert [message["role"] for message in second["request"]["chat"]] == ["user", "assistant", "user"]

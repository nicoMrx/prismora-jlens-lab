from prismora_lab.canonical import canonical_json_bytes, sha256_json


def test_canonical_hash_ignores_dict_order_but_not_list_order():
    a = {"b": 2, "a": [1, 2]}
    b = {"a": [1, 2], "b": 2}
    c = {"a": [2, 1], "b": 2}
    assert canonical_json_bytes(a) == canonical_json_bytes(b)
    assert sha256_json(a) == sha256_json(b)
    assert sha256_json(a) != sha256_json(c)

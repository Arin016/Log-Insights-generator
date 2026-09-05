import json

from eval.synthetic import case, generate, CATEGORIES, load_case


def test_generator_variety_reproducibility_and_label_separation(tmp_path):
    a=generate(tmp_path/"a",groups=6)
    b=generate(tmp_path/"b",groups=6)
    assert a==b
    group_splits={}
    for item in a["cases"]:
        group_splits.setdefault(item["group_id"],set()).add(item["split"])
        s=load_case(tmp_path/"a",item["case_id"])
        s.verify()
        assert all("expected_claims" not in e.raw_json for e in s.events)
    assert all(len(splits)==1 for splits in group_splits.values())
    assert {item["category"] for item in a["cases"]} == set(CATEGORIES)


def test_paired_surface_and_abstain_labels():
    a,la,_=case(1,0,"positive","development")
    b,lb,_=case(1,0,"missing_source","development")
    assert la["group_id"]==lb["group_id"]
    assert la["expected_terminal"]=="SURFACE_TO_ANALYST"
    assert lb["expected_terminal"]=="HUMAN_REVIEW_REQUIRED"
    assert a["case_id"] != b["case_id"]

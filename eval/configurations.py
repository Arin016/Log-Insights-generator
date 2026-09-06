"""Frozen same-adapter baselines and one-factor harness ablations."""
from core.v2.engine import HarnessConfig
from core.v2.control import Budgets


def configurations():
    v2=HarnessConfig()
    def variant(name,**changes):
        # Validate variants instead of bypassing validation through model_copy.
        return HarnessConfig.model_validate(v2.model_dump()|{"name":name}|changes)
    baseline=dict(graph=False,contradiction=False,semantic=False,selective=False,defenses=False,coverage=False)
    return [
        variant("rules",**baseline,adapter="rules",model="deterministic-correlation-2.0",initial="full",
                representation="raw",drill_down=False,verification="none"),
        variant("naive_single_pass",**baseline,initial="full",representation="raw",drill_down=False,verification="none"),
        variant("scoped_single_pass",**baseline,initial="scoped",representation="legacy_pipe",drill_down=False,verification="none"),
        variant("demo_style_react",**baseline,initial="scoped",representation="legacy_pipe",verification="existence"),
        variant("v2_no_semantic",semantic=False),
        v2,
        *(variant("v2_"+representation,representation=representation) for representation in ("raw","legacy_pipe","pipe","typed_json","typed_edges")),
        variant("v2_no_graph",graph=False),
        variant("v2_no_contradiction",contradiction=False),
        variant("v2_no_selective_triage",selective=False),
        variant("v2_no_injection_defenses",defenses=False),
        variant("v2_no_coverage",coverage=False),
        variant("v2_initial_scope_only",drill_down=False),
        variant("v2_tool_budget_1",budgets=Budgets(tool_calls=1).model_dump()),
        variant("v2_small_context",capsule_rows=2),
    ]

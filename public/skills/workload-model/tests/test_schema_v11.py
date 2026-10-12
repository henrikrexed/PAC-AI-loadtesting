"""§4 v1.1 additive schema bump: G-R1 steps[].request, G-P1 fields[].target.

Pins the renderer-completeness invariant: the v1.1 fields are present and validated,
AND a pre-v1.1 model (no request/target) still validates — the bump is additive.
"""

from __future__ import annotations

import copy
import json
from pathlib import Path

import jsonschema
import pytest

SCRIPTS = Path(__file__).resolve().parent.parent / "scripts"
SCHEMA = json.loads((SCRIPTS / "schema.json").read_text())
ROOT = Path(__file__).resolve().parent.parent.parent  # -> skills/
PRE_V11_MODEL = ROOT / "k6-synthesis" / "test" / "fixtures" / "shop-checkout.workload-model.json"


def _validator():
    jsonschema.Draft7Validator.check_schema(SCHEMA)
    return jsonschema.Draft7Validator(SCHEMA)


def _pre_v11_model():
    return json.loads(PRE_V11_MODEL.read_text())


def test_schema_is_valid_draft7():
    jsonschema.Draft7Validator.check_schema(SCHEMA)


def test_pre_v11_model_still_validates():
    """Back-compat: a model with no `request`/`target` must validate unchanged."""
    model = _pre_v11_model()
    errs = list(_validator().iter_errors(model))
    assert errs == [], [e.message for e in errs]


def test_g_r1_structured_request_validates():
    model = _pre_v11_model()
    model["spec"]["journeys"][0]["steps"][0]["request"] = {
        "method": "GET",
        "pathTemplate": "/api/products",
        "queryParams": {"page": "1"},
        "headers": {"Accept": "application/json"},
    }
    errs = list(_validator().iter_errors(model))
    assert errs == [], [e.message for e in errs]


def test_g_p1_field_target_validates():
    model = _pre_v11_model()
    model["spec"]["payloads"]["checkout"]["fields"][0]["target"] = {"into": "body_field", "as": "email"}
    model["spec"]["payloads"]["checkout"]["fields"][1]["target"] = {"into": "query_param", "as": "cur"}
    errs = list(_validator().iter_errors(model))
    assert errs == [], [e.message for e in errs]


def test_g_r1_bad_method_rejected():
    model = _pre_v11_model()
    model["spec"]["journeys"][0]["steps"][0]["request"] = {"method": "FETCH"}
    errs = list(_validator().iter_errors(model))
    assert len(errs) >= 1


def test_g_p1_bad_target_into_rejected():
    model = _pre_v11_model()
    model["spec"]["payloads"]["checkout"]["fields"][0]["target"] = {"into": "cookie"}
    errs = list(_validator().iter_errors(model))
    assert len(errs) >= 1


def test_g_p1_target_requires_into():
    model = _pre_v11_model()
    model["spec"]["payloads"]["checkout"]["fields"][0]["target"] = {"as": "email"}
    errs = list(_validator().iter_errors(model))
    assert len(errs) >= 1

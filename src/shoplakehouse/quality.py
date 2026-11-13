"""Great Expectations gates on the complete candidate Silver snapshot."""

from __future__ import annotations

import os
from typing import Any

os.environ.setdefault("GX_ANALYTICS_ENABLED", "false")
import great_expectations as gx
import pandas as pd

from .contracts import Table
from .errors import DataQualityError


def validate_snapshot(frame: pd.DataFrame, table: Table) -> dict:
    context = gx.get_context(mode="ephemeral")
    source = context.data_sources.add_pandas(name="candidate")
    asset = source.add_dataframe_asset(name=table.name)
    definition = asset.add_batch_definition_whole_dataframe(name="all_rows")
    batch = definition.get_batch(batch_parameters={"dataframe": frame})
    expectations: list[Any] = [gx.expectations.ExpectColumnValuesToBeUnique(column=table.key)]
    expectations.extend(
        gx.expectations.ExpectColumnValuesToNotBeNull(column=column)
        for column in table.required
        if column in table.silver_columns
    )
    failures = []
    for expectation in expectations:
        result = batch.validate(expectation)
        if not result.success:
            failures.append(expectation.expectation_type)
    summary = {
        "entity": table.name,
        "rows": len(frame),
        "checks": len(expectations),
        "failures": failures,
    }
    if failures:
        raise DataQualityError(f"GX validation failed for {table.name}: {failures}")
    return summary

class PipelineError(RuntimeError):
    """Base exception for an unsuccessful, unpublished pipeline run."""


class DataQualityError(PipelineError):
    """Records or aggregates failed a declared quality gate."""


class SchemaDriftError(PipelineError):
    """The source shape no longer matches a reviewed contract."""


class ConcurrentRunError(PipelineError):
    """Another process owns the pipeline lease."""

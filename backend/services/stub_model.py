"""Small pickleable stub model used in tests.

This class implements `.predict(X)` and returns a constant value so
tests that expect a persisted model can load and run it deterministically.
"""
from typing import Any


class StubModel:
    def predict(self, X: Any):
        # Return a single-element prediction compatible with the codepaths
        # that do `model.predict(features)[0]`.
        return [27.0]

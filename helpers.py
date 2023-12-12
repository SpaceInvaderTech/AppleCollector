"""
Helper functions
"""

# pylint: disable=missing-function-docstring

from itertools import islice


def status_code_success(status_code):
    return 200 <= status_code < 300


def chunks(data, step):
    if isinstance(data, dict):
        data_iterable = iter(data)
        for _ in range(0, len(data), step):
            yield {k: data[k] for k in islice(data_iterable, step)}
    elif isinstance(data, list):
        for i in range(0, len(data), step):
            yield data[i : i + step]

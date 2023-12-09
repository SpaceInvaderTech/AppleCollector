"""
Helper functions
"""

# pylint: disable=missing-function-docstring

from itertools import islice


def status_code_success(status_code):
    return 200 <= status_code < 300


def chunks(data, step):
    data_iterable = iter(data)
    for _ in range(0, len(data), step):
        yield {k: data[k] for k in islice(data_iterable, step)}

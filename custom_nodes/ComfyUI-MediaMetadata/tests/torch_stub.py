"""
Minimal torch stand-in for local testing.

The sandbox's PyPI torch wheel is the CUDA build and cannot import without the
NVIDIA libraries, so the test harness falls back to this stub when the real
torch is unusable. It implements exactly the two operations the node uses
(from_numpy + unsqueeze) plus enough surface for the harness to read the
result back as a numpy array.
"""
import numpy as np


class Tensor:
    def __init__(self, array):
        self._array = np.asarray(array)

    def unsqueeze(self, axis):
        return Tensor(np.expand_dims(self._array, axis))

    def numpy(self):
        return self._array

    def __getitem__(self, item):
        return Tensor(self._array[item])

    @property
    def shape(self):
        return self._array.shape

    def __repr__(self):
        return f"Tensor(shape={self._array.shape})"


def from_numpy(array):
    return Tensor(array)

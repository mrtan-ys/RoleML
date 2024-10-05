""" File-based implementation of CIFAR-10 dataset. """

from collections.abc import Iterable
from pathlib import Path
from typing import Literal, Optional, Union

import numpy as np

from roleml.library.workload.datasets.templates import XYDataset
from roleml.library.workload.datasets.zoo.image.cifar_10.util import unpickle, load_array_from_files

__all__ = ['CiFar10Dataset', 'CiFar10SlicedDataset']


class CiFar10Dataset(XYDataset):

    def __init__(self, root: str, part: Literal['train', 'test'] = 'train', index: Optional[int] = None):
        if part == 'train':
            if index is None:
                files = [f'data_batch_{i}' for i in (1, 2, 3, 4, 5)]
            else:
                files = [f'data_batch_{index}']
        else:
            files = ['test_batch']

        all_data = []
        all_labels = []
        for filename in files:
            data, labels = unpickle(str(Path(root) / filename))
            all_data.append(data.reshape(10000, 32, 32, 3))
            all_labels.extend(labels)

        super().__init__(np.concatenate(all_data), np.array(all_labels))


class CiFar10SlicedDataset(XYDataset):

    def __init__(self, root: str, index: Optional[Union[int, Iterable[int]]] = None):
        if index is None:
            all_indices = range(10)
        else:
            try:
                all_indices = list(index)   # type: ignore
            except TypeError:
                all_indices = [index]
        data_files = [str(Path(root) / f'data_{i}.npy') for i in all_indices]
        label_files = [str(Path(root) / f'labels_{i}.npy') for i in all_indices]

        super().__init__(load_array_from_files(*data_files), load_array_from_files(*label_files))

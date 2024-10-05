import os.path
from pathlib import Path

import numpy as np

from roleml.library.workload.datasets.zoo.image.cifar_10.util import unpickle

__all__ = ['slice_cifar_10_dataset', 'slice_cifar_10_dataset_from_cli']


def slice_cifar_10_dataset(root: str, output_path: str, parts: int = 2):
    overall_index = 0
    part_size = 10000 // parts
    os.makedirs(output_path, exist_ok=True)

    for i in (1, 2, 3, 4, 5):
        filename = str(Path(root) / f'data_batch_{i}')
        data, labels = unpickle(str(Path(root) / filename))
        data = data.reshape(10000, 32, 32, 3)
        for j in range(parts):
            np.save(str(Path(output_path) / f'data_{overall_index}'), data[j * part_size:(j + 1) * part_size])
            np.save(str(Path(output_path) / f'labels_{overall_index}'), labels[j * part_size:(j + 1) * part_size])
            overall_index += 1


def slice_cifar_10_dataset_from_cli():
    import argparse

    parser = argparse.ArgumentParser(description='slice CIFAR-10 training data and save as numpy arrays.')
    parser.add_argument('source', help='source path containing the 5 training data files')
    parser.add_argument('output_path', help='output path to save the slices')
    parser.add_argument('-c', '--count', help='# of slices for each training set, default to 5', type=int, default=5)

    args = parser.parse_args()

    slice_cifar_10_dataset(args.source, args.output_path, parts=args.count)


if __name__ == '__main__':
    slice_cifar_10_dataset_from_cli()

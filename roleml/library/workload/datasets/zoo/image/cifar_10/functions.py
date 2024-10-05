from collections.abc import Iterable
from typing import Union

import numpy as np
import torch
import torchvision.transforms as transforms

from roleml.library.workload.datasets.templates import XYDataset
from roleml.library.workload.datasets.zoo.image.cifar_10.impl import CiFar10Dataset, CiFar10SlicedDataset


def transform_torch(dataset: Union[CiFar10Dataset, CiFar10SlicedDataset]) -> XYDataset:
    transform = transforms.Compose([
        transforms.ToTensor(),
        transforms.Normalize((0.5, 0.5, 0.5), (0.5, 0.5, 0.5))
    ])
    x = [transform(img) for img in dataset.x]
    y = dataset.y
    return XYDataset(x, y)


def combine(data: Iterable):
    data = list(data)
    x = np.array([d[0].numpy() for d in data])
    x = torch.tensor(x)
    y = np.array([d[1] for d in data])
    y = torch.from_numpy(y)
    return x, y

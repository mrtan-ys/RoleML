from pathlib import Path
from typing import Callable, Optional

from torch.utils.data import DataLoader, Subset
from torchvision.datasets import ImageFolder

from roleml.shared.importing import Loadable, load


def _train_dataset(root: str, transform: Optional[Callable] = None) -> ImageFolder:
    return ImageFolder(root=str(Path(root) / "train"), transform=transform)


def _test_dataset(root: str, transform: Optional[Callable] = None) -> ImageFolder:
    return ImageFolder(root=str(Path(root) / "val"), transform=transform)


def slice_train_dataset(root: str, num_slices: int, transform: Optional[Callable] = None) -> list[Subset]:
    full = _train_dataset(root, transform=transform)
    n = len(full) // num_slices
    return [Subset(full, list(range(i * n, (i + 1) * n))) for i in range(num_slices)]


def get_train_loader(
        root: str, region: int, samples_per_region: int, batch_size: int = 32,
        transform: Optional[Loadable[Callable]] = None) -> DataLoader:
    full = _train_dataset(root, load(transform, Callable) if transform else None)
    total = len(full)
    indices = [(region * samples_per_region + i) % total for i in range(samples_per_region)]
    return DataLoader(Subset(full, indices), batch_size=batch_size, drop_last=False)


def get_test_loader(
        root: str, samples: int, batch_size: int = 32,
        transform: Optional[Loadable[Callable]] = None) -> DataLoader:
    full = _test_dataset(root, load(transform, Callable) if transform else None)
    if samples is not None and samples < len(full):
        indices = [i * len(full) // samples for i in range(samples)]
        dataset = Subset(full, indices)
    else:
        dataset = full
    return DataLoader(dataset, batch_size=batch_size, drop_last=False)


# class-like shortcuts

ImageNet100TrainDataset = get_train_loader
ImageNet100TestDataset = get_test_loader

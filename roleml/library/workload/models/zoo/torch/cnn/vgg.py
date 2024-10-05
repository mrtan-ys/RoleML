"""
Modified from: https://en.d2l.ai/chapter_convolutional-modern/vgg.html

Reference:
Zhang, A., Lipton, Z. C., Li, M., & Smola, A. J. (2023). Dive into Deep Learning. Cambridge University Press.
"""

from collections.abc import Sequence
from typing import Literal

from torch import nn, optim

from roleml.library.workload.models.templates.torch.classification import SimpleTorchXYModel

__all__ = ['VGGModel', 'VGGLiteModel']


def vgg_block(num_convs: int, in_channels: int, out_channels: int) -> nn.Sequential:
    layers = []
    for _ in range(num_convs):
        layers.append(nn.Conv2d(in_channels, out_channels, kernel_size=3, padding=1))
        layers.append(nn.ReLU())
        in_channels = out_channels
    layers.append(nn.MaxPool2d(kernel_size=2, stride=2))
    return nn.Sequential(*layers)


VGGArchType = Literal['VGG11', 'VGG16', 'VGG19']

vgg_arch: dict[VGGArchType, Sequence[tuple[int, int]]] = {
    'VGG11': ((1, 64), (1, 128), (2, 256), (2, 512), (2, 512)),
    'VGG16': ((2, 64), (2, 128), (3, 256), (3, 512), (3, 512)),
    'VGG19': ((2, 64), (2, 128), (4, 256), (4, 512), (4, 512)),
}


def vgg(*, in_channels: int = 1,
        conv_arch: Sequence[tuple[int, int]] = ((1, 64), (1, 128), (2, 256), (2, 512), (2, 512))) -> nn.Sequential:
    # TODO currently for 112x112 only; add image size as arg to automatically-detect linear size
    conv_blks = []
    for (num_convs, out_channels) in conv_arch:
        conv_blks.append(vgg_block(num_convs, in_channels, out_channels))
        in_channels = out_channels

    return nn.Sequential(
        *conv_blks, nn.Flatten(),
        nn.Linear(out_channels * 7 * 7, 4096), nn.ReLU(), nn.Dropout(0.5),  # type: ignore
        nn.Linear(4096, 4096), nn.ReLU(), nn.Dropout(0.5),
        nn.Linear(512, 10))


def vgg_lite(*, in_channels: int = 1,
             conv_arch: Sequence[tuple[int, int]] = ((1, 64), (1, 128), (2, 256), (2, 512), (2, 512))) -> nn.Sequential:
    conv_blks = []
    for (num_convs, out_channels) in conv_arch:
        conv_blks.append(vgg_block(num_convs, in_channels, out_channels))
        in_channels = out_channels

    return nn.Sequential(
        *conv_blks, nn.Flatten(),
        nn.Linear(512, 10))


class VGGModel(SimpleTorchXYModel):

    vgg_maker = vgg

    def build_model(self, type: VGGArchType = 'VGG11', in_channels: int = 1, lr: float = 0.01, **_) \
            -> tuple[nn.Module, optim.Optimizer, nn.Module]:
        try:
            module = self.__class__.vgg_maker(in_channels=in_channels, conv_arch=vgg_arch[type])
        except KeyError:
            raise ValueError(f'unsupported VGG type f{type}') from None
        optimizer = optim.Adam(module.parameters(), lr=lr)
        criterion = nn.CrossEntropyLoss()
        return module, optimizer, criterion


class VGGLiteModel(VGGModel):

    vgg_maker = vgg_lite

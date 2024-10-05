from collections.abc import Mapping
from typing import Any

import torch
import torch.nn as nn


def split_gradients(local_gradients: torch.Tensor, num_blocks: int):
    total_size = local_gradients.numel()
    block_size = total_size // num_blocks
    remainder = total_size % num_blocks
    blocks = []
    start_index = 0
    for i in range(num_blocks):
        end_index = start_index + block_size + (1 if i < remainder else 0)
        blocks.append(local_gradients[start_index:end_index])
        start_index = end_index
    return blocks


def he_initialization(state_dict: Mapping[str, Any]):
    for name, param in state_dict.items():
        if 'weight' in name:
            if 'conv' in name or 'fc' in name:
                nn.init.kaiming_uniform_(param, nonlinearity='relu')
        elif 'bias' in name:
            nn.init.zeros_(param)

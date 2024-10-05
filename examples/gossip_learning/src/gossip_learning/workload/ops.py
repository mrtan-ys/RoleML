import torch


def torch_params_averager(data_1, data_2, count: int = 2):
    return {k: torch.div(torch.add(data_1[k], data_2[k]), count) for k in data_1}


def drop_local(data_1, data_2, count: int = 2):     # noqa: signature fixed
    return data_2

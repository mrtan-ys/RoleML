from .random import RandomOneOffIndexSampler, RandomReplaceIndexSampler
from .sequential import SequentialOneOffIndexSampler, SequentialCycleIndexSampler


BUILTIN_SAMPLERS = {
    'sequential': SequentialOneOffIndexSampler,
    'sequential-oneoff': SequentialOneOffIndexSampler,
    'sequential-cycle': SequentialCycleIndexSampler,
    'random': RandomReplaceIndexSampler,
    'random-oneoff': RandomOneOffIndexSampler,
    'random-replace': RandomReplaceIndexSampler,
}

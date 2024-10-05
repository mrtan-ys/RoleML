from typing import Optional

from roleml.library.workload.datasets.bases import DataStreams


def train(model, dataset_train: DataStreams, dataset_test: Optional[DataStreams] = None, *, num_epochs: int = 10):
    for i in range(num_epochs):
        stats = model.train(dataset_train)
        print(f'epoch {i} stats', stats)
        if dataset_test:
            test_result = model.test(dataset_test)
            print(f'epoch {i} test result', test_result)

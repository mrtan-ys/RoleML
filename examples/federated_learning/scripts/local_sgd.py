import os
import sys
source_abs = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), 'src')
sys.path.append(source_abs)


def local_sgd(*, num_epochs: int, test: bool, num_threads: int, simulate_update: bool, add_pauses: bool):
    import io
    import time
    if simulate_update:
        import pickle
    else:
        pickle = None

    print(time.asctime(), 'start model loading')
    from federated_learning.workload.lenet_5 import MyLeNet5RGBModel
    model = MyLeNet5RGBModel(optimizer='sgd', lr=0.01, num_threads=num_threads)
    if add_pauses:
        time.sleep(5)

    print(time.asctime(), 'start train dataset loading')
    # RoleML core components not loaded
    from roleml.library.workload.datasets.views import DatasetViewFactory
    from roleml.library.workload.datasets.samplers import SequentialOneOffIndexSampler
    from roleml.library.workload.datasets.zoo.image.cifar_10.functions import transform_torch, combine
    from federated_learning.workload.cifar_10 import MyCiFar10SlicedDataset
    view_factory = DatasetViewFactory
    dataset_view = view_factory(
        MyCiFar10SlicedDataset(root='/home/roleml/datasets/cifar-10/sliced', index=0),
        converters=[transform_torch],
        batch_size=32, drop_last=False, combiner=combine)
    if add_pauses:
        time.sleep(5)

    if test:
        print(time.asctime(), 'start test dataset loading')
        from federated_learning.workload.cifar_10 import MyCiFar10Dataset
        model_test = model
        dataset_test_view = view_factory(
            MyCiFar10Dataset(root='/home/roleml/datasets/cifar-10', part='test'),
            converters=[transform_torch],
            sampler=SequentialOneOffIndexSampler, combiner=combine
        )
        if add_pauses:
            time.sleep(5)
    else:
        model_test = None
        dataset_test_view = None

    time.sleep(0.25)
    print(time.asctime(), 'start training')
    for i in range(num_epochs):
        result = model.train(dataset_view)
        print(time.asctime(), f'epoch result of {i}', result)
        if simulate_update:
            assert pickle is not None
            params = model.get_params()
            file = io.BytesIO(pickle.dumps(params))
            params = pickle.load(file)
            if test:
                assert model_test is not None
                model_test.set_params(params)
            else:
                model.set_params(params)
        else:
            file = None
        if test:
            assert model_test is not None and dataset_test_view is not None
            test_result = model_test.test(dataset_test_view)
            print(time.asctime(), f'test result of {i}', test_result)
        if simulate_update:
            assert file is not None
            file.close()
            del file
            print(time.asctime(), 'simulated parameter update')


if __name__ == '__main__':
    import argparse
    import os
    import time

    parser = argparse.ArgumentParser()
    parser.add_argument('-r', '--resource', action='store_true', help='monitor resource usage')
    parser.add_argument('-t', '--temperature', action='store_true', help='monitor temperature on Raspberry Pi')
    parser.add_argument('-p', '--add-pauses', action='store_true', help='add pauses upon completion of each stage')
    parser.add_argument('-n', '--num-epochs', type=int, help='number of training epochs', default=5)
    parser.add_argument('-d', '--num-threads', type=int, help='number of threads for training and testing', default=1)
    parser.add_argument('-T', '--test', action='store_true', help='test the model after each training epoch')
    parser.add_argument(
        '-s', '--simulate-update', action='store_true',
        help='simulate parameter update using serialization and deserialization')
    args = parser.parse_args()

    current_dir = os.path.dirname(os.path.abspath(__file__))

    # RoleML core components not loaded

    if args.resource:
        from roleml.scripts.runner.recipes.measurement.resource.run import ResourceMeasurementSession
        resource_session = ResourceMeasurementSession(f'{current_dir}/resource.log', 'local SGD')
        resource_session.begin(0)
    else:
        resource_session = None
    
    if args.temperature:
        from roleml.scripts.runner.recipes.measurement.temperature_rpi.run import RPITemperatureMeasurementSession
        rpi_temperature_session = RPITemperatureMeasurementSession(f'{current_dir}/temperature_rpi.log', 'local SGD')
        rpi_temperature_session.begin(0)
    else:
        rpi_temperature_session = None

    if resource_session or rpi_temperature_session:
        print(f'Please wait for 10s while measuring initial state...')
        time.sleep(10)
    print(time.asctime(), 'starting')

    try:
        local_sgd(
            num_epochs=args.num_epochs, test=args.test, num_threads=args.num_threads,
            simulate_update=args.simulate_update, add_pauses=args.add_pauses)
    finally:
        if resource_session:
            resource_session.end()
        if rpi_temperature_session:
            rpi_temperature_session.end()

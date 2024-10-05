import pickle

import numpy as np


def unpickle(file):
    with open(file, 'rb') as fo:
        content = pickle.load(fo, encoding='bytes')
    return content[b'data'], content[b'labels']


def load_array_from_files(*files):
    """ Load array from one or more files (and concatenate into one). """
    list_of_data = [np.load(file) for file in files]
    return np.concatenate(list_of_data)

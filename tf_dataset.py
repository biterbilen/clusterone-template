import multiprocessing
import logging
import tensorflow as tf
from tensorflow.contrib.data import TextLineDataset
from tensorflow.contrib.data import Dataset
from tensorflow.python.framework.errors_impl import OutOfRangeError


class TFDataSet(object):
    """Abstract class that helps to work with TensorFlow Datasets"""

    def __init__(self, name, data_files_pattern, dataset_class=TextLineDataset,
                 min_queue_examples=0, shuffle_size=None):
        """
        :param name: name of the dataset.
        :param str data_files_pattern: pattern of the data files
        :param Dataset dataset_class: class to create the dataset with the files. By default is
        TextLineDataset
        :param int min_queue_examples: minimum number of examples to queue, this value should be
        proportional to the ram of the computer. By default is 0
        :param int shuffle_size: size of the buffer for shuffling, this value should be
        proportional to the ram of the computer
        """
        self.name = name
        self.data_files_pattern = data_files_pattern
        self.dataset_class = dataset_class
        self.min_queue_examples = min_queue_examples
        self.shuffle_size = shuffle_size

    def read(self, batch_size, num_epochs=1, shuffle=False, task_spec=None):
        """
        Reads the data and return a tuple of (inputs,outputs)
        :param batch_size: the batch size of the returned inputs/outputs
        :param num_epochs: the number of epochs to read the dataset
        :param shuffle: whether to shuffle the data or not
        :param task_spec: the task spec of the training. I will help to know whether it is
        distributed training or not
        :return: The result of calling dataset.make_one_shot_iterator().get_next()
        """
        # create the dataset of files with the data
        dataset = Dataset.list_files(self.data_files_pattern)
        # set the number of epochs
        dataset = dataset.repeat(num_epochs)
        if shuffle:
            # read one sample per file
            dataset = dataset.interleave(self.dataset_class,
                                         # number of readers the same as number of CPUs
                                         cycle_length=multiprocessing.cpu_count() + 1,
                                         # block size is 1 to get directly a flat map
                                         block_length=1)
        else:
            # reads files sequentially
            files = []
            filename = dataset.make_one_shot_iterator().get_next()
            try:
                with tf.Session() as sess:
                    while True:
                        d = sess.run(filename)
                        files.append(d)
            except OutOfRangeError:
                pass
            dataset = self.dataset_class(files)

        if task_spec and task_spec.num_workers > 1:
            # split the dataset in shards
            # TODO in TF 1.4 use: dataset = dataset.shard(task_spec.num_workers, task_spec.index)
            from tensorflow.python.ops import math_ops

            def filter_fn(elem_index, _):
                mod_result = math_ops.mod(elem_index, task_spec.num_workers)
                return math_ops.equal(mod_result, task_spec.index)

            dataset = dataset.enumerate().filter(filter_fn).map(lambda _, elem: elem)

        if shuffle:
            # shuffle the samples
            if self.shuffle_size is None:
                raise ValueError('shuffle_size has not been set')
            dataset = dataset.shuffle(buffer_size=self.shuffle_size)

        # process each example
        dataset = dataset.map(self._map,
                              # use as many threads as CPUs + 1
                              # TODO in TF 1.4 use: num_parallel_calls=multiprocessing.cpu_count() + 1,
                              num_threads=multiprocessing.cpu_count() + 1,
                              # buffer the data as CPUs * batch_size + minimum_size
                              output_buffer_size=batch_size * multiprocessing.cpu_count() +
                                                 self.min_queue_examples)
        dataset = dataset.batch(batch_size)
        return dataset.make_one_shot_iterator().get_next()

    def _map(self, example_serialized):
        """
        Maps a example_serialized read from the dataset into the final set of tf.Tensors
        to return to the model.

        Simple example:

        def _parse(line):
            a, b = [np.int32(x) for x in line.split()]
            return a, b

        t_input, t_ouptut = tf.py_func(_parse, [line], [tf.int32, tf.int32],
                                       stateful=True, name='py_parse_example')
        t_ouptut = tf.add(t_ouptut, 1)

        return t_input, t_ouptut

        :param example_serialized: the example serialized
        :return: a tuple of the tensors to return when get_next is called. Usually (inputs,outputs)
        """
        raise NotImplementedError('Should have implemented this')

    def _count_num_records(self):
        """
        Counts the number of non-empty lines (the data samples) from the data_files. This function
        is called from get_size the first time.
        :return int: the number of non-empty lines in the data_files
        """
        size = 0
        dataset = Dataset.list_files(self.data_files_pattern).repeat(1)
        dataset = self.dataset_class(dataset).repeat(1)
        samples = 0
        try:
            next_element = dataset.make_one_shot_iterator().get_next()
            with tf.Session() as sess:
                while True:
                    sess.run(next_element)
                    samples += 1
        except:
            pass
        return samples

    def get_size(self):
        if self._size is None:
            self._size = self._count_num_records()
        return self._size

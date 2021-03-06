# -*- coding: utf-8 -*-

'''This module contains recurrent network structures.'''

import collections
import numpy as np
import re
import sys
import theano.tensor as TT

from . import feedforward


def batches(arrays, steps=100, batch_size=64, rng=None):
    '''Return a callable that generates samples from a dataset.

    Parameters
    ----------
    arrays : list of ndarray (time-steps, data-dimensions)
        Arrays of data. Rows in these arrays are assumed to correspond to time
        steps, and columns to variables. Multiple arrays can be given; in such
        a case, these arrays usually correspond to [input, output]---for
        example, for a recurrent regression problem---or [input, output,
        weights]---for a weighted regression or classification problem.
    steps : int, optional
        Generate samples of this many time steps. Defaults to 100.
    batch_size : int, optional
        Generate this many samples per call. Defaults to 64. This must match the
        batch_size parameter that was used when creating the recurrent network
        that will process the data.
    rng : :class:`numpy.random.RandomState` or int, optional
        A random number generator, or an integer seed for a random number
        generator. If not provided, the random number generator will be created
        with an automatically chosen seed.

    Returns
    -------
    callable :
        A callable that can be used inside a dataset for training a recurrent
        network.
    '''
    assert batch_size >= 2, 'batch_size must be at least 2!'
    assert isinstance(arrays, (tuple, list)), 'arrays must be a tuple or list!'

    if rng is None or isinstance(rng, int):
        rng = np.random.RandomState(rng)

    def sample():
        xs = [np.zeros((batch_size, steps, a.shape[1]), a.dtype) for a in arrays]
        for i in range(batch_size):
            j = rng.randint(len(arrays[0]) - steps)
            for x, a in zip(xs, arrays):
                x[i] = a[j:j+steps]
        return xs

    return sample


class Text(object):
    '''A class for handling sequential text data.

    Parameters
    ----------
    text : str
        A blob of text.
    alpha : str, optional
        An alphabet to use for representing characters in the text. If not
        provided, all characters from the text occurring at least ``min_count``
        times will be used.
    min_count : int, optional
        If the alphabet is to be computed from the text, discard characters that
        occur fewer than this number of times. Defaults to 2.
    unknown : str, optional
        A character to use to represent "out-of-alphabet" characters in the
        text. This must not be in the alphabet. Defaults to '\0'.

    Attributes
    ----------
    text : str
        A blob of text, with all non-alphabet characters replaced by the
        "unknown" character.
    alpha : str
        A string containing each character in the alphabet.
    '''

    def __init__(self, text, alpha=None, min_count=2, unknown='\0'):
        self.alpha = alpha
        if self.alpha is None:
            self.alpha = ''.join(sorted(set(
                char for char, count in
                collections.Counter(text).items()
                if char != unknown and count >= min_count)))
        self.text = re.sub(r'[^{}]'.format(re.escape(self.alpha)), unknown, text)
        assert unknown not in self.alpha
        self._rev_index = unknown + self.alpha
        self._fwd_index = dict(zip(self._rev_index, range(1 + len(self.alpha))))

    def encode(self, txt):
        '''Encode a text string by replacing characters with alphabet index.

        Parameters
        ----------
        txt : str
            A string to encode.

        Returns
        -------
        classes : list of int
            A sequence of alphabet index values corresponding to the given text.
        '''
        return list(self._fwd_index.get(c, 0) for c in txt)

    def decode(self, enc):
        '''Encode a text string by replacing characters with alphabet index.

        Parameters
        ----------
        classes : list of int
            A sequence of alphabet index values to convert to text.

        Returns
        -------
        txt : str
            A string containing corresponding characters from the alphabet.
        '''
        return ''.join(self._rev_index[c] for c in enc)

    def classifier_batches(self, steps, batch_size, rng=None):
        '''Create a callable that returns a batch of training data.

        Parameters
        ----------
        steps : int
            Number of time steps in each batch.
        batch_size : int
            Number of training examples per batch.
        rng : :class:`numpy.random.RandomState` or int, optional
            A random number generator, or an integer seed for a random number
            generator. If not provided, the random number generator will be
            created with an automatically chosen seed.

        Returns
        -------
        batch : callable
            A callable that, when called, returns a batch of data that can be
            used to train a classifier model.
        '''
        assert batch_size >= 2, 'batch_size must be at least 2!'

        if rng is None or isinstance(rng, int):
            rng = np.random.RandomState(rng)

        T = np.arange(steps)

        def batch():
            inputs = np.zeros((batch_size, steps, 1 + len(self.alpha)), 'f')
            outputs = np.zeros((batch_size, steps), 'i')
            for b in range(batch_size):
                offset = rng.randint(len(self.text) - steps - 1)
                enc = self.encode(self.text[offset:offset + steps + 1])
                inputs[b, T, enc[:-1]] = 1
                outputs[b, T] = enc[1:]
            return [inputs, outputs]

        return batch


class Autoencoder(feedforward.Autoencoder):
    '''An autoencoder network attempts to reproduce its input.

    Notes
    =====

    A recurrent autoencoder model requires the following inputs during training:

    - ``x``: A three-dimensional array of input data. Each element of axis 0 of
      ``x`` is expected to be one sample in a minibatch. Each element of axis 1
      of ``x`` represents a moment of time. Each element of axis 2 of ``x``
      represents the measurements of a particular input variable across all
      times and all data items.
    '''

    def __init__(self, layers=(), loss='mse', weighted=False):
        super(feedforward.Autoencoder, self).__init__(
            layers=layers, loss=loss, in_dim=3, weighted=weighted)


class Regressor(feedforward.Regressor):
    '''A regressor attempts to produce a target output.

    Notes
    =====

    A recurrent regression model takes the following inputs:

    - ``x``: A three-dimensional array of input data. Each element of axis 0 of
      ``x`` is expected to be one moment in time. Each element of axis 1 of
      ``x`` holds a single sample from a batch of data. Each element of axis 2
      of ``x`` represents the measurements of a particular input variable across
      all times and all data items.

    - ``targets``: A three-dimensional array of target output data. Each element
      of axis 0 of ``targets`` is expected to be one moment in time. Each
      element of axis 1 of ``targets`` holds a single sample from a batch of
      data. Each element of axis 2 of ``targets`` represents the measurements of
      a particular output variable across all times and all data items.
    '''

    def __init__(self, layers=(), loss='mse', weighted=False):
        super(feedforward.Regressor, self).__init__(
            layers=layers, loss=loss, in_dim=3, out_dim=3, weighted=weighted)


class Classifier(feedforward.Classifier):
    '''A classifier attempts to match a 1-hot target output.

    Notes
    =====

    Unlike a feedforward classifier, where the target labels are provided as a
    single vector, a recurrent classifier requires a vector of target labels for
    each time step in the input data. So a recurrent classifier model requires
    the following inputs for training:

    - ``x``: A three-dimensional array of input data. Each element of axis 0 of
      ``x`` is expected to be one moment in time. Each element of axis 1 of
      ``x`` holds a single sample in a batch of data. Each element of axis 2 of
      ``x`` represents the measurements of a particular input variable across
      all times and all data items in a batch.

    - ``labels``: A two-dimensional array of integer target labels. Each element
      of ``labels`` is expected to be the class index for a single batch item.
      Axis 0 of this array represents time, and axis 1 represents data samples
      in a batch.
    '''

    def __init__(self, layers=(), loss='xe', weighted=False):
        super(feedforward.Classifier, self).__init__(
            layers=layers, loss=loss, in_dim=3, out_dim=2, weighted=weighted)

    def predict_sequence(self, labels, steps, streams=1, rng=None):
        '''Draw a sequential sample of class labels from this network.

        Parameters
        ----------
        labels : list of int
            A list of integer class labels to get the classifier started.
        steps : int
            The number of time steps to sample.
        streams : int, optional
            Number of parallel streams to sample from the model. Defaults to 1.
        rng : :class:`numpy.random.RandomState` or int, optional
            A random number generator, or an integer seed for a random number
            generator. If not provided, the random number generator will be
            created with an automatically chosen seed.

        Yields
        ------
        label(s) : int or list of int
            Yields at each time step an integer class label sampled sequentially
            from the model. If the number of requested streams is greater than
            1, this will be a list containing the corresponding number of class
            labels.
        '''
        if rng is None or isinstance(rng, int):
            rng = np.random.RandomState(rng)
        offset = len(labels)
        batch = max(2, streams)
        inputs = np.zeros((batch, offset + steps, self.layers[0].size), 'f')
        inputs[:, np.arange(offset), labels] = 1
        for i in range(offset, offset + steps):
            chars = []
            for pdf in self.predict_proba(inputs[:i])[:, -1]:
                try:
                    c = rng.multinomial(1, pdf).argmax(axis=-1)
                except ValueError:
                    # sometimes the pdf triggers a normalization error. just
                    # choose greedily in this case.
                    c = pdf.argmax(axis=-1)
                chars.append(int(c))
            inputs[np.arange(batch), i, chars] = 1
            yield chars[0] if streams == 1 else chars

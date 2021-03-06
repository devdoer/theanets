'''This package groups together a bunch of Theano code for neural nets.'''

from .activations import Activation
from .feedforward import Autoencoder, Regressor, Classifier
from .graph import Network
from .layers import Layer
from .losses import Loss
from .main import Experiment

from . import recurrent

__version__ = '0.7.0pre'

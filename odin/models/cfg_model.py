"""
.. module:: config
    :synopsis: Module for configuration of the project, mainly which neuron model is used

.. moduleauthor:: Marc Javin
"""

from .celeg import CElegansNeuron
from .leakint import LeakyIntegrate
from .hhsimple import HodgHuxSimple

NEURON_MODEL = HodgHuxSimple
"""Class used for biological neuron models"""

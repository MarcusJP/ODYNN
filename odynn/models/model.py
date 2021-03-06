"""
.. module:: cls
    :synopsis: Module containing basic cls abstract class

.. moduleauthor:: Marc Javin
"""

import pylab as plt
from cycler import cycler
from abc import ABC, abstractmethod
import numpy as np
from odynn import utils
from odynn.utils import classproperty
import tensorflow as tf
import scipy as sp


class Neuron(ABC):
    V_pos = 0
    """int, Default position of the voltage in state vectors"""
    _ions = {}
    """dictionnary, name of ions in the vector states and their positions"""
    default_init_state = None
    """array, Initial values for the vector of state variables"""

    def __init__(self, dt=0.1):
        self.dt = dt
        self._init_state = self.default_init_state

    @property
    def num(self):
        """int, Number of neurons being modeled in this object"""
        return self._num

    @property
    def init_state(self):
        """ndarray, Initial state vector"""
        return self._init_state

    @classproperty
    def ions(self):
        """dict, contains the names of modeled ion concentrations as keys and their position in init_state as values"""
        return self._ions

    @abstractmethod
    def step(self, X, i):
        """
        Integrate and update state variable (voltage and possibly others) after one time step

        Args:
          X(ndarray): State variables
          i(float): Input current

        Returns:
            ndarray: updated state vector

        """
        pass

    @classmethod
    def plot_output(cls, ts, i_inj, states, y_states=None, suffix="", show=True, save=False, l=1, lt=1,
                    targstyle='-'):
        """
        Plot voltage and ion concentrations, potentially compared to a target model

        Args:
          ts(ndarray of dimension [time]): time steps of the measurements
          i_inj(ndarray of dimension [time]): input current
          states(ndarray of dimension [time, state_var, nb_neuron]):
          y_states(list of ndarray [time, nb_neuron], optional): list of values for the target model, each element is an
            ndarray containing the recordings of one state variable (Default value = None)
          suffix(str): suffix for the name of the saved file (Default value = "")
          show(bool): If True, show the figure (Default value = True)
          save(bool): If True, save the figure (Default value = False)
          l(float): width of the main lines (Default value = 1)
          lt(float): width of the target lines (Default value = 1)
          targstyle(str): style of the target lines (Default value = '-')

        """

        plt.figure()
        nb_plots = len(cls._ions) + 2
        custom_cycler = None
        if (states.ndim > 3): # circuit in parallel
            states = np.reshape(np.swapaxes(states,-2,-1), (states.shape[0], states.shape[1], -1))
            custom_cycler = cycler('color', utils.COLORS.repeat(y_states[cls.V_pos].shape[1]))
            y_states = [np.reshape(y, (y.shape[0], -1)) if y is not None else None for y in y_states]

        # Plot voltage
        p = plt.subplot(nb_plots, 1, 1)
        if custom_cycler is not None:
            p.set_prop_cycle(custom_cycler)
        plt.plot(ts, states[:, cls.V_pos], linewidth=l)
        if y_states is not None:
            if y_states[cls.V_pos] is not None:
                plt.plot(ts, y_states[cls.V_pos], 'r', linestyle=targstyle, linewidth=lt, label='target model')
                plt.legend()
        plt.ylabel('Voltage (mV)')

        for i, (ion, pos) in enumerate(cls._ions.items()):
            p = plt.subplot(nb_plots, 1, 2+i)
            if custom_cycler is not None:
                p.set_prop_cycle(custom_cycler)
            plt.plot(ts, states[:, pos], linewidth=l)
            if y_states is not None:
                if y_states[pos] is not None:
                    plt.plot(ts, y_states[pos], 'r', linestyle=targstyle, linewidth=lt, label='target model')
                    plt.legend()
            plt.ylabel('[{}]'.format(ion))

        plt.subplot(nb_plots, 1, nb_plots)
        plt.plot(ts, i_inj, 'b')
        plt.xlabel('t (ms)')
        plt.ylabel('$I_{inj}$ ($\\mu{A}/cm^2$)')

        utils.save_show(show, save, utils.IMG_DIR + 'output_%s' % suffix)

    @abstractmethod
    def calculate(self, i):
        """Iterate over i (current) and return the state variables obtained after each step

        Args:
          i(ndarray): input current, dimension [time, (batch, (self.num))]

        Returns:
            ndarray: state vectors concatenated [i.shape[0], len(self.init_state)(, i.shape[1], (i.shape[2]))]
        """
        pass



class BioNeuron(Neuron):
    """Abstract class to implement for using a new biological model
    All methods and class variables have to be implemented in order to have the expected behavior

    """
    default_params = None
    """dict, Default set of parameters for the model, of the form {<param_name> : value}"""
    parameter_names = None
    """names of parameters from the model"""
    _constraints_dic = None
    """dict, Constraints to be applied during optimization
        Should be of the form : {<variable_name> : [lower_bound, upper_bound]}
    """

    def __new__(cls, *args, **kwargs):
        obj = Neuron.__new__(cls)
        obj._init_names()
        return obj

    def __init__(self, init_p=None, tensors=False, dt=0.1):
        """
        Reshape the initial state and parameters for parallelization in case init_p is a list

        Args:
            init_p(dict or list of dict): initial parameters of the neuron(s). If init_p is a list, then this object
                will model n = len(init_p) neurons
            tensors(bool): used in the step function in order to use tensorflow or numpy
            dt(float): time step

        """
        Neuron.__init__(self, dt=dt)
        if(init_p is None):
            init_p = self.default_params
            self._num = 1
        elif(init_p == 'random'):
            init_p = self.get_random()
            self._num = 1
        elif isinstance(init_p, list):
            self._num = len(init_p)
            if self._num == 1:
                init_p = init_p[0]
            else:
                init_p = {var: np.array([p[var] for p in init_p], dtype=np.float32) for var in init_p[0].keys()}
        elif hasattr(init_p[self.parameter_names[0]], '__len__'):
            self._num = len(init_p[self.parameter_names[0]])
            init_p = {var: np.array(val, dtype=np.float32) for var, val in init_p.items()}
        else:
            self._num = 1
        if self._num > 1:
            self._init_state = np.stack([self._init_state for _ in range(self._num)], axis=-1)
        self._tensors = tensors
        self._init_p = init_p
        self._param = self._init_p.copy()
        self.dt = dt

    def _inf(self, V, rate):
        """Compute the steady state value of a gate activation rate"""
        mdp = self._param['%s__mdp' % rate]
        scale = self._param['%s__scale' % rate]
        if self._tensors:
            return tf.sigmoid((V - mdp) / scale)
        else:
            return 1 / (1 + sp.exp((mdp - V) / scale))

    def _update_gate(self, rate, name, V):
        tau = self._param['%s__tau'%name]
        return ((tau * self.dt) / (tau + self.dt)) * ((rate / self.dt) + (self._inf(V, name) / tau))

    def calculate(self, i_inj):
        """
        Simulate the neuron with input current `i_inj` and return the state vectors

        Args:
            i_inj: input currents of shape [time, batch]

        Returns:
            ndarray: series of state vectors of shape [time, state, batch]

        """
        X = [self._init_state]
        for i in i_inj:
            X.append(self.step(X[-1], i))
        return np.array(X[1:])

    @classmethod
    def _init_names(cls):
        cls.parameter_names = list(cls.default_params.keys())

    @staticmethod
    def get_random():
        """Return a dictionnary with the same keys as default_params and random values"""
        pass

    @staticmethod
    def plot_results(*args, **kwargs):
        """Function for plotting detailed results of some experiment"""
        pass

    def parallelize(self, n):
        """Add a dimension of size n in the initial parameters and initial state

        Args:
          n(int): size of the new dimension
        """
        if self._num > 1 and list(self._init_p.values())[0].ndim == 1:
                self._init_p = {var: np.stack([val for _ in range(n)], axis=val.ndim) for var, val in self._init_p.items()}
        elif not hasattr(list(self._init_p.values())[0], '__len__'):
                self._init_p = {var: np.stack([val for _ in range(n)], axis=-1) for var, val in self._init_p.items()}
        self._init_state = np.stack([self._init_state for _ in range(n)], axis=-1)
        self._param = self._init_p.copy()

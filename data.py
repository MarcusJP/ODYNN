from statsmodels.nonparametric.smoothers_lowess import lowess
from scipy.interpolate import interp1d, splrep, splev
from scipy.signal import savgol_filter
import numpy as np
import pandas as pd
import pylab as plt
import time
import pickle
import math
from matplotlib.ticker import FormatStrFormatter

DUMP_FILE = 'data/dump'
FILE_LV = 'tmp/dump_lossratevars'
plt.rc('ytick', labelsize=8)    # fontsize of the tick labels


def get_data_dump(file=DUMP_FILE):
    with open(file, 'rb') as f:
        T, X, V, Ca = pickle.load(f)
    return T, X, V, Ca

def get_data_dump2(file=DUMP_FILE):
    with open(file, 'rb') as f:
        T, X, Ca = pickle.load(f)
    return T, X, Ca

def check_alpha(tinit, i, trace):
    vals = np.logspace(math.log10(0.1), math.log10(100.), num=20)
    idx=0
    plt.subplot(211)
    plt.plot(trace)
    spl = splrep(tinit, trace, s=0.5)
    trace = splev(tinit, spl)
    plt.plot(trace)
    plt.subplot(212)
    plt.plot(i)
    plt.show()
    for alpha in vals:
        idx += 1
        k = 189.e-6
        n = 3.8
        bas = (-k*trace) / (trace - np.full(trace.shape, alpha))
        cac = np.power(bas, n)
        plt.subplot(len(vals)/4, 4, idx)
        plt.plot(cac, label='alpha=%.2f'%alpha)
        z2 = savgol_filter(cac, 9, 3)
        plt.plot(z2, 'r', label='smooth')
        plt.legend()
    plt.show()

if __name__ == '__main__':
    dt = pd.read_csv('data/AVAL1.csv')
    dt = dt.head(400)
    trace = np.array(dt['trace'])
    i = np.array(dt['inputCurrent'])*10
    tinit = np.array(dt['timeVector'])*1000
    t = np.arange(0,tinit[-1],step=1)


    check_alpha(tinit, i, trace)
    exit(0)


    t1 = time.time()
    l = lowess(trace, tinit, return_sorted=False, frac=0.01)

    f = interp1d(tinit, l, kind='cubic')
    z = f(t)
    t2 = time.time()
    print('lowess+interp : %s'%(t2-t1))

    t1 = time.time()
    exact = splrep(tinit, trace, k=1)
    spl = splrep(tinit, trace, s=0.5)
    zexact = splev(t, exact)
    z2 = splev(t, spl)
    t2 = time.time()
    print('splrep : %s' % (t2-t1))

    spli = splrep(tinit, i, k=2)
    i = splev(t, spli)

    # plt.subplot(211)
    # plt.plot(trace)
    # plt.plot(l)
    # plt.subplot(212)
    plt.plot(z, 'g', label='lowess+interp1d')
    plt.plot(z2, 'b', label='splrev')
    plt.plot(zexact, 'r', label='exact')
    plt.legend()
    plt.show()

    pickle.dump([t, i, z2], open(DUMP_FILE, 'wb'))
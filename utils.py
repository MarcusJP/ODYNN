import pylab as plt

RATE_COLORS = {'p' : '#00ccff',
               'q' : '#0000ff',
               'n' : '#cc00ff',
               'e' : '#b30000',
               'f' : '#ff9900',
               'h' : '#ff1a1a'
                }

def plots_output(ts, i_inj, cac_lum, y_cac_lum, suffix="", show=True, save=False):
    plt.figure()

    plt.subplot(3, 1, 1)
    plt.plot(ts, cac_lum, 'r')
    plt.ylabel('Ca2+ concentration predicted')

    plt.subplot(3, 1, 2)
    plt.plot(ts, y_cac_lum, 'r')
    plt.ylabel('Ca2+ concentration true')

    plt.subplot(3, 1, 3)
    plt.plot(ts, i_inj, 'k')
    plt.xlabel('t (ms)')
    plt.ylabel('$I_{inj}$ ($\\mu{A}/cm^2$)')
    plt.ylim(-1, 40)

    if (show):
        plt.show()

    if(save):
        plt.savefig('images/output_%s.png' % suffix)


def plots_results(model, ts, i_inj_values, results, suffix="", show=True, save=False):
    print(results.shape)
    V = results[:, 0]
    p = results[:, 1]
    q = results[:, 2]
    n = results[:, 3]
    e = results[:, 4]
    f = results[:, 5]
    cac = results[:, 6]

    h = model.h_notensor(cac)
    ica = model.I_Ca(V, e, f, h)
    ik = model.I_Ks(V, n) + model.I_Kf(V, p, q)
    il = model.I_L(V)

    plt.figure()

    plt.subplot(5, 1, 1)
    plt.title('Hodgkin-Huxley Neuron')
    plt.plot(ts, V, 'k')
    plt.ylabel('V (mV)')

    plt.subplot(5, 1, 2)
    plt.plot(ts, cac, 'r')
    plt.ylabel('Ca2+ concentration')

    plt.subplot(5, 1, 3)
    plt.plot(ts, ica, 'c', label='$I_{Ca}$')
    plt.plot(ts, ik, 'y', label='$I_{K}$')
    plt.plot(ts, il, 'm', label='$I_{L}$')
    plt.ylabel('Current')
    plt.legend()

    plt.subplot(5, 1, 4)
    plt.plot(ts, p, RATE_COLORS['p'], label='p')
    plt.plot(ts, q, RATE_COLORS['q'], label='q')
    plt.plot(ts, n, RATE_COLORS['n'], label='n')
    plt.plot(ts, e, RATE_COLORS['e'], label='e')
    plt.plot(ts, f, RATE_COLORS['f'], label='f')
    plt.plot(ts, h, RATE_COLORS['h'], label='h')
    plt.ylabel('Gating Value')
    plt.legend()

    plt.subplot(5, 1, 5)
    plt.plot(ts, i_inj_values, 'k')
    plt.xlabel('t (ms)')
    plt.ylabel('$I_{inj}$ ($\\mu{A}/cm^2$)')
    plt.ylim(-1, 40)

    if(show):
        plt.show()

    if(save):
        plt.savefig('images/results_%s.png'%suffix)
# %%
from scipy.integrate import odeint
import pickle
import pandas as pd
import numpy as np
import matplotlib.pyplot as plt
from tensorflow.keras.layers import Dense, Activation
from tensorflow.keras.models import Sequential, load_model
from src.dataGen import test_data

columns, in_scaler, out_scaler = pickle.load(open('data/tmp.pkl', 'rb'))
# columns = org.columns
species = columns
labels = columns.drop(['AR', 'dt', 'f', 'cp'])
input_features = labels

# %%
out_m = out_scaler.std.mean_.astype('float32')
out_s = out_scaler.std.scale_.astype('float32')
# out_m = (new[labels]-org[labels]).div(org.dt,axis=0).mean().values
# out_s = (new[labels]-org[labels]).div(org.dt,axis=0).std().values

model_inv = Sequential()
model_inv.add(Dense(len(out_m), input_dim=len(out_m), trainable=True))
model_inv.add(Activation('linear'))
model_inv.layers[0].set_weights([(out_s) * np.identity(len(out_m)), +out_m])

in_m = in_scaler.std.mean_.astype('float32')
in_s = in_scaler.std.scale_.astype('float32')
# in_m = org[labels].mean().values
# in_s = org[labels].std().values

model_trans = Sequential()
model_trans.add(Dense(len(in_m), input_dim=(len(in_m)), trainable=True))
model_trans.add(Activation('linear'))
model_trans.layers[0].set_weights([(1 / in_s) * np.identity(len(in_m)),
                                   -(in_m / in_s)])

# %%
model_neuralODE = load_model('base_neuralODE.h5')
model_neuralODE.summary()

# %%
post_model = Sequential()
post_model.add(model_trans)
post_model.add(model_neuralODE)
post_model.add(model_inv)
post_model.save('postODENet.h5')

# %%
# post_model.predict(org[labels].iloc[0:1])

# out_scaler.inverse_transform(model_neuralODE.predict(
#     in_scaler.transform(org[labels].iloc[0:1])))


# %%
def euler(data_in, dt):

    pred = data_in[input_features]

    #     print(i)
    model_pred = pd.DataFrame(out_scaler.inverse_transform(
        model_neuralODE.predict(in_scaler.transform(pred),
                                batch_size=1024 * 8)),
                              columns=labels)
    # model_pred = pd.DataFrame(post_model.predict(
    #     pred, batch_size=1024*8), columns=labels)

    pred = (model_pred) * dt + pred

    return pred


def rk2(data_in, dt):

    pred = data_in[input_features]

    k1 = pd.DataFrame(post_model.predict(pred, batch_size=1024 * 8),
                      columns=labels)
    mid = k1 * (dt / 2) + pred

    k2 = pd.DataFrame(post_model.predict(mid, batch_size=1024 * 8),
                      columns=labels)

    pred = k2 * dt + pred

    return pred


def rk4(data_in, dt):
    p1 = data_in
    k1 = pd.DataFrame(post_model.predict(p1[input_features],
                                         batch_size=1024 * 8),
                      columns=labels)
    # print(k1)
    p2 = k1 * dt / 2 + data_in
    k2 = pd.DataFrame(post_model.predict(p2[input_features],
                                         batch_size=1024 * 8),
                      columns=labels)

    p3 = k2 * dt / 2 + data_in
    k3 = pd.DataFrame(post_model.predict(p3[input_features],
                                         batch_size=1024 * 8),
                      columns=labels)

    p4 = k3 * dt + data_in
    k4 = pd.DataFrame(post_model.predict(p4[input_features],
                                         batch_size=1024 * 8),
                      columns=labels)

    model_pred = 1 / 6 * (k1 + 2 * k2 + 2 * k3 + k4)
    pred = data_in + model_pred * dt
    # pred = pred.clip(0)
    # print(model_red)
    return pred


def nvAd(data_in, dt, odeAg, st):
    # st = 10
    pred = data_in[input_features]

    for i in range(st):
        pred = odeAg(pred, dt / st)

    # pred = pred.clip(0)

    return pred, (pred - data_in[input_features]) / dt


# %%


def dydt(x, t):
    out = out_scaler.inverse_transform(
        model_neuralODE.predict(in_scaler.transform(x.reshape(1, -1)),
                                batch_size=1024 * 8))
    # out = post_model.predict(x.reshape(1, -1))

    return out.flatten()


def odeInt(data_in, dt):
    out_ode = []
    for i in range(len(data_in)):
        x0 = data_in[input_features].iloc[i:i + 1]
        ode_out = odeint(dydt, x0.values[0], [0, dt])
        out_ode.append(ode_out[1].reshape(1, -1))

    out = np.concatenate(out_ode)
    out = pd.DataFrame(out, columns=labels)

    return out, (out - data_in[labels]) / dt


solvers = {'euler': euler, 'midpoint': rk2, 'rk4': rk4}
# %%
# post_species = species.drop(['cp', 'Hs', 'Rho','dt','f','N2'])
post_species = pd.Index(['HO2', 'OH', 'O', 'H2'])
# post_species = pd.Index(['T'])
# post_species = labels
plt.rcParams['figure.figsize'] = [15, 5]
st = 1
ini_T = 1401
dt = 1e-6
solver = 'rk4'
for n in [2]:
    input_0, test = test_data(ini_T, n, columns, dt)

    input_0 = input_0.reset_index(drop=True)
    test = test.reset_index(drop=True)
    print(test.shape)
    # logLab=['HO2','H2O2']
    # logLab=['HO2','H2O2','O','OH','H2O','H']
    # input_0[logLab] = np.log(input_0[logLab])
    # test[logLab] = np.log(test[logLab])
    # input_0 = np.cbrt(input_0)
    # test = np.cbrt(test)

    test = test.astype('float32')
    # input_0 = input_0.iloc[:100]
    # test = test.iloc[:100]
    s = 2
    e = -1
    input_0 = input_0.iloc[s:e].reset_index(drop=True)
    test = test.iloc[s:e].reset_index(drop=True)
    print(test.shape)
    pred, model_pred = nvAd(input_0, dt, solvers[solver], st)
    # pred, model_pred = odeInt(input_0, dt)

    test_target = ((test[labels] - input_0[labels]) / dt)

    testGrad = pd.DataFrame(out_scaler.transform(test_target[labels]),
                            columns=labels)
    trGrad = pd.DataFrame(out_scaler.transform(model_pred[labels]),
                          columns=labels)

    for sp in post_species.intersection(species):
        f, axarr = plt.subplots(1, 3)
        f.suptitle('{}: {}, T={}'.format(solver.upper(), sp, ini_T))

        axarr[0].plot(test[sp])
        axarr[0].plot(pred[sp], 'rd', ms=2)
        # axarr[0].set_title(str(n) + '_' + sp)

        # axarr[1].plot(abs(test[sp] - pred[sp]) / test[sp], 'yd', ms=2)
        axarr[1].plot((test[sp] - pred[sp]) / test[sp].max(), 'yd', ms=2)

        #         axarr[1].set_ylim(-0.005, 0.005)
        # axarr[1].set_title(str(n) + '_' + sp)

        ax2 = axarr[1].twinx()
        ax2.plot(test_target[sp], 'bd', ms=2)
        ax2.plot(model_pred[sp], 'rd', ms=2)
        # ax2.set_ylim(-0.0015, 0.0015)

        axarr[2].plot(testGrad[sp], 'bd', ms=2)
        axarr[2].plot(trGrad[sp], 'rd', ms=2)
        # axarr[2].set_ylim(-1,1)

        #           ax2.plot(no_scaler[sp], 'md', ms=2)

        plt.savefig('fig/' + '{}_{}_{}_{}'.format(st, solver, ini_T, sp))
        plt.show()

# %%


def integration():
    t = np.linspace(0, 2e-4, 2000)
    out = odeint(dydt, input_0[labels].iloc[0:1].values[0], t)
    out = pd.DataFrame(out, columns=labels)
    out['t'] = t
    return out


acc = integration()
#%%
test['t'] = np.linspace(0, (test.shape[0] - 1) * dt, test.shape[0])
sp = 'T'
plt.plot(acc['t'], acc[sp], 'rd', ms=2)
plt.plot(test['t'], input_0[sp], 'b')
plt.title('{},T={}'.format(sp, ini_T))
plt.show()

# %%
import tensorflow.keras as keras
from tensorflow.keras.layers import Input
from tensorflow.keras.models import Model
from tensorflow.keras.utils import plot_model

dim_input = len(labels)

din = Input(shape=(dim_input, ), name='input_y')
dt = Input(shape=(1, ), name='input_dt')

p1 = din
k1 = post_model(p1)

mul2 = keras.layers.multiply([k1, keras.layers.Lambda(lambda x: x * 0.5)(dt)])
p2 = keras.layers.add([mul2, p1])
k2 = post_model(p2)

mul3 = keras.layers.multiply([k2, keras.layers.Lambda(lambda x: x * 0.5)(dt)])
p3 = keras.layers.add([mul3, p1])
k3 = post_model(p3)

mul4 = keras.layers.multiply([k3, dt])
p4 = keras.layers.add([mul4, p1])
k4 = post_model(p4)

out1 = keras.layers.Lambda(lambda x: x * 1 / 6)(k1)
out2 = keras.layers.Lambda(lambda x: x * 1 / 3)(k2)
out3 = keras.layers.Lambda(lambda x: x * 1 / 3)(k3)
out4 = keras.layers.Lambda(lambda x: x * 1 / 6)(k4)
out = keras.layers.add([out1, out2, out3, out4],name='out')

rk4Model = Model(inputs=[din, dt], outputs=out)
rk4Model.summary()

plot_model(rk4Model, to_file="fig/rk4Model.png")
rk4Model.save('rk4Model.h5')

#%% RK4 Model
post_species = pd.Index(['HO2', 'OH', 'O', 'Hs'])

plt.rcParams['figure.figsize'] = [15, 5]
st = 1
ini_T = 1401
dt = 1e-6
solver = 'rk4Model'
for n in [2]:
    input_0, test = test_data(ini_T, n, columns, dt)

    input_0 = input_0.reset_index(drop=True)
    test = test.reset_index(drop=True)
    print(test.shape)

    test = test.astype('float32')
    s = 2
    e = -1
    input_0 = input_0.iloc[s:e].reset_index(drop=True)
    test = test.iloc[s:e].reset_index(drop=True)
    print(test.shape)

    pred,
    steps = np.ones((input_0.shape[0], 1))

    model_pred = pd.DataFrame(rk4Model.predict([input_0[labels], steps * dt]),
                              columns=labels)
    pred = input_0[labels] + model_pred * dt

    test_target = ((test[labels] - input_0[labels]) / dt)

    testGrad = pd.DataFrame(out_scaler.transform(test_target[labels]),
                            columns=labels)
    trGrad = pd.DataFrame(out_scaler.transform(model_pred[labels]),
                          columns=labels)

    for sp in post_species.intersection(species):
        f, axarr = plt.subplots(1, 3)
        f.suptitle('{}: {}, T={}'.format(solver.upper(), sp, ini_T))

        axarr[0].plot(test[sp])
        axarr[0].plot(pred[sp], 'rd', ms=2)

        axarr[1].plot((test[sp] - pred[sp]) / test[sp].max(), 'yd', ms=2)

        ax2 = axarr[1].twinx()
        ax2.plot(test_target[sp], 'bd', ms=2)
        ax2.plot(model_pred[sp], 'rd', ms=2)

        axarr[2].plot(testGrad[sp], 'bd', ms=2)
        axarr[2].plot(trGrad[sp], 'rd', ms=2)

        plt.savefig('fig/' + '{}_{}_{}_{}'.format(st, solver, ini_T, sp))
        plt.show()

#%%

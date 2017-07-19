import downhill
import theano
import theano.tensor as T
from theano.tensor.shared_randomstreams import RandomStreams
import numpy as np
import pandas as pd
import networkx as nx
from settings import PATH_TO_DUMPS

from load_data import load_blog_catalog, load_karate

# class HistLoss:
#     def __init__(self, N, dim, bin_num=64, neg_sampling=True, seed=None):
#         self.bin_num = bin_num
#         self.neg_sampling = neg_sampling
#         self.srng = RandomStreams(seed=234)
#
#         self.A = T.dmatrix('A')
#         self.w = theano.shared(np.random.normal(size=(N, dim)))
#         self.b = theano.shared(np.zeros((N, dim)))
#
#     def compile(self):
#         E = T.dot(self.A, self.w) + self.b
#         E_norm = E / E.norm(2, axis=1).reshape((E.shape[0], 1))
#         E_corr = T.dot(E_norm, E_norm.T)
#         pos_mask = A
#         neg_mask = 1 - pos_mask - T.eye(pos_mask.shape[0])

srng = RandomStreams(seed=234)
neg_sampling = True
bin_num = 64
dim = 16

N = 10312
graph = load_blog_catalog()
nodes = graph.nodes()
adjacency_matrix = nx.adjacency_matrix(graph, nodes).astype("float64")
adj_array = adjacency_matrix.toarray()

# graph = load_karate()
# nodes = graph.nodes()
# adjacency_matrix = nx.adjacency_matrix(graph, nodes).astype('float64')
# N = adjacency_matrix.shape[0]
# adj_array = adjacency_matrix.toarray()


# variables to optimize
w = theano.shared(np.random.normal(size=(N, dim)), 'w')
b = theano.shared(np.zeros((N, dim)), 'b')

# input for loss
A = T.dmatrix('A')
batch_indxs = T.vector('batch_indxs', dtype='int64')

# batched data
A_batched = A[batch_indxs]  # shape: (batch_n, N)
b_batched = b[batch_indxs]  # shape: (batch_n, dim)

E = T.dot(A_batched, w) + b_batched  # shape: (batch_n, dim)

E_norm = E/E.norm(2, axis=1).reshape((E.shape[0], 1))  # shape: (batch_n, batch_n)

E_corr = T.dot(E_norm, E_norm.T)  # shape: (batch_n, batch_n)

pos_mask = A_batched[:, batch_indxs]  # shape: (batch_n, batch_n)
neg_mask = 1 - pos_mask - T.eye(pos_mask.shape[0])  # shape: (batch_n, batch_n)

pos_samples = E_corr[pos_mask.nonzero()]
neg_samples = E_corr[neg_mask.nonzero()]

# if neg_sampling:
#     neg_samples = neg_samples[srng.choice(size=(2*pos_samples.shape[0], ), a=neg_samples.shape[0])]


def calc_hist_vec(samples, bin_num=bin_num):
    delta = 2/(bin_num - 1)
    # ts =  -1 + delta * T.arange(bin_num)
    rs = T.floor((samples + 1) / delta) + 1  # r is natural index
    ts = -1 + delta * (rs - 1)  # t_r is value between -1 and 1
    samples_sub_t_prev = samples - ts
    t_next_sub_samples = delta - samples_sub_t_prev

    H, _ = theano.map(
        lambda r: (
            T.sum(samples_sub_t_prev[T.eq(rs, r).nonzero()]) +
            T.sum(t_next_sub_samples[T.eq(rs-1, r).nonzero()])
        ),
        np.arange(1, bin_num + 1)
    )
    return H / delta

pos_hist = calc_hist_vec(pos_samples)
neg_hist = calc_hist_vec(neg_samples)

agg_pos = T.extra_ops.cumsum(pos_hist)
loss = T.sum(T.dot(agg_pos, neg_hist))


def get_batch():
    return np.random.choice(a=N, size=10), adj_array


downhill.minimize(
    loss,
    # train=(np.arange(N), adj_array),
    train=get_batch,
    inputs=[batch_indxs, A],
    monitor_gradients=True,
    batch_size=10,
    max_gradient_elem=0,
    learning_rate=0.1
)
print(w.get_value())
print(b.get_value())

# # testing
# import time
#
# print('Compiling')
# t = time.time()
# f = theano.function(
#     [A, E], [E_norm, E_corr, pos_hist, neg_hist, loss, pos_mask, neg_mask]
# )
# print(time.time() - t)
#
# # t = time.time()
# # res = f([[0, 1, 0], [1, 0, 1], [0, 1, 0]], [[1, 2, 3], [2, 3, 4], [-1, -2, -3]])
# # print(time.time() - t)
#
# print('Reading embedding')
# t = time.time()
# X = pd.read_csv(
#     '{}/models/deepwalk_BlogCatalog_d32.csv'.format(PATH_TO_DUMPS),
#     delim_whitespace=True, header=None,
#     skiprows=1,
#     index_col=0
# ).sort_index()
# E_input = X.values
# print(time.time() - t)
#
# print('Reading graph')
# t = time.time()
# graph = load_blog_catalog()
# nodes = graph.nodes()
# adjacency_matrix = nx.adjacency_matrix(graph, nodes).todense().astype("float32")
# print(time.time() - t)
#
# print('Solving')
# t = time.time()
# res = f(adjacency_matrix, E_input)
# print(time.time() - t)
#
# print(res[0])
# print(res[1][:2])
# print(res[2])
# print(res[3])
# print(res[4])
# print(res[5][:2])
# print(res[6][:2])

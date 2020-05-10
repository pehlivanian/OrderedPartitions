import logging
import multiprocessing
import numpy as np
from itertools import combinations
from scipy.special import comb
from sklearn.datasets import make_classification
from sklearn.model_selection import train_test_split
from sklearn.linear_model import LinearRegression
from sklearn.discriminant_analysis import LinearDiscriminantAnalysis
from functools import partial, lru_cache
from itertools import chain, islice

import theano
import theano.tensor as T
from theano.tensor.shared_randomstreams import RandomStreams

X,y = make_classification(random_state=55, n_samples=100)
X_train, X_test, y_train, y_test = train_test_split(X, y)

SEED = 55
rng = np.random.RandomState(SEED)

class GradientBoostingPartitionClassifier(object):
    def __init__(self,
                 X,
                 y,
                 min_partition_size,
                 max_partition_size,
                 gamma=0.,
                 eta=0.,
                 num_classifiers=100,
                 use_constant_term=False,
                 solver_type='linear_hessian',
                 learning_rate=0.1,
                 distill_method='OLS',
                 use_monotonic_partitions=True
                 ):

        # Inputs
        self.X = theano.shared(value=X, name='X', borrow=True)
        self.y = theano.shared(value=y, name='y', borrow=True)
        initial_X = self.X.get_value()
        self.N, self.num_features = initial_X.shape
        
        self.min_partition_size = min_partition_size
        self.max_partition_size = max_partition_size
        self.gamma = gamma
        self.eta = eta
        self.num_classifiers = num_classifiers
        self.curr_classifier = 0

        # algorithm directives
        # solver_type is one of
        # ('quadratic, 'linear_hessian', 'linear_constant')
        self.use_constant_term = use_constant_term
        self.solver_type = solver_type
        self.learning_rate = learning_rate
        self.distill_method = distill_method
        self.use_monotonic_partitions = use_monotonic_partitions

        # Derived
        # optimal partition at each step, not part of any
        # gradient calculation so not a tensor
        self.partitions = list()
        # distinct leaf values at each step, also not a tesnor
        self.distinct_leaf_values = np.zeros((self.num_classifiers + 1,
                                             self.N))
        # regularization penalty at each step
        self.regularization = theano.shared(name='regularization',
                                            value=np.zeros((self.num_classifiers + 1,
                                                            1)).astype(theano.config.floatX))
        # optimal learner at each step
        self.leaf_values = theano.shared(name='leaf_values',
                                         value=np.zeros((self.num_classifiers + 1,
                                                         self.N,
                                                         1)).astype(theano.config.floatX))
        # optimal approximate tree at each step
        self.implied_trees = theano.shared(name='implied_trees',
                                           value=np.zeros((self.num_classifiers + 1,
                                                           self.num_features + 1,
                                                           1)).astype(theano.config.floatX))

        # set initial random leaf values
        # leaf_value = np.asarray(rng.choice((0, 1),
        #                               self.N)).reshape(self.N, 1).astype(theano.config.floatX)
        # noise = np.asarray(rng.choice((-1e-1, 1e-1),
        #                               self.N)).reshape(self.N, 1).astype(theano.config.floatX)
        # leaf_value = self.y.get_value().reshape((self.N, 1)) + noise
        leaf_value = np.asarray(rng.uniform(low=0.0, high=1.0, size=(self.N, 1))).astype(theano.config.floatX)
        self.set_next_leaf_value(leaf_value)

        # Set initial partition to be the size 1 partition (all leaf values the same)
        self.partitions.append(list(range(self.N)))

        # Set initial classifier
        implied_tree = self.imply_tree(leaf_value)
        self.set_next_classifier(implied_tree)        
        
        # For testing
        self.srng = T.shared_randomstreams.RandomStreams(seed=SEED)

        self.curr_classifier += 1

    def set_next_classifier(self, classifier):
        i = self.curr_classifier
        c = T.dmatrix()
        update = (self.implied_trees,
                  T.set_subtensor(self.implied_trees[i, :, :], c))
        f = theano.function([c], updates=[update])
        f(classifier)

    def set_next_leaf_value(self, leaf_value):
        i = self.curr_classifier
        c = T.dmatrix()
        update = (self.leaf_values,
                  T.set_subtensor(self.leaf_values[i, :, :], c))
        f = theano.function([c], updates=[update])
        f(leaf_value)

    def imply_tree(self, leaf_values):
        X0 = self.X.get_value()
        y0 = leaf_values
            
        if self.distill_method == 'OLS':
            from sklearn.linear_model import LinearRegression
            reg = LinearRegression(fit_intercept=True).fit(X0, y0)
            implied_tree = np.concatenate([reg.coef_.squeeze(), reg.intercept_]).reshape(-1,1)
        elif self.distill_method == 'LDA':
            clf_lda = LDAImpliedTree(X0, y0)
            clf_lda.fit()
            implied_tree = clf_lda
        elif self.distill_method == 'direct':
            implied_tree = np.asarray([np.nan]*(1 + self.num_features)).reshape(-1, 1)
        return implied_tree

    def weak_learner_predict(self, implied_tree, classifier_ind):
        if self.distill_method == 'OLS':
            ones = T.as_tensor(np.ones((self.N, 1)).astype(theano.config.floatX))
            X = T.concatenate([self.X, ones], axis=1)
            y_hat = T.dot(X, implied_tree)
        elif self.distill_method == 'direct':
            y_hat = self.leaf_values[classifier_ind]
            
        return y_hat

    def predict(self):
        def iter_step(learner, classifier_ind):
            y_step = self.weak_learner_predict(learner, classifier_ind)
            return y_step

        # scan is short-circuited by length of T.arange(self.curr_classifier)
        y,inner_updates = theano.scan(
            fn=iter_step,
            sequences=[self.implied_trees, T.arange(self.curr_classifier)],
            outputs_info=[None],
            n_steps=self.curr_classifier,
            )

        return T.sum(y, axis=0)
    
    def loss(self, y_hat):
        return self._mse(y_hat) + T.sum(self.regularization)

    def loss_without_regularization(self, y_hat):
        return self._mse(y_hat)

    def fit(self, num_steps=None):
        num_steps = num_steps or self.num_classifiers
        print('STEP {}: LOSS: {:4.6f}'.format(0, theano.function([], clf.loss_without_regularization(clf.predict()))()))        
        for i in range(num_steps):
            self.fit_step(num_partitions)
            print('STEP {}: LOSS: {:4.6f}'.format(i, theano.function([], self.loss_without_regularization(clf.predict()))()))
        print('Training finished')

    def fit_step(self, num_partitions):
        g, h, c = self.generate_coefficients(constantTerm=self.use_constant_term)

        optimizer = PartitionTreeOptimizer(g,
                                           h,
                                           c,
                                           solver_type=self.solver_type,
                                           use_monotonic_partitions=self.use_monotonic_partitions)
        optimizer.run(num_partitions)
        
        # Set next partition to be optimal
        self.partitions.append(optimizer.maximal_part)

        # Assert optimization correct
        assert np.isclose(optimizer.maximal_val, np.sum(optimizer.summands)), \
               'optimal value mismatch'
        for part,val in zip(optimizer.maximal_part, optimizer.summands):
            if self.solver_type == 'linear_hessian':
                assert np.isclose(np.sum(abs(g[part]))**2/np.sum(h[part]), val), \
                       'optimal partitions mismatch'

        print('LENGTH OF OPTIMAL PARTITIONS: {!r}'.format(
            [len(part) for part in optimizer.maximal_part]))
        print('OPTIMAL PARTITION ENDPOITS: {!r}'.format(
            [(p[0],p[-1]) for p in optimizer.maximal_part]))
        print('OPTIMAL SUMMANDS: {!r}'.format(
            optimizer.summands))
                    
        
        # Calculate optimal leaf_values
        leaf_value = np.zeros((self.N, 1))
        
        for part in optimizer.maximal_part:
            if self.solver_type == 'quadratic':
                r1, r2 = self.quadratic_solution_scalar(np.sum(g[part]),
                                                        np.sum(h[part]),
                                                        np.sum(c[part]))
                leaf_value[part] = self.learning_rate * r1
            elif self.solver_type == 'linear_hessian':
                min_val = -1 * np.sum(g[part])/np.sum(h[part])
                leaf_value[part] = self.learning_rate * min_val
            elif self.solver_type == 'linear_constant':
                min_val = -1 * np.sum(g[part])/np.sum(c[part])
                leaf_value[part] = self.learning_rate * min_val
            else:
                raise RuntimeError('Incorrect solver_type')
            
        # Set leaf_value
        self.set_next_leaf_value(leaf_value)

        # Calculate implied_tree
        implied_tree = self.imply_tree(leaf_value)

        # Set implied_tree
        self.set_next_classifier(implied_tree)

        self.curr_classifier += 1

    def generate_coefficients(self, constantTerm=False):
        x = T.dvector('x')
        loss = self.loss_without_regularization(T.shape_padaxis(x, 1))

        grads = T.grad(loss, x)
        hess = T.hessian(loss, x)

        G = theano.function([x], grads)
        H = theano.function([x], hess)

        y_hat0 = theano.function([], self.predict())().squeeze()
        g = G(y_hat0)
        h = np.diag(H(y_hat0))

        c = None
        if constantTerm and not self.solver_type == 'linear_hessian':
            c = theano.function([], self._mse_coordinatewise(self.predict()))().squeeze()
            return (g, h, c)

        return (g, h, c)        
        
    def generate_coefficients_old(self, constantTerm=False):
        ''' Generate gradient, hessian sequences for offgraph
            optimizaition, return types are np.arrays
        '''
        x = T.dvector('x')
        loss = self.loss_without_regularization(T.shape_padaxis(x, 1))


        grads = T.grad(loss, x)
        hess = T.hessian(loss, x)

        G = theano.function([x], grads)
        H = theano.function([x], hess)

        # Test - random y_hat, random increment f_T
        y_hat0 = rng.uniform(low=0., high=1., size=(self.N,))
        f_t = rng.uniform(low=0., high=.01, size=(self.N,))
        loss0 = theano.function([x], loss)(y_hat0 + f_t)        
        loss0_approx0 = theano.function([x], loss)(y_hat0) + \
                        np.dot(G(y_hat0), f_t) + \
                        0.5 * np.dot(f_t.T, np.dot(H(y_hat0), f_t))
        loss0_approx1 = theano.function([x], loss)(y_hat0) + \
                        np.dot(G(y_hat0), f_t) + \
                        0.5 * np.dot(np.dot(f_t.T, H(y_hat0)), f_t)
        assert np.isclose(loss0, loss0_approx0, rtol=0.01)
        assert np.isclose(loss0, loss0_approx1, rtol=0.01)

        # Test
        y_hat0 = rng.uniform(low=0., high=1., size=(self.N,))
        y0 = self.y.get_value()
        f_t0 = y0 - y_hat0
        g = G(y_hat0)
        h = np.dot(f_t0.T, H(y_hat0))
        y_tilde = y_hat0 - (0.5 * -g*g/h)
        assert np.isclose(y_tilde, y0).all()

        # Test
        quadratic_term0 = 0.5 * np.dot(f_t.T, np.dot(H(y_hat0), f_t))
        quadratic_term1 = 0.5 * np.dot(np.dot(f_t.T, H(y_hat0)), f_t)
        assert np.isclose(quadratic_term0, quadratic_term1)

        # Test - y_hat = prediction, f_t = y - y_hat
        y_hat0 = theano.function([], self.predict())().squeeze()
        f_t = self.y.get_value() - y_hat0
        loss0 = theano.function([x], loss)(y_hat0 + f_t)        
        loss0_approx = theano.function([x], loss)(y_hat0) + \
                      np.dot(G(y_hat0), f_t) + \
                      0.5 * np.dot(np.dot(f_t.T, H(y_hat0)), f_t)
        assert np.isclose(loss0, loss0_approx, rtol=0.01)

        y_hat = theano.function([], self.predict())().squeeze()
        f_t = self.y.get_value() - y_hat0
        g = G(y_hat0)
        h = np.dot(f_t.T, H(y_hat0))                

        if constantTerm:
            c = theano.function([], self._mse_coordinatewise(self.predict()))().squeeze()
            return (g, h, c)

        return (g, h)        

    def _mse(self, y_hat):
        # XXX
        return T.sum(self._mse_coordinatewise(y_hat))
        # return T.sqrt(T.sum(self._mse_coordinatewise(y_hat)))

    def _mse_coordinatewise(self, y_hat):
        return (T.shape_padaxis(self.y, 1) - y_hat)**2

    def _regularizer(self, leaf_values):
        size_reg = self.gamma * partition_size
        coeff_reg = 0.5 * self.eta * np.sum(leaf_values**2)
        return size_req + coeff_reg

    def quadratic_solution_scalar(self, g, h, c):
        a,b = 0.5*h, g
        s1 = -b
        s2 = np.sqrt(b**2 - 4*a*c)
        r1 = (s1 + s2) / (2*a)
        r2 = (s1 - s2) / (2*a)

        return r1, r2
    
    def quadratic_solution( self, g, h, c):
        a,b = 0.5*h, g
        s1 = -b
        s2 = np.sqrt(b**2 - 4*a*c)
        r1 = (s1 + s2) / (2*a)
        r2 = (s1 - s2) / (2*a)

        return (r1.reshape(-1,1), r2.reshape(-1, 1))
        
class OLSImpliedTree(LinearRegression):
    def __init__(self, X=None, y=None):
        super(OLSImpliedTree, self).__init__(fit_intercept=True)
        self.X = X
        self.y = y
        super(OLSImpliedTree, self).fit(X, y)
        
    def predict(self, X):
        coeffs = np.concatenate([reg.coef_.squeeze(), reg.intercept_]).reshape(-1,1)

        ones = T.as_tensor(np.ones((self.N, 1)).astype(theano.config.floatX))
        X = T.concatenate([self.X, ones], axis=1)
        y_hat = T.dot(X, implied_tree)

class LDAImpliedTree(LinearDiscriminantAnalysis):
    def __init__(self, X=None, y=None):
        super(LDAImpliedTree, self).__init__()
        self.X = X
        unique_vals = np.sort(np.unique(y))
        self.val_to_class = dict(zip(unique_vals, range(len(unique_vals))))
        self.class_to_val = {v:k for k,v in self.val_to_class.items()}
        self.y = np.array([self.val_to_class[x[0]] for x in y])

    def fit(self):
        super( LDAImpliedTree, self).fit(self.X, self.y)

    def predict(self, X):
        y_hat0 = super(LDAImpliedTree, self).predict(X)
        y_hat = np.array([self.class_to_val[x] for x in y_hat0])
        return y_hat

class Task(object):
    def __init__(self, a, b, c, solver_type, partition, partition_type='full'):
        self.partition = partition
        self.solver_type = solver_type
        self.task = partial(self._task, a, b, c)
        self.partition_type = partition_type # {'full', 'endpoints'}

    def __call__(self):
        return self.task(self.partition)

    def _task(self, a, b, c, partitions, report_each=1000):
        max_sum = float('-inf')
        arg_max = -1
        for ind,part in enumerate(partitions):
            val = 0
            part_vertex = [0] * len(part)
            for part_ind, p in enumerate(part):
                inds = p
                if self.partition_type == 'endpoints':
                    inds = range(p[0], p[1])
                if self.solver_type == 'linear_hessian':                    
                    part_sum = sum(a[inds])**2/sum(b[inds]) + sum(c[inds])
                # Is this correct?
                elif self.solver_type == 'quadratic':
                    part_sum = sum(a[inds])**2/sum(b[inds]) + sum(c[inds])
                elif self.solver_type == 'linear_constant':
                    part_sum = sum(a[inds])/sum(c[inds])
                else:
                    raise RuntimeError('incorrect solver_type specification')
                part_vertex[part_ind] = part_sum
                val += part_sum
            if val > max_sum:
                max_sum = val
                arg_max = part
                max_part_vertex = part_vertex
            # if not ind%report_each:
            #     print('Percent complete: {:.{prec}f}'.
            #           format(100*len(slices)*ind/num_partitions, prec=2))
        return (max_sum, arg_max, max_part_vertex)

class Worker(multiprocessing.Process):
    def __init__(self, task_queue, result_queue):
        multiprocessing.Process.__init__(self)
        self.task_queue = task_queue
        self.result_queue = result_queue

    def run(self):
        proc_name = self.name
        while True:
            task = self.task_queue.get()
            # print('{} : Fetched task of type {}'.format(proc_name, type(task)))
            if task is None:
                # print('Exiting: {}'.format(proc_name))
                self.task_queue.task_done()
                break
            result = task()
            self.task_queue.task_done()
            self.result_queue.put(result)

class PartitionTreeOptimizer(object):
    def __init__(self,
                 a,
                 b,
                 c=None,
                 num_workers=None,
                 solver_type='linear_hessian',
                 use_monotonic_partitions=True):


        self.a = a if c is not None else abs(a)
        self.b = b
        self.c = c if c is not None else np.zeros(a.shape)
        self.n = len(a)
        self.num_workers = num_workers or multiprocessing.cpu_count() - 1
        self.solver_type = solver_type
        self.use_monotonic_partitions = use_monotonic_partitions
        self.partition_type = 'endpoints' if self.use_monotonic_partitions else 'full'            
        
        self.INT_LIST = range(0, self.n)

        if self.solver_type == 'linear_hessian':
            self.sortind = np.argsort(self.a / self.b + self.c)
        elif self.solver_type == 'quadratic':
            self.sortind = np.argsort(self.a / self.b + self.c)
        elif self.solver_type == 'linear_constant':
            self.sortind = np.argsort(self.a / self.c)
        else:
            raise RuntimeError('incorrect solver_type specification')
        
        (self.a,self.b,self.c) = (seq[self.sortind] for seq in (self.a,self.b,self.c))

    def run(self, num_partitions):
        self.slice_partitions(num_partitions)

        num_slices = len(self.slices) # should be the same as num_workers
        if num_slices > 1:            
            tasks = multiprocessing.JoinableQueue()
            results = multiprocessing.Queue()
            workers = [Worker(tasks, results) for i in range(self.num_workers)]

            for worker in workers:
                worker.start()

            for i,slice in enumerate(self.slices):
                tasks.put(Task(self.a,
                               self.b,
                               self.c,
                               self.solver_type,
                               slice,
                               partition_type=self.partition_type))

            for i in range(self.num_workers):
                tasks.put(None)

            tasks.join()

            allResults = list()
            while not results.empty():
                result = results.get()
                allResults.append(result)            
        else:
            task = Task(self.a, self.b, self.c, self.solver_type, self.slices[0])
            allResults = [task()]
            
        def reduce(allResults, fn):
            return fn(allResults, key=lambda x: x[0])

        try:
            val,subsets,summands = reduce(allResults, max)
        except ValueError:
            raise RuntimeError('optimization failed for some reason')

        # Assert that partitions are monotonic
        # XXX
        # assert all(np.diff(list(chain.from_iterable(subsets))) > 0)
        
        if self.partition_type == 'endpoints':
            subsets = [range(s[0],s[1]) for s in subsets]

        self.maximal_val = val            
        self.maximal_sorted_part = subsets
        self.maximal_part = [list(self.sortind[subset]) for subset in subsets]
        self.summands = summands

    def slice_partitions(self, num_partitions):
        if self.use_monotonic_partitions == True:
            partitions = PartitionTreeOptimizer._monotonic_partitions(self.n, num_partitions)
        else:
            partitions = PartitionTreeOptimizer._knuth_partitions(self.INT_LIST, num_partitions)
        
        # Have to consume it; can't split work on generator
        partitions = list(partitions)
        num_partitions = len(partitions)

        stride = max(int(num_partitions/self.num_workers), 1)
        bin_ends = list(range(0, num_partitions, stride))
        bin_ends = bin_ends + [num_partitions] if num_partitions/self.num_workers else bin_ends
        islice_on = list(zip(bin_ends[:-1], bin_ends[1:]))
        
        rng.shuffle(partitions)
        slices = [list(islice(partitions, *ind)) for ind in islice_on]
        self.slices = slices

    @staticmethod
    def _monotonic_partitions(n, m):
        ''' Returns endpoints of all monotonic
            partitions
        '''
        combs = combinations(range(n-1), m-1)
        parts = list()
        for comb in combs:
            yield [(l+1, r+1) for l,r in zip((-1,)+comb, comb+(n-1,))]
    
    @staticmethod
    def _knuth_partitions(ns, m):
        def visit(n, a):
            ps = [[] for i in range(m)]
            for j in range(n):
                ps[a[j + 1]].append(ns[j])
            return ps

        def f(mu, nu, sigma, n, a):
            if mu == 2:
                yield visit(n, a)
            else:
                for v in f(mu - 1, nu - 1, (mu + sigma) % 2, n, a):
                    yield v
            if nu == mu + 1:
                a[mu] = mu - 1
                yield visit(n, a)
                while a[nu] > 0:
                    a[nu] = a[nu] - 1
                    yield visit(n, a)
            elif nu > mu + 1:
                if (mu + sigma) % 2 == 1:
                    a[nu - 1] = mu - 1
                else:
                    a[mu] = mu - 1
                if (a[nu] + sigma) % 2 == 1:
                    for v in b(mu, nu - 1, 0, n, a):
                        yield v
                else:
                    for v in f(mu, nu - 1, 0, n, a):
                        yield v
                while a[nu] > 0:
                    a[nu] = a[nu] - 1
                    if (a[nu] + sigma) % 2 == 1:
                        for v in b(mu, nu - 1, 0, n, a):
                            yield v
                    else:
                        for v in f(mu, nu - 1, 0, n, a):
                            yield v

        def b(mu, nu, sigma, n, a):
            if nu == mu + 1:
                while a[nu] < mu - 1:
                    yield visit(n, a)
                    a[nu] = a[nu] + 1
                yield visit(n, a)
                a[mu] = 0
            elif nu > mu + 1:
                if (a[nu] + sigma) % 2 == 1:
                    for v in f(mu, nu - 1, 0, n, a):
                        yield v
                else:
                    for v in b(mu, nu - 1, 0, n, a):
                        yield v
                while a[nu] < mu - 1:
                    a[nu] = a[nu] + 1
                    if (a[nu] + sigma) % 2 == 1:
                        for v in f(mu, nu - 1, 0, n, a):
                            yield v
                    else:
                        for v in b(mu, nu - 1, 0, n, a):
                            yield v
                if (mu + sigma) % 2 == 1:
                    a[nu - 1] = 0
                else:
                    a[mu] = 0
            if mu == 2:
                yield visit(n, a)
            else:
                for v in b(mu - 1, nu - 1, (mu + sigma) % 2, n, a):
                    yield v

        n = len(ns)
        a = [0] * (n + 1)
        for j in range(1, m + 1):
            a[n - m + j] = j - 1
        return f(m, n, 0, n, a)

    @staticmethod
    def _Bell_n_k(n, k):
        ''' Number of partitions of {1,...,n} into
            k subsets, a restricted Bell number
        '''
        if (n == 0 or k == 0 or k > n): 
            return 0
        if (k == 1 or k == n): 
            return 1

        return (k * PartitionTreeOptimizer._Bell_n_k(n - 1, k) + 
                    PartitionTreeOptimizer._Bell_n_k(n - 1, k - 1))

    @staticmethod
    def _Mon_n_k(n, k):
        return comb(n-1, k-1, exact=True)
    

# Test
num_steps = 5
num_classifiers = 50
num_partitions = 4

clf = GradientBoostingPartitionClassifier(X,
                                          y,
                                          min_partition_size=2,
                                          max_partition_size=10,
                                          gamma=0.,
                                          eta=0.,
                                          num_classifiers=num_classifiers,
                                          use_constant_term=False,
                                          solver_type='linear_hessian',
                                          learning_rate=1.0,
                                          distill_method='direct',
                                          use_monotonic_partitions=True
                                          )


clf.fit(num_steps)

# Vanilla regression model
from sklearn.linear_model import LinearRegression
X0 = clf.X.get_value()
y0 = theano.function([], clf.predict())()
reg = LinearRegression(fit_intercept=True).fit(X0, y0)
y_hat = reg.predict(X0)

x = T.dmatrix('x')
_loss = theano.function([x], clf.loss_without_regularization(x))

y_hat_clf = theano.function([], clf.predict())()
y_hat_ols = reg.predict(X0)

print('_loss_clf: {:4.6f}'.format(_loss(y_hat_ols)))
print('_loss_ols: {:4.6f}'.format(_loss(y_hat_clf)))

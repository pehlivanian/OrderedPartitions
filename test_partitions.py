import os
import sys
import numpy as np
import pickle
import multiprocessing
from scipy.special import comb
from functools import partial
from itertools import chain, islice, combinations
import matplotlib.pyplot as plot
from scipy.spatial import ConvexHull, Delaunay


SEED = 3369
rng = np.random.RandomState(SEED)

def subsets(ns):
    return list(chain(*[[[list(x)] for x in combinations(range(ns), i)] for i in range(1,ns+1)]))

def knuth_partition(ns, m):
    if m == 1:
        return [[ns]]
    
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

def Bell_n_k(n, k):
    ''' Number of partitions of {1,...,n} into
        k subsets, a restricted Bell number
    '''
    if (n == 0 or k == 0 or k > n): 
        return 0
    if (k == 1 or k == n): 
        return 1
      
    return (k * Bell_n_k(n - 1, k) + 
                Bell_n_k(n - 1, k - 1))

def _Mon_n_k(n, k):
    return comb(n-1, k-1, exact=True)


def slice_partitions(partitions):
    # Have to consume it; can't split work on generator
    partitions = list(partitions)
    num_partitions = len(partitions)
    
    bin_ends = list(range(0,num_partitions,int(num_partitions/NUM_WORKERS)))
    bin_ends = bin_ends + [num_partitions] if num_partitions/NUM_WORKERS else bin_ends
    islice_on = list(zip(bin_ends[:-1], bin_ends[1:]))

    rng.shuffle(partitions)
    slices = [list(islice(partitions, *ind)) for ind in islice_on]
    return slices

def reduce(return_values, fn):
    return fn(return_values, key=lambda x: x[0])

class EndTask(object):
    pass

class Task(object):
    def __init__(self, a, b, partition, power=2, cond=max):
        self.partition = partition
        self.cond = cond
        self.task = partial(self._task, a, b, power)

    def __call__(self):
        return self.task(self.partition)

    def _task(self, a, b, power, partitions, report_each=1000):

        if self.cond == min:
            max_sum = float('inf')
        else:
            max_sum = float('-inf')            
        
        arg_max = -1
        
        for ind,part in enumerate(partitions):
            val = 0
            part_val = [0] * len(part)
            # print('PARTITION: {!r}'.format(part))
            for part_ind, p in enumerate(part):
                part_sum = np.sum(a[p])**power/np.sum(b[p])
                part_val[part_ind] = part_sum
                val += part_sum
                # print('    SUBSET: {!r} SUBSET SCORE: {:4.4f}'.format(p, part_sum))
            if self.cond(val, max_sum) == val:
                max_sum = val
                arg_max = part
            # print('    PARTITION SCORE: {:4.4f}'.format(val))
        print('MAX PARTITION SCORE: {:4.4f}, MAX_PARTITION: {!r}'.format(max_sum, arg_max))
        # print()
        return (max_sum, arg_max)

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
            if isinstance(task, EndTask):
                # print('Exiting: {}'.format(proc_name))
                self.task_queue.task_done()
                break
            result = task()
            self.task_queue.task_done()
            self.result_queue.put(result)

# LTSS demonstration
if __name__ == '__NOT_MAIN__':
    NUM_POINTS = 8
    POWER = 3.6
    NUM_WORKERS = multiprocessing.cpu_count() - 1
    INT_LIST= range(0, NUM_POINTS)
    
    partitions = subsets(NUM_POINTS)

    slices = slice_partitions(partitions)

    trial = 0
    while True:
        a0 = rng.uniform(low=-10.0, high=10.0, size=int(NUM_POINTS))
        b0 = rng.uniform(low=1., high=10.0, size=int(NUM_POINTS))        
        
        ind = np.argsort(a0/b0)

        (a,b) = (seq[ind] for seq in (a0,b0))
        
        tasks = multiprocessing.JoinableQueue()
        results = multiprocessing.Queue()
        workers = [Worker(tasks, results) for i in range(NUM_WORKERS)]
        num_slices = len(slices)

        if len(partitions) > 100000:
            for worker in workers:
                worker.start()

            for i,slice in enumerate(slices):
                tasks.put(Task(a, b, slice, power=3))

            for i in range(NUM_WORKERS):
                tasks.put(EndTask())

            tasks.join()
        
            allResults = list()
            slices_left = num_slices
            while not results.empty():
                result = results.get(block=True)
                allResults.append(result)
                slices_left -= 1
        else:
            allResults = [Task(a, b, partitions, power=POWER)()]
            
        r_max = reduce(allResults, max)

        try:
            assert all(np.diff(list(chain.from_iterable(r_max[1]))) == 1)
            assert -1+NUM_POINTS in r_max[1][0]
        except AssertionError as e:
            with open('_'.join(['a', str(SEED), str(trial), str(PARTITION_SIZE)]), 'wb') as f:
                pickle.dump(a, f)
            with open('_'.join(['b', str(SEED), str(trial), str(PARTITION_SIZE)]), 'wb') as f:
                pickle.dump(b, f)
            with open('_'.join(['rmax', str(SEED), str(trial), str(PARTITION_SIZE)]), 'wb') as f:
                pickle.dump(r_max, f)

        print('TRIAL: {} : max: {:4.6f} prtn: {!r}'.format(trial, *r_max))
    
        trial += 1

def plot_convex_hull(a0, b0, plot_extended=False, plot_symmetric=False, show_plot=True, show_contours=True):
    NUM_AXIS_POINTS = 201

    fig1, ax1 = None, None

    def in_hull(dhull, x, y):
        return dhull.find_simplex((x,y)) >= 0
    
    def F_symmetric(x,y, gamma):
        return x**gamma/y + (Cx-x)**gamma/(Cy-y)

    def F_orig(x, y, gamma):
        return x**gamma/y
    
    def dF_orig(x, y, gamma):
        return np.array([2*x/y, -x**2/y**2])    

    ind = np.argsort(a0**PRIORITY_POWER/b0)
    (a,b) = (seq[ind] for seq in (a0,b0))

    pi = subsets(len(a))
    if not plot_extended:
        mp = [p[0] for p in pi if len(p[0]) == len(a0)]
        pi.remove(mp)

    if plot_symmetric:
        F = F_symmetric
        title = 'F Symmetric, '
    else:
        F = F_orig
        title = 'F Non-Symmetric, '

    if plot_extended:
        title += 'Full Hull'
    else:
        title += 'Constrained Hull'

    title += '  Case: (n, T) = : ( ' + str(len(a0)) + ', ' + str(PARTITION_SIZE) + ' )'
        
    X = list()
    Y = list()
    txt = list()

    for subset in pi:
        s = subset[0]
        X.append(np.sum(a[s]))
        Y.append(np.sum(b[s]))
        txt.append(str(s))

    if plot_extended:
        X = [0.] + X
        Y = [0.] + Y
        txt = ['-0-'] + txt

    points = np.stack([X,Y]).transpose()

    Xm, XM = np.min(X), np.max(X)
    Ym, YM = np.min(Y), np.max(Y)
    Cx, Cy = np.sum(a), np.sum(b)        

    hull = ConvexHull(points)
    vertices = [points[v] for v in hull.vertices]
    dhull = Delaunay(vertices)

    if show_plot:
        cmap = plot.cm.RdYlBu        
        fig1, ax1 = plot.subplots(1,1)

        xaxis = np.linspace(Xm, XM, NUM_AXIS_POINTS)
        yaxis = np.linspace(Ym, YM, NUM_AXIS_POINTS)
        xaxis, yaxis = xaxis[:-1], yaxis[:-1]
        Xgrid,Ygrid = np.meshgrid(xaxis, yaxis)
        Zgrid = F(Xgrid, Ygrid, POWER)
        
        for xi,xv in enumerate(xaxis):
            for yi,yv in enumerate(yaxis):
                if in_hull(dhull, xv, yv):
                    continue
                else:
                    Zgrid[yi,xi] = 0.

        if show_contours:
            cp = ax1.contourf(Xgrid, Ygrid, Zgrid, cmap=cmap)            
            cp.changed()
            fig1.colorbar(cp)
            

        ax1.scatter(X, Y)
        for i,t in enumerate(txt):
            if i in hull.vertices:
                t = t.replace('[','<').replace(']','>')
            else:
                t = t.replace('[','').replace(']','')
            t = t.replace(', ', ',')
            ax1.annotate(t, (X[i], Y[i]))

        for simplex in hull.simplices:
            ax1.plot(points[simplex,0], points[simplex,1], 'k-')

        plot.title(title)    

        # XXX
        # plot.pause(1e-3)

    vertices_txt = [txt[v] for v in hull.vertices]
    print(vertices_txt)

    return fig1, ax1, vertices_txt
    

def plot_polytope(a0, b0, plot_constrained=True, show_plot=True, save_plot=False):

    fig1, ax1,vert_const_asym = plot_convex_hull(a0, b0, plot_extended=False, plot_symmetric=False, show_plot=show_plot)
    # plot.savefig('plot1.pdf') if save_plot
    plot.pause(1e-3)
    fig2, ax2,vert_const_sym = plot_convex_hull(a0, b0, plot_extended=False, plot_symmetric=True, show_plot=show_plot)
    # plot.savefig('plot2.pdf') if save_plot
    plot.pause(1e-3)    
    fig3, ax3,vert_ext_asym = plot_convex_hull(a0, b0, plot_extended=True, plot_symmetric=False, show_plot=show_plot)
    # plot.savefig('plot3.pdf') if save_plot
    plot.pause(1e-3)    
    fig4, ax4,vert_ext_sym = plot_convex_hull(a0, b0, plot_extended=True, plot_symmetric=True, show_plot=show_plot)
    # plot.savefig('plot14.pdf') if save_plot
    plot.pause(1e-3)    

    if show_plot:
        plot.close()
        plot.close()
        plot.close()
        plot.close()

    return vert_const_asym, vert_const_sym, vert_ext_asym, vert_ext_sym

def optimize(a0, b0, PARTITION_SIZE, POWER, NUM_WORKERS, PRIORITY_POWER, cond=max):
    ind = np.argsort(a0**PRIORITY_POWER/b0)
    (a,b) = (seq[ind] for seq in (a0,b0))

    # XXX
    # if num_mon_partitions > 100:
    if False:
        tasks = multiprocessing.JoinableQueue()
        results = multiprocessing.Queue()
        workers = [Worker(tasks, results) for i in range(NUM_WORKERS)]
        num_slices = len(slices)
        
        for worker in workers:
            worker.start()

        for i,slice in enumerate(slices):
            tasks.put(Task(a, b, slice, power=POWER, cond=cond))

        for i in range(NUM_WORKERS):
            tasks.put(EndTask())

        tasks.join()
        
        allResults = list()
        slices_left = num_slices
        while not results.empty():
            result = results.get(block=True)
            allResults.append(result)
            slices_left -= 1
    else:
        partitions = list(knuth_partition(range(0, len(a)), PARTITION_SIZE))
        allResults = [Task(a, b, partitions, power=POWER, cond=cond)()]
    
            
    r_max = reduce(allResults, cond)

    # import pdb
    # pdb.set_trace()

    # summands = [np.sum(a[p])**2/np.sum(b[p]) for p in r_max[1]]
    # parts = [ind[el] for el in [p for p in r_max[1]]]
    
    return r_max

# Maximal ordered partition demonstration
if __name__ == '__fake_news__':
    NUM_POINTS =        int(sys.argv[1]) or 3          # N
    PARTITION_SIZE =    int(sys.argv[2]) or 2          # T
    POWER =             float(sys.argv[3]) or 2.2      # gamma
    PRIORITY_POWER =    float(sys.argv[4]) or 1.0      # tau

    NUM_WORKERS = min(NUM_POINTS, multiprocessing.cpu_count() - 1)
    
    num_partitions = Bell_n_k(NUM_POINTS, PARTITION_SIZE)
    num_mon_partitions = _Mon_n_k(NUM_POINTS, PARTITION_SIZE)
    partitions = knuth_partition(range(0, NUM_POINTS), PARTITION_SIZE)
    
    slices = slice_partitions(partitions)

    trial = 0
    bad_cases = 0
    while True:
        # a0 = rng.choice(range(1,11), NUM_POINTS, True)
        # b0 = rng.choice(range(1,11), NUM_POINTS, True)

        # XXX
        a0 = rng.uniform(low=-10.0, high=10.0, size=int(NUM_POINTS))
        b0 = rng.uniform(low=0., high=10.0, size=int(NUM_POINTS))

        # XXX
        a0 = np.round(a0, 2)
        b0 = np.round(b0, 2)
        
        a0 = np.round(a0, 8)
        b0 = np.round(b0, 8)

        # a0 = np.array([8, 2, 9])
        # b0 = np.array([8, 1, 3])
        
        # gamma == 2.0, lambda > 1.0
        # x = 2.
        # delta = 1.
        # a0 = np.array([x-delta, delta, x+delta])
        # b0 = np.array([x, delta, x])

        # delta = 1
        # a0 = np.array([delta, 2*delta, 3*delta])
        # b0 = np.array([1, 1, 1])

        # gamma < 2.0
        # q = 1
        # epsilon = 1e-3
        # x = 1
        # b0 = np.array([1./(q*x+epsilon), 1./(q*epsilon), 1./(q*x-epsilon)])
        # a0 = np.array([1./x, 1./epsilon, 1./x])

        # a0 = np.array([-5.64313, -5.11986,  9.99038,  1.93718])
        # b0 = np.array([0.0772588, 1.22881  , 3.35838  , 0.0288292])

        # a0 = np.array([-5.64, -5.12,  10.0,  1.94])
        # b0 = np.array([0.077, 1.23, 3.36, 0.029])

        # a0 = np.array([ 0.37, 0.17, 0.50 ])
        # b0 = np.array([ 0.87, 0.37, 0.39 ])

        # a0 = np.array( [ 0.267532, 0.179856, 0.068246, 0.4343, 0.92863 ])
        # b0 = np.array( [ 0.6126, 0.312329, 0.090831, 0.566307, 0.566294 ] )
        # a0 = np.array([0.992819, 0.04904, 0.622353, 0.464107, 0.608956, 0.984192])
        # b0 = np.array([0.935323, 0.02541, 0.279373, 0.205452, 0.24599, 0.315633])
        # a0 = np.array([ -0.937353, -0.09833699999999999, -0.668365, 0.731261 ])
        # b0 = np.array([ 0.267252, 0.09030100000000001, 0.811923, 0.91252 ])
        # a0 = np.array([ 0.445962, 0.105416, 0.905763, 0.919112 ])
        # b0 = np.array([ 0.616067, 0.092109, 0.702833, 0.642663 ])
        # a0 = np.array([ 0.96563, 0.530856, 0.446896, 0.748362, 0.438265 ])
        # b0 = np.array([ 0.896815, 0.473519, 0.374769, 0.142674, 0.039357 ])
        # (4,3) case
        # a0 = np.array([ 0.772736, 0.523752, 0.858158, 0.120438 ])
        # b0 = np.array([ 0.378871, 0.210641, 0.256059, 0.032089 ])
        # (4,3) mixed-sign case
        # a0 = np.array([ -0.649362, -0.546916, -0.661853, 0.863409 ])
        # b0 = np.array([ 0.14663, 0.445009, 0.605386, 0.441687 ])
        # a0 = np.array([-9.9525, -9.5814, -0.42452918,  4.4462,  9.2472])
        # b0 = np.array([5.8318, 5.7728, 0.5, 8.1294, 9.2019])
        # (4, 3, 4) case
        # a0 = np.array([-5.554 , -2.501 , -4.9577, -6.0844])
        # b0 = np.array([1.3083, 1.6324, 3.5354, 6.7042])
                      
        # a0 = np.array([.75, .25, 1.25])
        # b0 = np.array([1, .25, 1])

        sortind = np.argsort(a0**PRIORITY_POWER/b0)
        a0 = a0[sortind]
        b0 = b0[sortind]

        r_max_raw = optimize(a0, b0, PARTITION_SIZE, POWER, NUM_WORKERS, PRIORITY_POWER)
        vert_const_asym, vert_const_sym, vert_ext_asym, vert_ext_sym = plot_polytope(a0, b0, show_plot=False)

        # if True or len(vert_const_sym) != (0 + len(vert_ext_sym)):
        # if len(vert_const_sym) > 2*(len(a0)+2):
        #     vert_const_asym, vert_const_sym, vert_ext_asym, vert_ext_sym = plot_polytope(a0, b0, show_plot=True)
        #     import pdb
        #     pdb.set_trace()

        # a0 = -1 * a0
        # r_max_neg = optimize(a0, b0, PARTITION_SIZE, POWER, NUM_WORKERS, PRIORITY_POWER)

        # if (len(vert_ext_sym) > 2*len(a0)) or True:
        #     import pdb
        #     pdb.set_trace()

        # if (np.sum(a0)**POWER/np.sum(b0)) > r_max_raw[0]:
        #     vert_const_asym, vert_const_sym, vert_ext_asym, vert_ext_sym = plot_polytope(a0, b0, show_plot=True)
        #     import pdb
        #     pdb.set_trace()
        
        if False:
            print('TRIAL: {} : max_raw: {:4.6f} pttn: {!r}'.format(trial, *r_max_raw))

        def F_orig(x, y, gamma):
            return np.sum(x)**gamma/np.sum(y)
        def F_symmetric(x, y, Cx, Cy, gamma):
            if np.sum(x) == Cx:
                return F_orig(Cx, Cy, gamma)
            else:
                return np.sum(x)**gamma/np.sum(y) + (Cx-np.sum(x))**gamma/(Cy-np.sum(y))

        # if (np.dot(dF_orig(np.sum(a0), np.sum(b0), POWER), (-a0[0], -b0[0])) < 0) and \
        #    (np.dot(dF_orig(np.sum(a0), np.sum(b0), POWER), (-a0[-1], -b0[-1])) < 0):
            # if (2*a0[0] - b0[0]*(np.sum(a0)/np.sum(b0)) > 0):
        # if ((b0[-1]*(np.sum(a0)/np.sum(b0)) - 2*a0[-1]) > 0):
        #     vert_const_asym, vert_const_sym, vert_ext_asym, vert_ext_sym = plot_polytope(a0, b0, show_plot=True)
        #     import pdb
        #     pdb.set_trace()

        all_scores = [(i,F_orig(a0[:i], b0[:i], POWER)) for i in range(1,len(a0))] + \
        [(i,F_orig(a0[i:], b0[i:], POWER)) for i in range(1,len(a0))] + \
        [(len(a0),F_orig(a0, b0, POWER))]
        all_sym_scores = [(i, F_orig(a0[:i], b0[:i], POWER) + F_orig(a0[i:], b0[i:], POWER))
                          for i in range(1,len(a0))] + \
                          [(len(a0), F_orig(a0, b0, POWER))]
        # if not all((any(set(s).issubset(set(ss)) for ss in optim_all[PARTITION_SIZE-2][1]) for s in optim_all[PARTITION_SIZE-1][1])):

        # vert_const_asym, vert_const_sym, vert_ext_asym, vert_ext_sym = plot_polytope(a0, b0, show_plot=False)
        
        # if np.argmax(all_scores) == (len(all_scores)-1):            
        # if min(all_sym_scores, key=lambda x:x[1])[0] != len(a0):
        # if max(all_sym_scores, key=lambda x:x[1])[0] == len(all_sym_scores):
        #     optim_all = [optimize(a0, b0, i, POWER, NUM_WORKERS, PRIORITY_POWER) for i in range(1, 1+len(a0))]
        #     vert_const_asym, vert_const_sym, vert_ext_asym, vert_ext_sym = plot_polytope(a0, b0, show_plot=True)            
        #     import pdb
        #     pdb.set_trace()
        #     if len(set(vert_const_sym).difference(set(vert_ext_sym))) ==  0:
        #         vert_const_asym, vert_const_sym, vert_ext_asym, vert_ext_sym = plot_polytope(a0, b0, show_plot=True)

        # optim_all = [optimize(a0, b0, i, POWER, NUM_WORKERS, PRIORITY_POWER) for i in range(1, 1+len(a0))]

        # Condition B, to test when T >= 3
        # optim_all = [optimize(a0, b0, i, POWER, NUM_WORKERS, PRIORITY_POWER) for i in range(1, 1+len(a0))]        
        # if not all((any(set(s).issubset(set(ss)) for ss in optim_all[PARTITION_SIZE-2][1]) for s in optim_all[PARTITION_SIZE-1][1])):
        #     vert_const_asym, vert_const_sym, vert_ext_asym, vert_ext_sym = plot_polytope(a0, b0, show_plot=True)                
        #     import pdb
        #     pdb.set_trace()
        

        try:
            assert all(np.diff(list(chain.from_iterable(r_max_raw[1]))) == 1)
        except AssertionError as e:
            # if ((a0>0).all() or (a0<0).all()):
            #     continue
            # if any([len(x)==1 for x in r_max_abs[1]]):
            #     continue
            
            # r_max_raw_minus_1 = optimize(a0, b0, PARTITION_SIZE-1, POWER, NUM_WORKERS, PRIORITY_POWER)

            # Stop if exception found
            # optim_all = [optimize(a0, b0, i, POWER, NUM_WORKERS, PRIORITY_POWER) for i in range(1, 1+len(a0))]
            # if len(set(vert_const_sym).difference(set(vert_ext_sym))) ==  0:
            # if np.argmax(all_scores) == (len(all_scores)-1):
            #     import pdb
            #     pdb.set_trace()

            # Condition A, to test when T >= 3
            # if not all([all(a0[s] > 0) or all(a0[s] < 0) for s in optim_all[PARTITION_SIZE-2][1]]):
            #     vert_const_asym, vert_const_sym, vert_ext_asym, vert_ext_sym = plot_polytope(a0, b0, show_plot=True)                
            #     import pdb
            #     pdb.set_trace()
            
            # if not all([all(a0[s] > 0) or all(a0[s] < 0) for s in r_max_raw[1]]):
            #     vert_const_asym, vert_const_sym, vert_ext_asym, vert_ext_sym = plot_polytope(a0, b0, show_plot=True)                
            #     import pdb
            #     pdb.set_trace()

            # Condition B, to test when T >= 3
            # if not all((any(set(s).issubset(set(ss)) for ss in optim_all[PARTITION_SIZE-2][1]) for s in optim_all[PARTITION_SIZE-1][1])):
            #     vert_const_asym, vert_const_sym, vert_ext_asym, vert_ext_sym = plot_polytope(a0, b0, show_plot=True)                
            #     import pdb
            #     pdb.set_trace()

            delFdelX = 4*(np.sum(a0)**3)/np.sum(b0)
            delFdelY = -(np.sum(a0)**4)/(np.sum(b0)**2)
            mu2 = (-a0[-1]*delFdelX - b0[-1]*delFdelY)
            mu1 = (-a0[0]*delFdelX - b0[0]*delFdelY)

            if max(all_sym_scores, key=lambda x:x[1])[0] != len(all_sym_scores) or True:
                optim_all = [optimize(a0, b0, i, POWER, NUM_WORKERS, PRIORITY_POWER) for i in range(1, 1+len(a0))]
                vert_const_asym, vert_const_sym, vert_ext_asym, vert_ext_sym = plot_polytope(a0, b0, show_plot=True)
                import pdb
                pdb.set_trace()

            # print('FOUND')
            # if (mu1 >0) or (mu2 > 0):
            #     import pdb
            #     pdb.set_trace()

            # r_max_raw_less = optimize(a0, b0, PARTITION_SIZE-1, POWER, NUM_WORKERS, PRIORITY_POWER)
            # if (r_max_raw[0] > r_max_raw_less[0]) or (not all(np.diff(list(chain.from_iterable(r_max_raw_less[1]))))):
            #     vert_const_asym, vert_const_sym, vert_ext_asym, vert_ext_sym = plot_polytope(a0, b0)
            #     import pdb
            #     pdb.set_trace()
                
            if False:
                if not os.path.exists('./violations'):
                    os.mkdir('./violations')
                with open('_'.join(['./violations/a', str(SEED),
                                    str(trial),
                                    str(PARTITION_SIZE)]), 'wb') as f:
                    pickle.dump(a0, f)
                with open('_'.join(['./violations/b', str(SEED),
                                    str(trial),
                                    str(PARTITION_SIZE)]), 'wb') as f:
                    pickle.dump(b0, f)
                with open('_'.join(['./violations/rmax', str(SEED),
                                    str(trial),
                                    str(PARTITION_SIZE)]), 'wb') as f:
                    pickle.dump(r_max_raw, f)
                bad_cases += 1
                if bad_cases == 10:
                    import sys
                    sys.exit()
    
        trial += 1

if (False):
#### Reconstruct ####
    import numpy as np
    def F(x,y):
        return np.sum(x)**2/np.sum(y)
    X1 = -3.70595
    Y1 = 0.106088
    X2 = 4.87052
    Y2 = 4.58719
    beta = 0.0772588
    alpha = -5.64313
    b = 3.35838
    a = 9.99038

    X1_val = X1
    Y1_val = Y1
    X2_val = X2
    Y2_val = Y2
    X1 = np.array([alpha, X1_val-alpha])
    Y1 = np.array([beta, Y1_val-beta])
    X2 = np.array([X2_val-a, a])
    Y2 = np.array([Y2_val-b, b])
    
    X1_m_alpha = X1[1:]
    Y1_m_beta  = Y1[1:]
    X1_p_a     = np.concatenate([X1, np.array([a])])
    Y1_p_b     = np.concatenate([Y1, np.array([b])])
    X2_p_alpha = np.concatenate([X2, np.array([alpha])])
    Y2_p_beta  = np.concatenate([Y2, np.array([beta])])
    X2_m_a     = X2[:-1]
    Y2_m_b     = Y2[:-1]
    X1_m_alpha_p_a = np.concatenate([X1_m_alpha, np.array([a])])
    Y1_m_beta_p_b = np.concatenate([Y1_m_beta, np.array([b])])
    X2_p_alpha_m_a = np.concatenate([X2[:-1], np.array([alpha])])
    Y2_p_beta_m_b = np.concatenate([Y2[:-1], np.array([beta])])
    
    assert (F(X1_m_alpha,Y1_m_beta)-F(X1,Y1)) > 0
    assert (F(X1_p_a,Y1_p_b)-F(X1,Y1)) < 0
    assert (F(X2_p_alpha,Y2_p_beta)-F(X2,Y2)) < 0
    assert (F(X2_m_a,Y2_m_b)-F(X2,Y2)) > 0
    
    top_row = F(X1_m_alpha,Y1_m_beta)+F(X2_p_alpha,Y2_p_beta)-F(X1,Y1)-F(X2,Y2)
    bot_row = F(X1_p_a,Y1_p_b)+F(X2_m_a,Y2_m_b)-F(X1,Y1)-F(X2,Y2)
    plus_minus = F(X1_m_alpha_p_a,Y1_m_beta_p_b)+F(X2_p_alpha_m_a,Y2_p_beta_m_b)-F(X1,Y1)-F(X2,Y2)

    a0 = np.array([X1[0], X2[0], X2[1], X1[1]])
    b0 = np.array([Y1[0], Y2[0], Y2[1], Y1[1]])

if (False):
    import numpy as np

    # gamma == 2.0, lambda > 1.0
    x = 1e6
    delta = 10.01
    theta = 2.0
    gamma = 2.0
    a0 = np.array([x-delta, delta, x+delta])
    b0 = np.array([x, delta, x])

    sortind = np.argsort(a0**theta/b0)
    a = a0[sortind]
    b = b0[sortind]

    part0 = [[0],[1,2]]
    part1 = [[0,1],[2]]
    part2 = [[0,2],[1]]

    sum([np.sum(a[part])**gamma/np.sum(b[part]) for part in part0])

if (False):
    import numpy as np
    import matplotlib.pyplot as plot
    
    gamma = 2.0
    delta = 1e-1
    C1 = 2+delta
    C2 = 2+delta
    epsilon = delta/2

    def F(x,y,gamma):
        return x**gamma/y + (C1-x)*gamma/(C2-y)

    xaxis = np.linspace(0.01, 2+delta-epsilon, 1000)
    yaxis = np.linspace(0.25, 2+delta-epsilon, 1000)
    X,Y = np.meshgrid(xaxis, yaxis)
    Z = F(X,Y,gamma)

    fig,ax = plot.subplots(1,1)
    cp = ax.contourf(X, Y, Z)
    fig.colorbar(cp)
    plot.show()

if (False):
    import numpy as np

    count = 0
    
    rng = np.random.RandomState(552)
    while True:
        NUM_POINTS = rng.choice(10)+2
        upper_limit_a = rng.uniform(low=0., high=1000.)
        upper_limit_b = rng.uniform(low=0., high=1000.)
        a0 = rng.uniform(low=0.000001, high=upper_limit_a, size=NUM_POINTS)
        b0 = rng.uniform(low=0.000001, high=upper_limit_b, size=NUM_POINTS)

        a0 = np.round(a0,2)
        b0 = np.round(b0,2)
        
        sortind = np.argsort(a0/b0)
        a0 = a0[sortind]
        b0 = b0[sortind]

        # gamma = 2
        # delFdelX = 2*np.sum(a0)/np.sum(b0)
        # delFdelY = -(np.sum(a0)**2/np.sum(b0)**2)
        # gamma = 4
        delFdelX = 4*(np.sum(a0)**3)/np.sum(b0)
        delFdelY = -(np.sum(a0)**4)/(np.sum(b0)**2)
        # gamma = 6
        # delFdelX = 6*(np.sum(a0)**5)/np.sum(b0)
        # delFdelY = -(np.sum(a0)**6)/(np.sum(b0)**2)
        
        if (-a0[-1]*delFdelX - b0[-1]*delFdelY) > 0:
            if (-a0[0]*delFdelX - b0[0]*delFdelY) > 0:
                print('FOUND')
                
        count+=1
        if not count%100000:
            print('count: {}'.format(count))
        
    
if (False):
    import numpy as np
    import matplotlib.pyplot as plot

    gamma = 2.0
    count = 0

    def score(a,b,gamma):
        return np.sum(a)**gamma/np.sum(b)
    def all_scores(a,b,gamma):
        scores = [score(a[range(0,i)], b[range(0,i)], gamma) + score(a[range(i,len(a))],
                                                              b[range(i,len(a))], gamma)
                  for i in range(1,len(a))] + [score(a, b, gamma)]
        return scores
    
    rng = np.random.RandomState(553)
    while True:
        NUM_POINTS = rng.choice(1000)+2 # so that len(a0) >= 2
        upper_limit_a = rng.uniform(low=-1000., high=1000.)
        upper_limit_b = rng.uniform(low=0., high=1000.)
        a0 = rng.uniform(low=0.000001, high=upper_limit_a, size=NUM_POINTS)
        b0 = rng.uniform(low=0.000001, high=upper_limit_b, size=NUM_POINTS)
        
        sortind = np.argsort(a0/b0)
        a0 = a0[sortind]
        b0 = b0[sortind]

        ind = range(0,len(a0))

        # Symmetric case
        scores = all_scores(a0,b0,gamma)

        # plot.plot(scores)
        # plot.pause(1e-3)
        # import pdb
        # pdb.set_trace()
        # plot.close()

        if np.argmax(scores) == len(a0)-1:
            print('FOUND')
            print(a0)
            print(b0)
            
if (False):
    import numpy as np

    count = 0
    
    rng = np.random.RandomState(552)
    while True:
        NUM_POINTS = rng.choice(10)+2
        upper_limit_a = rng.uniform(low=-1000., high=1000.)
        upper_limit_b = rng.uniform(low=0., high=1000.)
        a0 = rng.uniform(low=0.000001, high=upper_limit_a, size=NUM_POINTS)
        b0 = rng.uniform(low=0.000001, high=upper_limit_b, size=NUM_POINTS)

        sortind = np.argsort(a0/b0)
        a0 = a0[sortind]
        b0 = b0[sortind]

        lhs1 = (a0[0]/b0[0])
        lhs2 = (a0[-1]/b0[-1])
        rhs = np.sum(a0)/np.sum(b0)

        # print("( ",lhs,", ",rhs," )")
        
        if (lhs1 > rhs) or (lhs2 < rhs):
            print('FOUND')
            print("( ",lhs,", ",rhs," )")

if (False):
    import numpy as np

    count = 0
    
    rng = np.random.RandomState(552)
    while True:
        NUM_POINTS = 5
        k = 3
        l = 4
        upper_limit_a = rng.uniform(low=0., high=1000.)
        upper_limit_b = rng.uniform(low=0., high=1000.)
        a0 = rng.uniform(low=0.000001, high=upper_limit_a, size=NUM_POINTS)
        b0 = rng.uniform(low=0.000001, high=upper_limit_b, size=NUM_POINTS)

        sortind = np.argsort(a0/b0)
        a0 = a0[sortind]
        b0 = b0[sortind]

        xk = a0[k]
        yk = b0[k]
        Cxl = np.sum(a0[:l])
        Cyl = np.sum(b0[:l])
        Cxkm1 = np.sum(a0[:(k-1)])
        Cykm1 = np.sum(b0[:(k-1)])

        s1 = ((xk/yk)-(Cxl/Cyl))*yk*Cyl
        s2 = ((xk/yk)-(Cxkm1/Cykm1))*yk*Cykm1
        if (s1-s2)>0:
            print(a0)
            print(b0)
                    
if (False):
    import numpy as np

    count = 0

    gamma = 2.0

    def F(a,b,gamma):
        return np.sum(a)**gamma/np.sum(b)

    # def F(a,b,gamma):
    #     return np.log(np.sum(a))/np.sum(b)
    
    rng = np.random.RandomState(847)
    while True:
        NUM_POINTS = 10
        a0 = rng.uniform(low=0., high=100., size=NUM_POINTS)
        b0 = rng.uniform(low=0., high=1., size=NUM_POINTS)

        sortind = np.argsort(a0/b0)
        a0 = a0[sortind]
        b0 = b0[sortind]

        # lhs = F(a0, b0, gamma)
        # rhs = F(a0[0], b0[0], gamma) + F(a0[1], b0[1], gamma)
        lhs = F(a0, b0, gamma)
        rhs = F(a0[0], b0[0], gamma)

        import pdb
        pdb.set_trace()

        if lhs < rhs:
            print('FOUND')
            print("( ",lhs,", ",rhs," )")

        count += 1
        if not count%1000000:
            print('count: {}'.format(count))

if (False):
    import numpy as np

    count = 0
    gamma = 4.0

    def F(a,b,gamma):
        return np.sum(a)**gamma/np.sum(b)

    # def F(a,b,gamma):
    #     return np.log(np.sum(a))/np.sum(b)
    
    rng = np.random.RandomState(87)
    while True:
        NUM_POINTS = 5
        LEN_SUBSET = 3
        subind = rng.choice(NUM_POINTS, LEN_SUBSET, replace=False)
        minind = min(subind)
        maxind = max(subind)
        a0 = rng.uniform(low=-100., high=0., size=NUM_POINTS)
        b0 = rng.uniform(low=0., high=1., size=NUM_POINTS)

        sortind = np.argsort(a0/b0)
        a0 = a0[sortind]
        b0 = b0[sortind]

        lhs = b0[maxind]/a0[maxind]
        rhs = b0[minind]/a0[minind]
        mid = np.sum(b0[subind])/np.sum(a0[subind])

        if (lhs > mid) or (mid > rhs):
            print('FOUND')
            print(a0)
            print(b0)
            print(subind)
            print("( ",lhs,", ",rhs," )")

        count += 1
        if not count%1000000:
            print('count: {}'.format(count))
            
if (False):
    import numpy as np

    def score(a,b,gamma):
        return np.sum(a)**gamma/np.sum(b)
    
    def score_symmetric(x,y,i,gamma):
        Cx,Cy = np.sum(x), np.sum(y)
        return np.sum(x[:i])**gamma/np.sum(y[:i]) + (Cx-np.sum(x[:i]))**gamma/(Cy-np.sum(y[:i]))
    

    count = 0
    gamma = 2.0
    
    rng = np.random.RandomState(552)
    while True:
        NUM_POINTS = 2
        upper_limit_a = rng.uniform(low=-1000., high=1000.)
        upper_limit_b = rng.uniform(low=0., high=1000.)
        a0 = rng.uniform(low=0.000001, high=upper_limit_a, size=NUM_POINTS)
        b0 = rng.uniform(low=0.000001, high=upper_limit_b, size=NUM_POINTS)

        sortind = np.argsort(a0/b0)
        a0 = a0[sortind]
        b0 = b0[sortind]

        # Seed = 552
        # upper_limit_a = rng.uniform(low=-1000., high=1000.)
        # upper_limit_b = rng.uniform(low=0., high=1000.)
        # a0 = rng.uniform(low=0.000001, high=upper_limit_a, size=NUM_POINTS)
        # b0 = rng.uniform(low=0.000001, high=upper_limit_b, size=NUM_POINTS)        
        # a0 = np.array([-769.88725716, -261.39267287])
        # b0 = np.array([435.20909316, 147.76250352])

        if score(a0, b0, gamma) >= score_symmetric(a0,b0,1,gamma):
        # if (score(a0, b0, gamma) - score(a0[:-1], b0[:-1], gamma)) > score(a0[-1], b0[-1], gamma):
            print('FOUND')
            print(a0)
            print(b0)
    
        count+=1
        if not count%1000000:
            print('count: {}'.format(count))

if (False):
    import numpy as np

    def score(a,b,gamma):
        return np.sum(a)**gamma/np.sum(b)
    
    def score_symmetric(x,y,Cx,Cy,gamma):
        if ((np.sum(x) == Cx) and (np.sum(y) == Cy)) or ((np.sum(x) == 0.) and (np.sum(y) == 0.)):
            return Cx**gamma/Cy
        else:
            return np.sum(x)**gamma/np.sum(y) + (Cx-np.sum(x))**gamma/(Cy-np.sum(y))
    

    count = 0
    gamma = 2.0
    
    rng = np.random.RandomState(552)
    while True:
        NUM_POINTS = 3
        upper_limit_a = rng.uniform(low=-1000., high=1000.)
        upper_limit_b = rng.uniform(low=0., high=1000.)
        a0 = rng.uniform(low=0.000001, high=upper_limit_a, size=NUM_POINTS)
        b0 = rng.uniform(low=0.000001, high=upper_limit_b, size=NUM_POINTS)

        sortind = np.argsort(a0/b0)
        a0 = a0[sortind]
        b0 = b0[sortind]

        Cx,Cy = np.sum(a0), np.sum(b0)        

        # Seed = 552
        # upper_limit_a = rng.uniform(low=-1000., high=1000.)
        # upper_limit_b = rng.uniform(low=0., high=1000.)
        # a0 = rng.uniform(low=0.000001, high=upper_limit_a, size=NUM_POINTS)
        # b0 = rng.uniform(low=0.000001, high=upper_limit_b, size=NUM_POINTS)        
        # a0 = np.array([-769.88725716, -261.39267287])
        # b0 = np.array([435.20909316, 147.76250352])

        # Holds for gamma = 1.0
        # if (score(a0[[0,2]], b0[[0,2]], gamma) - score(a0[0], b0[0], gamma)) <= (score(a0, b0, gamma) - score(a0[[0,1]], b0[[0,1]], gamma)):
        if (score_symmetric(a0[[0,2]], b0[[0,2]], Cx, Cy, gamma) - score_symmetric(a0[0], b0[0], Cx, Cy, gamma)) <= (score_symmetric(a0, b0, Cx, Cy, gamma) - score_symmetric(a0[[0,1]], b0[[0,1]], Cx, Cy, gamma)):
            print('FOUND')
            print(a0)
            print(b0)

        count+=1
        if not count%1000000:
            print('count: {}'.format(count))

if (False):
    import numpy as np

    count = 0

    rng = np.random.RandomState(552)
    while True:

        NUM_POINTS = rng.choice(100)+2
        SPLIT_INDEX = np.max([rng.choice(NUM_POINTS-1), 2])
        
        upper_limit_a = rng.uniform(low=-1000., high=1000.)
        upper_limit_b = rng.uniform(low=-0., high=1000.)
        a0 = rng.uniform(low=-1*upper_limit_a, high=upper_limit_a, size=NUM_POINTS)
        b0 = rng.uniform(low=-0., high=upper_limit_b, size=NUM_POINTS)

        sortind = np.argsort(a0/b0)
        a0 = a0[sortind]
        b0 = b0[sortind]

        Cx,Cy = np.sum(a0), np.sum(b0)        


        # if (np.sum(a0[:SPLIT_INDEX])/np.sum(b0[:SPLIT_INDEX]) > np.sum(a0)/np.sum(b0)) or \
        #    (np.sum(a0)/np.sum(b0) > np.sum(a0[SPLIT_INDEX:])/np.sum(b0[SPLIT_INDEX:])):
        if (np.sum(a0[:-1+SPLIT_INDEX])/np.sum(b0[:-1+SPLIT_INDEX]) > np.sum(a0[:SPLIT_INDEX])/np.sum(b0[:SPLIT_INDEX])):
            print('FOUND')
            print(a0)
            print(b0)

        count+=1

        if not count%10000:
            print('count: {}'.format(count))

if (True):
    import numpy as np

    count = 0
    gamma = 4.0
    seed = 146
    
    def F_noy(a,b,gamma):
        return np.sum(a)**gamma
    
    def F(a,b,gamma):
        return np.sum(a)**gamma/np.sum(b)

    def F_sym(a,b,Cx,Cy,gamma):
        if (np.sum(a) == Cx) or (np.sum(a) == 0.) or (np.sum(b) == Cy) or (np.sum(b) == 0):
            return Cx**gamma/Cy
            # return np.sum(a)**gamma/np.sum(b)
        else:
            return (np.sum(a)**gamma/np.sum(b)) + ((Cx-np.sum(a))**gamma/(Cy-np.sum(b)))
            # return np.sum(a)**gamma/np.sum(b)

    rng = np.random.RandomState(seed)
    while True:

        NUM_POINTS = 4

        j = np.max([rng.choice(int(NUM_POINTS/2)), 2])
        k = rng.choice(int(NUM_POINTS/2)) + int(NUM_POINTS/2) + 1
        j,k,l = np.sort(rng.choice(int(NUM_POINTS), 3, replace=False))
        
        # l,m,n,o = np.sort(rng.choice(int(NUM_POINTS), 4, replace=False))
        # l,m = np.sort(rng.choice(int(NUM_POINTS), 2, replace=False))
        # n,o = np.sort(rng.choice(int(NUM_POINTS), 2, replace=False))

        upper_limit_a = rng.uniform(low=0., high=100.)
        upper_limit_b = rng.uniform(low=0., high=100.)
        a0 = rng.uniform(low=-0., high=upper_limit_a, size=NUM_POINTS)
        b0 = rng.uniform(low=-0., high=upper_limit_b, size=NUM_POINTS)


        # a0 = np.round(a0, 0)
        # b0 = np.round(b0, 0)
        sortind = np.argsort(a0/b0)
        a0 = a0[sortind]
        b0 = b0[sortind]
        Cx = np.sum(a0)
        Cy = np.sum(b0)

        # STRONG SUBMODULARITY
        # ====================
        # Submodularity : (lhs1+lhs2) >= (rhs1+rhs2) => submodular
        # sets = subsets(NUM_POINTS)
        # m,n = rng.choice(len(sets), 2, replace=False)
        # lset, rset = sets[m][0], sets[n][0]
        # l_r_int = list(set(lset).intersection(set(rset)))
        # l_r_union = list(set(lset).union(set(rset)))
        # lhs1 = F(a0[lset], b0[lset], gamma)
        # lhs2 = F(a0[rset], b0[rset], gamma)
        # rhs1 = F(a0[l_r_union], b0[l_r_union], gamma)
        # rhs2 = F(a0[l_r_int], b0[l_r_int], gamma)
        # print('lset: {}'.format(lset))
        # print('rset: {}'.format(rset))
        # print('l_r_int: {}'.format(l_r_int))
        # print('l_r_union: {}'.format(l_r_union))
        # print('=====')

        # CONSECUTIVE SUBMODULARITY
        # =========================
        # Weak submodularity : (lhs1+lhs2) >= (rhs1+rhs2) => weakly submodular
        # XXX
        # inequality flips for gamma=2 when replacing F with F_noy;
        # F is weakly submodular, F_noy is weakly supermodular
        # F is subadditive, hence weakly subadditive, but
        # F_noy is superadditive
        # lhs1 = F(a0[j:(k+1)],b0[j:(k+1)],gamma)
        # lhs2 = F(a0[(j+1):(k+2)],b0[(j+1):(k+2)],gamma)
        # rhs1 = F(a0[j:(k+2)],b0[j:(k+2)],gamma)
        # rhs2 = F(a0[(j+1):(k+1)],b0[(j+1):(k+1)],gamma)

        # CONSECUTIVE SUBMODULARITY
        # =========================
        # Another version of weak submodularity : (lhs1+lhs2) >= (rhs1+rhs2) => weakly submodular
        # j,k = np.sort(rng.choice(int(NUM_POINTS+1), 2, replace=False))
        # l,m = np.sort(rng.choice(int(NUM_POINTS+1), 2, replace=False))
        # lset, rset = set(range(j,k)), set(range(l,m))
        # l_r_int = lset.intersection(rset)
        # l_r_union = lset.union(rset)
        # lset, rset, l_r_int, l_r_union = list(lset), list(rset), list(l_r_int), list(l_r_union)
        # lhs1 = F(a0[lset], b0[lset], gamma)
        # lhs2 = F(a0[rset], b0[rset], gamma)
        # rhs1 = F(a0[l_r_union], b0[l_r_union], gamma)
        # rhs2 = F(a0[l_r_int], b0[l_r_int], gamma)
        # print('lset: {}'.format(lset))
        # print('rset: {}'.format(rset))
        # print('l_r_int: {}'.format(l_r_int))
        # print('l_r_union: {}'.format(l_r_union))
        # print(lhs1+lhs2,rhs1+rhs2)
        # print(j,k,l,m)
        # print('========')

        # CONSECUTIVE SUBMODULARITY
        # =========================
        # Yet another version of weak submodularity : (lhs1+lhs2) >= (rhs1+rhs2) => weakly submodular
        # j,k,l,m = np.sort(rng.choice(int(NUM_POINTS+1), 4, replace=False))
        # lhs1 = F(a0[j:l], b0[j:l], gamma)
        # lhs2 = F(a0[k:m], b0[k:m], gamma)
        # rhs1 = F(a0[j:m], b0[j:m], gamma)
        # rhs2 = F(a0[k:l], b0[k:l], gamma)
 
        # CONSECUTIVE NONSPLITTIGN SUBMODULARITY
        # ======================================
        i,j = np.sort(rng.choice(int(NUM_POINTS), 2, replace=False))
        fb1,fb2 = rng.choice(2, 2, replace=True)
        lset = set(range(0,i+1)) if fb1 else set(range(i,NUM_POINTS))
        rset = set(range(0,j+1)) if fb2 else set(range(j,NUM_POINTS))
        l_r_int = lset.intersection(rset)
        l_r_union = lset.union(rset)
        lset,rset,l_r_int,l_r_union = list(lset),list(rset),list(l_r_int),list(l_r_union)
        lhs1 = F(a0[lset], b0[lset], gamma)
        lhs2 = F(a0[rset], b0[rset], gamma)
        rhs1 = F(a0[l_r_union], b0[l_r_union], gamma)
        rhs2 = F(a0[l_r_int], b0[l_r_int], gamma) if l_r_int else 0.
        print('i,j: ({},{})'.format(i,j))
        print('lset: {}'.format(lset))
        print('rset: {}'.format(rset))
        print('l_r_int: {}'.format(l_r_int))
        print('l_r_union: {}'.format(l_r_union))
        print(lhs1+lhs2,rhs1+rhs2)
        print('=====')
                      
       
                
        # Subadditivity : (lhs1+lhs2) >= (rhs1+rhs2)
        # sets = subsets(NUM_POINTS)
        # m,n = rng.choice(len(sets), 2, replace=False)
        # lset, rset = sets[m][0], sets[n][0]
        # rset = list(set(rset).difference(set(lset)))
        # l_r_union = list(set(lset).union(set(rset)))
        # lhs1 = F(a0[lset], b0[lset], gamma)
        # lhs2 = F(a0[rset], b0[rset], gamma)
        # rhs1 = F(a0[l_r_union], b0[l_r_union], gamma)
        # rhs2 = 0.
        # lhs1 = F_sym(a0[lset], b0[lset], Cx, Cy, gamma)
        # lhs2 = F_sym(a0[rset], b0[rset], Cx, Cy, gamma)
        # rhs1 = F_sym(a0[l_r_union], b0[l_r_union], Cx, Cy, gamma)
        # rhs2 = 0.

        # Weak subadditivity : (lhs1+lhs2) >= (rhs1+rhs2)
        # Subadditivity of F_sym irrelelvant
        # lhs1 = F_sym(a0[j:k],b0[j:k],Cx,Cy,gamma)
        # lhs2 = F_sym(a0[k:l],b0[k:l],Cx,Cy,gamma)
        # rhs1 = F_sym(a0[j:l],b0[j:l],Cx,Cy,gamma)
        # rhs2 = 0.
        # lhs1 = F(a0[j:k],b0[j:k],gamma)
        # lhs2 = F(a0[k:l],b0[k:l],gamma)
        # rhs1 = F(a0[j:l],b0[j:l],gamma)
        # rhs2 = 0.

        # Quasiconvexity - note this is not a property of the set function,
        # but of the function defined on R x R+
        # j,k = rng.choice(range(2, int(NUM_POINTS)), 2, replace=False)
        # x1,y1 = np.sum(a0[:j]), np.sum(b0[:j])
        # x2,y2 = np.sum(a0[:k]), np.sum(b0[:k])
        # For F
        # if F(x1,y1,gamma) >= F(x2,y2,gamma):
        #     x1_tmp = x1
        #     y1_tmp = y1
        #     x1 = x2
        #     y1 = y2
        #     x2 = x1_tmp
        #     y2 = y1_tmp
        # lhs1 = (gamma - 1 - gamma*(x1/x2) + (y1/y2))*F(x2,y2,gamma)
        # lhs2 = 0.
        # rhs1 = 0.
        # rhs2 = 0.

        # For F_sym
        # if F_sym(x1,y1,Cx,Cy,gamma) >= F_sym(x2,y2,Cx,Cy,gamma):
        #     x1_tmp = x1
        #     y1_tmp = y1
        #     x1 = x2
        #     y1 = y2
        #     x2 = x1_tmp
        #     y2 = y1_tmp
        # XXX
        # lhs1 = (gamma - 1 - gamma*(x1/x2) + (y1/y2))*F(x2,y2,gamma)
        # lhs2 = (gamma*(x1/(Cx-x2)) - gamma*(x2/(Cx-x2)) + (y2/(Cy-y2)) - (y1/(Cy-y2)))*F(Cx-x2,Cy-y2,gamma)
        # rhs1 = 0.
        # rhs2 = 0.

        if ((lhs1+lhs2)<(rhs1+rhs2)) and not np.isclose(lhs1+lhs2, rhs1+rhs2):
        # if not np.isclose(lhs1+lhs2, rhs1+rhs2):
            print('FOUND')
            print(lhs1+lhs2)
            print(rhs1+rhs2)
            print('a0: ', a0)
            print('b0: ', b0)
            # import pdb
            # pdb.set_trace()
            sys.exit()

        count+=1

        if not count%10:
            print('count: {}'.format(count))
    
if (False):
    import numpy as np

    count = 0
    gamma = 4.0
    
    rng = np.random.RandomState(552)
    while True:
        NUM_POINTS = 2
        upper_limit_a = rng.uniform(low=0., high=1000.)
        upper_limit_b = rng.uniform(low=0., high=1000.)
        a0 = rng.uniform(low=0.000001, high=upper_limit_a, size=NUM_POINTS)
        b0 = rng.uniform(low=0.000001, high=upper_limit_b, size=NUM_POINTS)

        sortind = np.argsort(a0/b0)
        a0 = a0[sortind]
        b0 = b0[sortind]

        lhs1 = (a0[0]**gamma/b0[0])
        lhs2 = (a0[-1]**gamma/b0[-1])
        rhs = np.sum(a0)**gamma/np.sum(b0)

        # print("( ",lhs,", ",rhs," )")

        if rhs > (lhs1+lhs2):
            print('FOUND')

import pandas as pd
import numpy as np
rng = np.random.RandomState(552)
NUM_ROWS = 1000
df = pd.DataFrame({'c1': rng.uniform(0., 1., NUM_ROWS), 'c2': rng.choice(list('ABC'),NUM_ROWS)})

def f1(df):
    return df[df['c1'] > 0.5][df.c2 == 'A']

def f2(df):
    return df[(df.c1 > 0.5) & (df.c2 == 'A')]

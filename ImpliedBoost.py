import numpy as np
from sklearn.datasets import make_classification, load_breast_cancer
from sklearn.model_selection import train_test_split

import classifier
import solver
import utils
from optimalsplitboost import OptimalSplitGradientBoostingClassifier

USE_SIMULATED_DATA = True
USE_01_LOSS = False
TEST_SIZE = 0.10

##########################
## Generate Random Data ##
##########################
if (USE_SIMULATED_DATA):
    SEED = 253
    NUM_SAMPLES = 75
    rng = np.random.RandomState(SEED)
    
    X,y = make_classification(random_state=SEED, n_samples=NUM_SAMPLES)
    X_train, X_test, y_train, y_test = train_test_split(X, y, test_size=TEST_SIZE)
##############################
## END Generate Random Data ##
##############################
else:
    data = load_breast_cancer()
    X, y = data.data, data.target
    X_train, X_test, y_train, y_test = train_test_split(X,y, test_size=TEST_SIZE)
if USE_01_LOSS:
    X_train = 2*X_train - 1
    X_test = 2*X_test - 1
    y_train = 2*y_train - 1
    y_test = 2*y_test - 1
#############################
## Generate Empirical Data ##
#############################


if __name__ == '__main__':
    num_steps = 30
    num_classifiers = num_steps
    min_partitions = 50
    max_partitions = 51

    import sklearn.tree
    # distiller = classifier.classifierFactory(sklearn.tree.DecisionTreeClassifier)
    distiller = classifier.classifierFactory(sklearn.tree.DecisionTreeRegressor)

    clf = OptimalSplitGradientBoostingClassifier(X_train,
                                                 y_train,
                                                 min_partition_size=min_partitions,
                                                 max_partition_size=max_partitions,
                                                 gamma=0.025,
                                                 eta=0.025,
                                                 num_classifiers=num_classifiers,
                                                 use_constant_term=False,
                                                 solver_type='linear_hessian',
                                                 learning_rate=0.55,
                                                 distiller=distiller,
                                                 use_monotonic_partitions=False,
                                                 shortest_path_solver=True
                                                 )

    clf.fit(num_steps)

    utils.oos_summary(clf, X_test, y_test)


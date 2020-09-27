import skopt
from xgboost import XGBRegressor
import pandas as pd

from hpo.hpo_metrics import root_mean_squared_error
import preprocessing as pp
from hpo.trial import Trial

# Loading data and preprocessing
FOLDER = r'C:\Users\Max\Documents\GitHub\housing_regression\datasets'
TRAIN_FILE = 'train.csv'
TEST_FILE = 'test.csv'
SAMPLE_SUB = 'sample_submission.csv'

train_raw = pp.load_data(FOLDER, TRAIN_FILE)
test_raw = pp.load_data(FOLDER, TEST_FILE)

X_train, y_train, X_val, y_val, X_test = pp.process(train_raw, test_raw, standardization=False, logarithmic=False,
                                                    count_encoding=False)

# Define HP-space according to the skopt library
space_rf = [skopt.space.Integer(1, 200, name='n_estimators'),
            skopt.space.Integer(1, 80, name='max_depth'),
            skopt.space.Integer(1, 30, name='min_samples_leaf'),
            skopt.space.Integer(2, 20, name='min_samples_split'),
            skopt.space.Categorical(['auto', 'sqrt'], name='max_features')]
# skopt.space.Real(0.1, 0.9, name='max_samples')

space_svr = [skopt.space.Real(low=1e-3, high=1e+3, name='C'),
             skopt.space.Categorical(['scale', 'auto'], name='gamma'),
             skopt.space.Real(low=1e-3, high=1e+0, name='epsilon')]

space_keras = [skopt.space.Categorical([.0005, .001, .005, .01, .1], name='init_lr'),
               skopt.space.Categorical([8, 16, 32, 64], name='batch_size'),
               skopt.space.Categorical(['cosine', 'constant'], name='lr_schedule'),
               skopt.space.Categorical(['relu', 'tanh'], name='layer1_activation'),
               skopt.space.Categorical(['relu', 'tanh'], name='layer2_activation'),
               skopt.space.Categorical([16, 32, 64, 128, 256, 512], name='layer1_size'),
               skopt.space.Categorical([16, 32, 64, 128, 256, 512], name='layer2_size'),
               skopt.space.Categorical([.0, .3, .6], name='dropout1'),
               skopt.space.Categorical([.0, .3, .6], name='dropout2')]

space_xgb = [skopt.space.Categorical(['gbtree', 'gblinear', 'dart'], name='booster'),
             skopt.space.Integer(1, 200, name='n_estimators'),
             skopt.space.Integer(1, 80, name='max_depth')]

# Setting for the trial
ML_AlGO = 'XGBoostRegressor'
N_RUNS = 2
N_FUNC_EVALS = 15  # Optimization budget is limited by the number of function evaluations (should be dividable by 3 for
# BOHB and HB to ensure comparability)
N_WORKERS = 1
# OPT_Schedule = [('optuna', 'TPE'), ('optuna', 'CMA-ES'), ('optuna', 'RandomSearch'),
# ('skopt', 'SMAC'), ('skopt', 'GPBO'), ('hpbandster', 'BOHB'), ('hpbandster', 'Hyperband'), ('RoBO', 'Fabolas'),
# ('RoBO', 'Bohamiann')]
OPT_Schedule = [('optuna', 'RandomSearch')]
# Create a new trial
trial = Trial(hp_space=space_xgb, ml_algorithm=ML_AlGO, optimization_schedule=OPT_Schedule, metric=root_mean_squared_error, n_runs=N_RUNS,
              n_func_evals=N_FUNC_EVALS, n_workers=N_WORKERS, x_train=X_train, y_train=y_train, x_val=X_val,
              y_val=y_val)

# Run the optimizations
res = trial.run()

# Analyze the results
curves = trial.plot_learning_curve(res)
curves.show()

print(trial.get_best_trial_result(res))

metrics = trial.get_metrics(res)

bla = 0

# # Train best model on the whole data set
# x_data = pd.concat(objs=[X_train, X_val], axis=0)
# y_data = pd.concat(objs=[y_train, y_val], axis=0)
#
# best_trial = trial.get_best_trial_result(res)
#
# best_model = XGBRegressor(**best_trial['HP-configuration'])
# best_model.fit(x_data, y_data)
#
# y_pred = best_model.predict(X_test)
#
# sample_submission = pp.load_data(folder=FOLDER, file=SAMPLE_SUB)
# this_submission = sample_submission.copy()
#
# this_submission['SalePrice'] = y_pred
# this_submission.to_csv(r'C:\Users\Max\Documents\GitHub\housing_regression\datasets\submission.csv')

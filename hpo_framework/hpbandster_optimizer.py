import time
import hpbandster.core.nameserver as hpns
from hpbandster.optimizers import BOHB
from hpbandster.optimizers import HyperBand
import hpbandster.core.result as hpres
import pandas as pd
from multiprocessing import Process
import skopt

from hpo_framework.baseoptimizer import BaseOptimizer
from hpo_framework.results import TuningResult
from hpo_framework.hpbandster_worker import HPBandsterWorker
from hpo_framework import multiproc_target_funcs


class HpbandsterOptimizer(BaseOptimizer):
    def __init__(self, hp_space, hpo_method, ml_algorithm, x_train, x_test, y_train, y_test, metric, n_func_evals,
                 random_seed, n_workers, do_warmstart, cross_val, shuffle, is_time_series):
        super().__init__(hp_space, hpo_method, ml_algorithm, x_train, x_test, y_train, y_test, metric, n_func_evals,
                         random_seed, n_workers, cross_val, shuffle, is_time_series)

        self.do_warmstart = do_warmstart

    def optimize(self) -> TuningResult:
        """
        Method performs a hyperparameter optimization run according to the selected HPO-method.
        :return: result: TuningResult
            TuningResult-object that contains the results of this optimization run.
        """

        # Start a nameserver
        NS = hpns.NameServer(run_id='hpbandster', host='127.0.0.1', port=None)
        NS.start()

        # Logging of the optimization results
        result_logger = hpres.json_result_logger(directory='./hpo/hpbandster_logs', overwrite=True)

        # Optimize on the predefined n_func_evals and measure the wall clock times
        start_time = time.time()
        self.times = []  # Initialize a list for saving the wall clock times

        # Use a warm start configuration
        if self.do_warmstart == 'Yes':

            try:

                # Initialize a dictionary for saving the warmstart configuration
                warmstart_dict = {}

                # Retrieve the warmstart hyperparameters for the ML-algorithm
                warmstart_params = self.get_warmstart_configuration()

                # Iterate over all hyperparameters of this ML-algorithm's tuned HP-space and add them to the dictionary
                for i in range(len(self.hp_space)):

                    this_param = self.hp_space[i].name
                    this_warmstart_value = warmstart_params[this_param]

                    # For some HPs (e.g. max_depth of RF) the default value is None, although their typical dtype is
                    # different (e.g. int)
                    if this_warmstart_value is None and type(self.hp_space[i]) == skopt.space.space.Integer:
                        # Try to impute these values by the mean value
                        this_warmstart_value = int(0.5 * (self.hp_space[i].low + self.hp_space[i].high))

                    # Add the warmstart value to the dictionary
                    warmstart_dict[this_param] = this_warmstart_value

                # Start a HPBandsterWorker to evaluate the warmstart configuration
                ws_worker = HPBandsterWorker(ml_algorithm=self.ml_algorithm, optimizer_object=self,
                                             nameserver='127.0.0.1', run_id='hpbandster')

                ws_worker.run(background=True)

                # Initialize the  optimizer / HPO-method
                if self.hpo_method == 'BOHB':
                    ws_optimizer = BOHB(configspace=HPBandsterWorker.get_warmstart_config(self.hp_space,
                                                                                          warmstart_dict),
                                        run_id='hpbandster',
                                        nameserver='127.0.0.1', min_budget=10, max_budget=10, eta=3.0,
                                        result_logger=result_logger)

                elif self.hpo_method == 'Hyperband':
                    ws_optimizer = HyperBand(configspace=HPBandsterWorker.get_warmstart_config(self.hp_space,
                                                                                               warmstart_dict),
                                             run_id='hpbandster',
                                             nameserver='127.0.0.1', min_budget=1, max_budget=10, eta=3.0,
                                             result_logger=result_logger)

                else:
                    raise Exception('Unknown HPO-method!')

                # Run the optimization / evaluation of the warmstart configuration
                # (only a single iteration / evaluation)
                _ = ws_optimizer.run(n_iterations=1)

                ws_optimizer.shutdown(shutdown_workers=True)

                # Load the results and pass them to the kwargs dictionary
                ws_results = hpres.logged_results_to_HBS_result(directory='./hpo/hpbandster_logs')
                kwargs = {'previous_result': ws_results}

                # Set flag to indicate that a warmstart took place
                did_warmstart = True

            except:
                print('Warmstarting hpbandster failed!')
                kwargs = {}

                # Set flag to indicate that NO warmstart took place
                did_warmstart = False

        # No warmstart requested
        else:
            kwargs = {}

            # Set flag to indicate that NO warmstart took place
            did_warmstart = False

        # No parallelization
        if self.n_workers == 1:
            # Start a worker
            worker = HPBandsterWorker(ml_algorithm=self.ml_algorithm, optimizer_object=self,
                                      nameserver='127.0.0.1', run_id='hpbandster')

            worker.run(background=True)

        # Process based parallelization - Start the workers
        elif self.n_workers > 1:
            processes = []
            for i in range(self.n_workers):
                p = Process(target=multiproc_target_funcs.initialize_worker,
                            args=(self.ml_algorithm, self, '127.0.0.1', 'hpbandster'))

                p.start()
                processes.append(p)

        # Run an optimizer
        # Select the specified HPO-tuning method
        if self.hpo_method == 'BOHB':
            eta = 3.0
            optimizer = BOHB(configspace=HPBandsterWorker.get_configspace(self.hp_space), run_id='hpbandster',
                             nameserver='127.0.0.1', min_budget=1, max_budget=10, eta=eta,
                             result_logger=result_logger, **kwargs)
            # Values for budget stages: https://arxiv.org/abs/1905.04970

        elif self.hpo_method == 'Hyperband':
            eta = 3.0
            optimizer = HyperBand(configspace=HPBandsterWorker.get_configspace(self.hp_space), run_id='hpbandster',
                                  nameserver='127.0.0.1', min_budget=1, max_budget=10, eta=eta,
                                  result_logger=result_logger, **kwargs)
            # Values for budget stages: https://arxiv.org/abs/1905.04970

        else:
            raise Exception('Unknown HPO-method!')

        # Start the optimization
        try:

            n_func_evals = self.n_func_evals

            n_iterations = int(n_func_evals / eta)
            if n_iterations < 1:
                n_iterations = 1

            res = optimizer.run(n_iterations=n_iterations, min_n_workers=self.n_workers)
            # Relation of budget stages, halving iterations and the number of evaluations:
            # https://arxiv.org/abs/1905.04970
            # number of function evaluations = eta * n_iterations
            run_successful = True

            # Check whether one of the evaluations failed (hpbandster continues the optimization procedure even if
            # the objective function cannot be evaluated)
            for config_key in res.data.keys():
                this_result = res.data[config_key].results

                for this_eval in this_result.keys():
                    this_success_flag = this_result[this_eval]['info']

                    # The run wasn't successful, if one of the evaluations failed
                    if not this_success_flag:
                        run_successful = False
                        break

        # Algorithm crashed
        except:
            # Add a warning here
            run_successful = False

        # Shutdown the optimizer and the server
        optimizer.shutdown(shutdown_workers=True)
        NS.shutdown()

        if self.n_workers > 1:
            # Join the processes (only for parallelization)
            for p in processes:
                p.join()

        # If the optimization run was successful, determine the optimization results
        if run_successful:

            # Extract the results and create an TuningResult instance to save them
            id2config = res.get_id2config_mapping()
            incumbent = res.get_incumbent_id()

            # Best hyperparameter configuration
            best_configuration = id2config[incumbent]['config']

            runs_df = pd.DataFrame(columns=['config_id#0', 'config_id#1', 'config_id#2', 'iteration', 'budget',
                                            'loss', 'timestamps [finished]', 'budget [%]'])
            all_runs = res.get_all_runs()

            # Iterate over all runs
            for i in range(len(all_runs)):
                this_run = all_runs[i]
                temp_dict = {'run_id': [i],
                             'config_id#0': [this_run.config_id[0]],
                             'config_id#1': [this_run.config_id[1]],
                             'config_id#2': [this_run.config_id[2]],
                             'iteration': this_run.config_id[0],
                             'budget': this_run.budget,
                             'loss': this_run.loss,
                             'timestamps [finished]': this_run.time_stamps['finished'],
                             'budget [%]': round(this_run.budget * 10, 2)}
                # alternatively: 'timestamps [finished]': this_run.time_stamps['finished']
                this_df = pd.DataFrame.from_dict(data=temp_dict)
                this_df.set_index('run_id', inplace=True)
                runs_df = pd.concat(objs=[runs_df, this_df], axis=0)

            # Sort according to the timestamps
            runs_df.sort_values(by=['timestamps [finished]'], ascending=True, inplace=True)

            losses = list(runs_df['loss'])
            best_val_loss = min(losses)
            evaluation_ids = list(range(1, len(losses) + 1))
            timestamps = list(runs_df['timestamps [finished]'])  # << hpbandster's capabilities for time measurement
            wall_clock_time = max(timestamps)
            budget = list(runs_df['budget [%]'])

            configurations = ()
            for i in range(len(losses)):
                this_config = (list(runs_df['config_id#0'])[i],
                               list(runs_df['config_id#1'])[i],
                               list(runs_df['config_id#2'])[i])

                configurations = configurations + (id2config[this_config]['config'],)

            # Compute the loss on the test set for the best found configuration
            test_loss = self.train_evaluate_ml_model(params=best_configuration, cv_mode=False, test_mode=True)

        # Run not successful (algorithm crashed)
        else:
            evaluation_ids, timestamps, losses, configurations, best_val_loss, best_configuration, wall_clock_time, \
                test_loss, budget = self.impute_results_for_crash()

        # Pass the results to a TuningResult-object
        result = TuningResult(evaluation_ids=evaluation_ids, timestamps=timestamps, losses=losses,
                              configurations=configurations, best_val_loss=best_val_loss,
                              best_configuration=best_configuration, wall_clock_time=wall_clock_time,
                              test_loss=test_loss, successful=run_successful, did_warmstart=did_warmstart,
                              budget=budget)

        return result

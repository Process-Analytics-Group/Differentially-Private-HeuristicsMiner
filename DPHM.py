# Standard Library Imports
import io
import random
from collections import Counter
from copy import deepcopy
from enum import Enum
from itertools import product
from tkinter import messagebox

# Third-Party Imports
import cairosvg
import graphviz
import numpy as np
from PIL import Image

# PM4Py Imports
import pm4py
from pm4py.algo.evaluation.generalization import algorithm as generalization_evaluator
from pm4py.algo.evaluation.simplicity import algorithm as simplicity_evaluator
from pm4py.objects.log.importer.xes import importer as xes_importer
from pm4py.statistics.attributes.log import get as log_attributes
from pm4py.util import exec_utils, xes_constants
from pm4py.util import xes_constants as xes
from pm4py.objects.dfg.utils import dfg_utils
from pm4py.visualization.petri_net import visualizer as pn_visualizer

# calculate()
from pm4py.algo.filtering.dfg.dfg_filtering import clean_dfg_based_on_noise_thresh
from pm4py.objects.heuristics_net import defaults
from pm4py.objects.heuristics_net.node import Node

# Type Checking (Conditional Import)
from typing import TYPE_CHECKING
if TYPE_CHECKING:
    from GUI import GUI as GUI


class DPHM:
    class Parameters(Enum):
        # Source: Based on and abbreviated from PM4PY
        ACTIVITY_KEY = 'pm4py:param:activity_key'

    class DPHeuristicsNet:
        # Source: Based on and abbreviated from PM4PY
        def __init__(self, frequency_dfg, activities=None, start_activities=None, end_activities=None,
                     activities_occurrences=None,
                     default_edges_color="#000000", performance_dfg=None, dfg_window_2=None, freq_triples=None,
                     net_name=""):

            self.net_name = [net_name]
            self.nodes = {}
            self.dependency_matrix = {}
            self.dfg_matrix = {}

            self.dfg = frequency_dfg
            self.performance_dfg = performance_dfg
            self.node_type = "frequency" if self.performance_dfg is None else "performance"

            self.activities = activities
            self.start_activities = [start_activities]
            self.end_activities = [end_activities]

            self.activities_occurrences = activities_occurrences
            if self.activities_occurrences is None:
                self.activities_occurrences = {}
                for act in self.activities:
                    self.activities_occurrences[act] = dfg_utils.sum_activities_count(frequency_dfg, [act])

            self.default_edges_color = [default_edges_color]
            self.dfg_window_2 = dfg_window_2
            self.dfg_window_2_matrix = {}
            self.freq_triples = freq_triples
            self.freq_triples_matrix = {}
            self.concurrent_activities = {}
            self.sojourn_times = {}

            self.min_dfg_occurrences = None
            self.performance_matrix = None

        def __add__(self, other_net):
            copied_self = deepcopy(self)
            for node_name in copied_self.nodes:
                if node_name in other_net.nodes:
                    node1 = copied_self.nodes[node_name]
                    node2 = other_net.nodes[node_name]
                    n1n = {x.node_name: x for x in node1.output_connections}
                    n2n = {x.node_name: x for x in node2.output_connections}
                    for out_node1 in node1.output_connections:
                        if out_node1.node_name in n2n:
                            node1.output_connections[out_node1] = node1.output_connections[out_node1] + \
                                                                  node2.output_connections[n2n[out_node1.node_name]]
                    for out_node2 in node2.output_connections:
                        if out_node2.node_name not in n1n:
                            if out_node2.node_name in copied_self.nodes:
                                nn = copied_self.nodes[out_node2.node_name]
                                node1.output_connections[nn] = node2.output_connections[out_node2]
                            else:
                                node1.output_connections[out_node2] = node2.output_connections[out_node2]
            diff_ext = [other_net.nodes[node] for node in other_net.nodes if node not in copied_self.nodes]
            for node in diff_ext:
                copied_self.nodes[node.node_name] = node
            copied_self.start_activities = copied_self.start_activities + other_net.start_activities
            copied_self.end_activities = copied_self.end_activities + other_net.end_activities
            copied_self.default_edges_color = copied_self.default_edges_color + other_net.default_edges_color
            copied_self.net_name = copied_self.net_name + other_net.net_name

            return copied_self

        def __repr__(self):
            return str(self.nodes)

        def __str__(self):
            return str(self.nodes)

    def __init__(self, gui):
        self.dfg_noise: float = 0.8
        self.dependency_noise: float = 0.1
        self.rejection_noise: float = 0.1

        self.event_log = None
        self.parameters = {}
        self.activity_key = exec_utils.get_param_value(self.Parameters.ACTIVITY_KEY, self.parameters,
                                                       xes.DEFAULT_NAME_KEY)  # Source: PM4PY

        self.num_activities = 0
        self.num_start_activities = 0
        self.num_end_activities = 0

        self.activities = None
        self.trace_list = None
        self.df_relations = None
        self.matrix = None
        self.noised_matrix = None
        self.starting_activities = None
        self.ending_activities = None
        self.noised_heu_net = None

        self.tree = None
        self.net = None
        self.im = None
        self.fm = None

        self.gamma: float = 0.01
        self.e_0: float = 0.01
        self.max_sampling_tries: int = int(max(1 / self.gamma * np.log(2 / self.e_0), 1 / (np.e * self.gamma)))

        Image.MAX_IMAGE_PIXELS = None
        self.GUI: GUI = gui

    def add_event_log(self, log):
        try:
            self.event_log = xes_importer.apply(log)
            self.activities = None
            self.trace_list = None
            self.df_relations = None
            self.matrix = None
            self.noised_matrix = None
            self.starting_activities = None
            self.ending_activities = None
            self.extract_activities()

        except Exception as e:
            messagebox.showerror("Error", f"Event log could not be loaded: {e}")

    def extract_activities(self):
        self.activities = list(
            log_attributes.get_attribute_values(
                self.event_log,
                self.activity_key,
                parameters=self.parameters
            ).keys()
        )
        self.num_activities = len(self.activities)  # NEW
        self.get_trace_list()

    def get_trace_list(self):
        trace_list = list()
        act_key = exec_utils.get_param_value(self.Parameters.ACTIVITY_KEY.value, parameters={},
                                             default=xes_constants.DEFAULT_NAME_KEY)

        start_set = set()
        end_set = set()

        for trace in self.event_log:
            tmp_list = list()

            start_set.add(trace[0][act_key])
            end_set.add(trace[-1][act_key])

            for i in range(len(trace) - 1):
                if i == 0:  # first activity
                    tmp_list.append(('0xb2e-start-0x31c', trace[i][act_key]))  # pre-fix a synthetic start
                tmp_list.append((trace[i][act_key], trace[i + 1][act_key]))  # in-between activity

                if i == len(trace) - 2:  # last activity
                    tmp_list.append((trace[i + 1][act_key], '0x31c-end-0x1021'))  # post-fix a synthetic end

            if len(trace) == 1:  # consider traces of length 1
                tmp_list.append(('0xb2e-start-0x31c', trace[0][act_key]))
                tmp_list.append((trace[0][act_key], '0x31c-end-0x1021'))

            tmp_list = list(set(tmp_list))  # upper-bind sensitivity to 1
            trace_list.append(tmp_list)

        self.trace_list = trace_list

        # store sets + counts as DPHM attributes
        self.num_start_activities = len(start_set)
        self.num_end_activities = len(end_set)

        self.create_matrix()

    def create_matrix(self):
        activities = sorted(self.activities, key=lambda s: s.lower())
        permutations = list(product(self.activities, repeat=2))
        for act in activities:
            permutations.append(tuple(('0xb2e-start-0x31c', act)))
            permutations.append(tuple((act, '0x31c-end-0x1021')))
        temp_matrix = {perm: 0 for perm in permutations}

        matrix = Counter(temp_matrix)

        self.matrix = matrix
        self.fill_matrix()

    def fill_matrix(self):
        for trace in self.trace_list:
            for pair in trace:
                self.matrix[pair] += 1

        self.rejection_sampling()

    def noise_matrix(self):
        if self.event_log is None:
            return

        # Preparation
        noised_matrix = {}
        starting_activities = {a: 0 for a in self.activities}
        ending_activities = {a: 0 for a in self.activities}

        # Noise everything
        for key, value in self.matrix.items():
            noised_matrix[key] = int(self.add_laplace_noise(value, 1, self.GUI.epsilon.get()*self.dfg_noise))

        # Extract noised starting and ending activities
        for key, value in noised_matrix.items():
            if key[0] == '0xb2e-start-0x31c':
                starting_activities[key[1]] += value
            if key[1] == '0x31c-end-0x1021':
                ending_activities[key[0]] += value

        # Remove synthetic start and end activities from matrix and convert it to counter
        filtered_dict = {k: v for k, v in noised_matrix.items() if
                         '0xb2e-start-0x31c' not in k and '0x31c-end-0x1021' not in k}

        # Create subset of starting activities
        j: int = self.create_subset_size(self.num_start_activities, self.num_activities)
        self.starting_activities = self.report_noisy_max(starting_activities, j)

        # Create subset of ending activities
        k: int = self.create_subset_size(self.num_end_activities, self.num_activities)
        self.ending_activities = self.report_noisy_max(ending_activities, k)

        # Create subset of matrix of all behavior
        lower, upper = self.calculate_bounds(filtered_dict)
        if lower == upper:
            filtered_dict = self.report_noisy_max(filtered_dict, lower)
        else:
            b: int = np.random.randint(lower, upper)
            filtered_dict = self.report_noisy_max(filtered_dict, b)

        noised_matrix = Counter(filtered_dict)
        self.noised_matrix = noised_matrix

    @staticmethod
    def create_subset_size(original_size, total_size) -> int:
        size: int = 0

        if original_size < total_size:
            size = np.random.randint(original_size, original_size+2)
        if original_size == total_size:
            size = total_size

        return size

    @staticmethod
    def add_laplace_noise(original_value: float, sensitivity: float, epsilon: float) -> float:
        """
        Adds Laplace noise to the given original value.

        Parameters:
            original_value (float): The original value to which noise is added.
            sensitivity (float): The sensitivity of the original value.
            epsilon (float): The privacy budget.

        Returns:
            float: The original value with added Laplace noise.
        """
        scale = sensitivity / epsilon
        noise = np.random.laplace(0., scale)
        noised_val = original_value + noise

        return noised_val

    def calculate_bounds(self, matrix: dict):
        # Count the number of activity pairs with a frequency > 0
        count_above_zero = sum(1 for value in matrix.values() if value > 0)

        # Calculate preliminary lower and upper bounds
        lower_bound = count_above_zero - 15
        upper_bound = count_above_zero + 15

        # Round to the nearest multiple of 5
        lower_bound = max(count_above_zero, 5 * round(lower_bound / 5))
        upper_bound = min(count_above_zero ** 2, 5 * round(upper_bound / 5))

        # Set boundaries for lower and upper bound
        if lower_bound < len(self.activities):
            lower_bound = len(self.activities)

        if upper_bound >= len(self.activities)**2:
            upper_bound = len(self.activities)**2-1

        return lower_bound, upper_bound

    @staticmethod
    def report_noisy_max(list_elements: dict, n: int):

        if not list_elements or n <= 0:
            return {}

        # Select the top-n highest noisy scores
        top_n_items = {key: list_elements[key] for key in sorted(list_elements, key=list_elements.get, reverse=True)[:n]}

        return top_n_items

    def rejection_sampling(self, renoise: bool=True):

        # Check for missing event log
        if self.event_log is None:
            return False

        for i in range(0, self.max_sampling_tries):
            # Chance to stop and return nothing
            coin_flip = random.random()
            if coin_flip <= self.gamma:
                return False

            if renoise:
                self.noise_matrix()

            noised_heu_net = self.DPHeuristicsNet(
                frequency_dfg=self.noised_matrix,  # safe, because epsilon-DP-noised
                activities=self.activities,  # safe, because we do not intend to change the process domain
                activities_occurrences=None,  # safe, because based on epsilon-DP-noised activity counts
                start_activities=self.starting_activities,  # safe, because epsilon-DP-noised
                end_activities=self.ending_activities,  # safe, because epsilon-DP-noised
                dfg_window_2=None,  # safe, because None
                freq_triples=None,  # safe, because None
                performance_dfg=None  # safe, because None
            )

            self.noised_heu_net = self.calculate(
                heu_net=noised_heu_net,  # safe, because epsilon-DP-noised
                config=
                {
                    "dependency_thresh": self.GUI.dependency.get(),
                    "and_measure_thresh": self.GUI.AND.get(),
                    "min_act_count": self.GUI.min_act.get(),
                    "min_dfg_occurrences": self.GUI.min_dfg.get(),
                    "dfg_pre_cleaning_noise_thresh": self.GUI.pre_noise.get(),
                    "loops_length_two_thresh": self.GUI.loop2.get(),
                    "parameters": {}  # safe, because {}
                }
            )

            try:
                self.net = None
                self.im = None
                self.fm = None

                # Convert HeuristicsNet into Petri Net
                from pm4py.algo.discovery.heuristics import algorithm as heuristics_miner
                net, initial_marking, final_marking = heuristics_miner.classic.hn_conv_alg.apply(self.noised_heu_net)
                self.net = net
                self.im = initial_marking
                self.fm = final_marking

            except ValueError:
                pass

            # Termination criterion: If check_rejection() returns True, the For-Loop is exited
            if self.check_rejection():
                return

    def calculate(self, heu_net, config=None):
        if config is None:
            config = {}

        dependency_thresh = config.get("dependency_thresh", defaults.DEFAULT_DEPENDENCY_THRESH)
        and_measure_thresh = config.get("and_measure_thresh", defaults.DEFAULT_AND_MEASURE_THRESH)
        min_act_count = config.get("min_act_count", defaults.DEFAULT_MIN_ACT_COUNT)
        min_dfg_occurrences = config.get("min_dfg_occurrences", defaults.DEFAULT_MIN_DFG_OCCURRENCES)
        dfg_pre_cleaning_noise_thresh = config.get("dfg_pre_cleaning_noise_thresh",
                                                   defaults.DEFAULT_DFG_PRE_CLEANING_NOISE_THRESH)
        loops_length_two_thresh = config.get("loops_length_two_thresh", defaults.DEFAULT_LOOP_LENGTH_TWO_THRESH)
        parameters = config.get("parameters", {})

        if parameters is None:
            parameters = {}
        heu_net.min_dfg_occurrences = min_dfg_occurrences
        heu_net.dependency_matrix = {}
        heu_net.dfg_matrix = {}
        heu_net.performance_matrix = {}
        if dfg_pre_cleaning_noise_thresh > 0.0:
            heu_net.dfg = clean_dfg_based_on_noise_thresh(heu_net.dfg,
                                                          heu_net.activities,
                                                          dfg_pre_cleaning_noise_thresh,
                                                          parameters=parameters
                                                          )
        if heu_net.dfg_window_2 is not None:
            for el in heu_net.dfg_window_2:
                act1 = el[0]
                act2 = el[1]
                value = heu_net.dfg_window_2[el]
                if act1 not in heu_net.dfg_window_2_matrix:
                    heu_net.dfg_window_2_matrix[act1] = {}
                heu_net.dfg_window_2_matrix[act1][act2] = value

        if heu_net.freq_triples is not None:
            for el in heu_net.freq_triples:
                act1 = el[0]
                act2 = el[1]
                act3 = el[2]
                value = heu_net.freq_triples[el]
                # avoid to consider self-loops
                if act1 == act3 and not act1 == act2:
                    if act1 not in heu_net.freq_triples_matrix:
                        heu_net.freq_triples_matrix[act1] = {}
                    heu_net.freq_triples_matrix[act1][act2] = value

        for el in heu_net.dfg:
            act1 = el[0]
            act2 = el[1]
            value = heu_net.dfg[el]
            perf_value = heu_net.performance_dfg[el] if heu_net.performance_dfg is not None else heu_net.dfg[el]

            if act1 not in heu_net.dependency_matrix:
                heu_net.dependency_matrix[act1] = {}
                heu_net.dfg_matrix[act1] = {}
                heu_net.performance_matrix[act1] = {}

            heu_net.dfg_matrix[act1][act2] = value
            heu_net.performance_matrix[act1][act2] = perf_value
            if not act1 == act2:
                inv_couple = (act2, act1)
                c1 = value
                if inv_couple in heu_net.dfg:
                    c2 = heu_net.dfg[inv_couple]
                    dep = (c1 - c2) / (c1 + c2 + 1)
                else:
                    dep = c1 / (c1 + 1)
            else:
                dep = value / (value + 1)
            heu_net.dependency_matrix[act1][act2] = dep

        for n1 in heu_net.dependency_matrix:
            for n2 in heu_net.dependency_matrix[n1]:
                condition1 = n1 in heu_net.activities_occurrences and heu_net.activities_occurrences[
                    n1] >= min_act_count
                condition2 = n2 in heu_net.activities_occurrences and heu_net.activities_occurrences[
                    n2] >= min_act_count
                condition3 = heu_net.dfg_matrix[n1][n2] >= min_dfg_occurrences
                condition4 = heu_net.dependency_matrix[n1][n2] >= dependency_thresh
                condition = condition1 and condition2 and condition3 and condition4

                if condition:
                    if n1 not in heu_net.nodes:
                        heu_net.nodes[n1] = Node(heu_net, n1, heu_net.activities_occurrences[n1],
                                                 is_start_node=(n1 in heu_net.start_activities),
                                                 is_end_node=(n1 in heu_net.end_activities),
                                                 default_edges_color=heu_net.default_edges_color[0],
                                                 node_type=heu_net.node_type, net_name=heu_net.net_name[0],
                                                 nodes_dictionary=heu_net.nodes)
                    if n2 not in heu_net.nodes:
                        heu_net.nodes[n2] = Node(heu_net, n2, heu_net.activities_occurrences[n2],
                                                 is_start_node=(n2 in heu_net.start_activities),
                                                 is_end_node=(n2 in heu_net.end_activities),
                                                 default_edges_color=heu_net.default_edges_color[0],
                                                 node_type=heu_net.node_type, net_name=heu_net.net_name[0],
                                                 nodes_dictionary=heu_net.nodes)

                    repr_value = heu_net.performance_matrix[n1][n2]
                    heu_net.nodes[n1].add_output_connection(heu_net.nodes[n2], heu_net.dependency_matrix[n1][n2],
                                                            heu_net.dfg_matrix[n1][n2], repr_value=repr_value)
                    heu_net.nodes[n2].add_input_connection(heu_net.nodes[n1], heu_net.dependency_matrix[n1][n2],
                                                           heu_net.dfg_matrix[n1][n2], repr_value=repr_value)
        for node in heu_net.nodes:
            heu_net.nodes[node].calculate_and_measure_out(and_measure_thresh=and_measure_thresh)
            heu_net.nodes[node].calculate_and_measure_in(and_measure_thresh=and_measure_thresh)
            heu_net.nodes[node].calculate_loops_length_two(heu_net.dfg_matrix, heu_net.freq_triples_matrix,
                                                           loops_length_two_thresh=loops_length_two_thresh)
        nodes = list(heu_net.nodes.keys())
        added_loops = set()

        for n1 in nodes:
            for n2 in heu_net.nodes[n1].loop_length_two:
                if n1 in heu_net.dfg_matrix and n2 in heu_net.dfg_matrix[n1] and heu_net.dfg_matrix[n1][
                    n2] >= min_dfg_occurrences and n1 in heu_net.activities_occurrences and \
                        heu_net.activities_occurrences[
                            n1] >= min_act_count and n2 in heu_net.activities_occurrences and \
                        heu_net.activities_occurrences[
                            n2] >= min_act_count:
                    if not ((n1 in heu_net.dependency_matrix and n2 in heu_net.dependency_matrix[n1] and
                             heu_net.dependency_matrix[n1][n2] >= dependency_thresh) or (
                                    n2 in heu_net.dependency_matrix and n1 in heu_net.dependency_matrix[n2] and
                                    heu_net.dependency_matrix[n2][n1] >= dependency_thresh)):
                        if n2 not in heu_net.nodes:
                            heu_net.nodes[n2] = Node(heu_net, n2, heu_net.activities_occurrences[n2],
                                                     is_start_node=(n2 in heu_net.start_activities),
                                                     is_end_node=(n2 in heu_net.end_activities),
                                                     default_edges_color=heu_net.default_edges_color[0],
                                                     node_type=heu_net.node_type, net_name=heu_net.net_name[0],
                                                     nodes_dictionary=heu_net.nodes)
                        v_n1_n2 = heu_net.dfg_matrix[n1][n2] if n1 in heu_net.dfg_matrix and n2 in heu_net.dfg_matrix[
                            n1] else 0
                        v_n2_n1 = heu_net.dfg_matrix[n2][n1] if n2 in heu_net.dfg_matrix and n1 in heu_net.dfg_matrix[
                            n2] else 0

                        if (n1, n2) not in added_loops:
                            repr_value = heu_net.performance_matrix[n1][
                                n2] if n1 in heu_net.performance_matrix and n2 in \
                                       heu_net.performance_matrix[n1] else 0
                            added_loops.add((n1, n2))
                            heu_net.nodes[n1].add_output_connection(heu_net.nodes[n2], 0,
                                                                    v_n1_n2, repr_value=repr_value)
                            heu_net.nodes[n2].add_input_connection(heu_net.nodes[n1], 0,
                                                                   v_n2_n1, repr_value=repr_value)

                        if (n2, n1) not in added_loops:
                            repr_value = heu_net.performance_matrix[n2][
                                n1] if n2 in heu_net.performance_matrix and n1 in \
                                       heu_net.performance_matrix[n2] else 0
                            added_loops.add((n2, n1))
                            heu_net.nodes[n2].add_output_connection(heu_net.nodes[n1], 0,
                                                                    v_n2_n1, repr_value=repr_value)
                            heu_net.nodes[n1].add_input_connection(heu_net.nodes[n2], 0,
                                                                   v_n1_n2, repr_value=repr_value)
        if len(heu_net.nodes) == 0:
            for act in heu_net.activities:
                heu_net.nodes[act] = Node(heu_net, act, heu_net.activities_occurrences[act],
                                          is_start_node=(act in heu_net.start_activities),
                                          is_end_node=(act in heu_net.end_activities),
                                          default_edges_color=heu_net.default_edges_color[0],
                                          node_type=heu_net.node_type, net_name=heu_net.net_name[0],
                                          nodes_dictionary=heu_net.nodes)

        return heu_net

    def check_rejection(self) -> bool:

            # Caching values for rejection sampling
            rej_sam_attr: str = self.GUI.rejection_sampling_attr.get()
            thresh_value: float = self.GUI.rejection_threshold.get()

            if rej_sam_attr == "Fitness":
                try:
                    fitness_tb = pm4py.fitness_token_based_replay(self.event_log, self.net, self.im, self.fm)
                    if (self.add_laplace_noise(fitness_tb.get('log_fitness'),
                                               1, self.GUI.epsilon.get() * self.GUI.epsilon.get()*self.rejection_noise) >= thresh_value):
                        self.render()
                        return True
                except ValueError:
                    pass

            elif rej_sam_attr == "Precision":
                try:
                    precision_tb = pm4py.precision_token_based_replay(self.event_log, self.net, self.im, self.fm)
                    if (self.add_laplace_noise(precision_tb,
                                               1, self.GUI.epsilon.get() * self.GUI.epsilon.get()*self.rejection_noise) >= thresh_value):
                        self.render()
                        return True
                except ValueError:
                    pass

            elif rej_sam_attr == "Simplicity":
                try:
                    simplicity = simplicity_evaluator.apply(self.net)
                    if (self.add_laplace_noise(simplicity,
                                               1, self.GUI.epsilon.get() * self.GUI.epsilon.get()*self.rejection_noise) >= thresh_value):
                        self.render()
                        return True
                except ValueError:
                    pass

            elif rej_sam_attr == "Generalization":
                try:
                    generalization = generalization_evaluator.apply(self.event_log, self.net, self.im, self.fm)
                    if (self.add_laplace_noise(generalization,
                                               1, self.GUI.epsilon.get() * self.GUI.epsilon.get()*self.rejection_noise) >= thresh_value):
                        self.render()
                        return True
                except ValueError:
                    pass

            elif rej_sam_attr == "F1-Score":
                try:
                    fitness_tb = pm4py.fitness_token_based_replay(self.event_log, self.net, self.im, self.fm)
                    precision_tb = pm4py.precision_token_based_replay(self.event_log, self.net, self.im, self.fm)

                    f = fitness_tb.get('log_fitness')
                    p = precision_tb
                    f1 = 0 if (f + p) == 0 else 2 * f * p / (f + p)

                    if (self.add_laplace_noise(f1,
                                               1, self.GUI.epsilon.get() * self.GUI.epsilon.get()*self.rejection_noise) >= thresh_value):
                        self.render()
                        return True
                except ValueError:
                    pass

            # If the method has not returned True by now, it returns False
            return False

    def render(self):
        # ==================================================== 1
        dot = graphviz.Digraph(format="png", graph_attr={"rankdir": "LR"})
        for act1 in self.noised_heu_net.dependency_matrix:
            for act2 in self.noised_heu_net.dependency_matrix[act1]:
                weight = self.noised_heu_net.dependency_matrix[act1][act2]
                if weight > self.GUI.dependency.get():
                    dot.edge(act1, act2, label=str(round(weight, 2)))
        png_data = dot.pipe(format="png")
        img = Image.open(io.BytesIO(png_data))
        self.GUI.apply_image(img, 1)

        # ==================================================== 2
        parameters = {
            pm4py.algo.discovery.heuristics.algorithm.Variants.CLASSIC.value.Parameters.DEPENDENCY_THRESH: self.GUI.dependency.get(),
            pm4py.algo.discovery.heuristics.algorithm.Variants.CLASSIC.value.Parameters.AND_MEASURE_THRESH: self.GUI.AND.get(),
            pm4py.algo.discovery.heuristics.algorithm.Variants.CLASSIC.value.Parameters.MIN_ACT_COUNT: self.GUI.min_act.get(),
            pm4py.algo.discovery.heuristics.algorithm.Variants.CLASSIC.value.Parameters.MIN_DFG_OCCURRENCES: self.GUI.min_dfg.get(),
            pm4py.algo.discovery.heuristics.algorithm.Variants.CLASSIC.value.Parameters.DFG_PRE_CLEANING_NOISE_THRESH: self.GUI.pre_noise.get(),
            pm4py.algo.discovery.heuristics.algorithm.Variants.CLASSIC.value.Parameters.LOOP_LENGTH_TWO_THRESH: self.GUI.loop2.get()
        }

        net, initial_marking, final_marking = pm4py.algo.discovery.heuristics.algorithm.classic.hn_conv_alg.apply(self.noised_heu_net, parameters)

        viz = pn_visualizer.apply(net, initial_marking, final_marking, parameters={
            pn_visualizer.Variants.WO_DECORATION.value.Parameters.FORMAT: "svg"})
        svg_data = pm4py.visualization.petri_net.visualizer.serialize(viz)
        png_data = cairosvg.svg2png(bytestring=svg_data)
        img = Image.open(io.BytesIO(png_data))
        self.GUI.apply_image(img, 2)


if __name__ == '__main__':
    from GUI import GUI
    app = GUI()
    app.root.mainloop()

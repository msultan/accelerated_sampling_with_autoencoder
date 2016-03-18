import copy, pickle, re, os, time, subprocess, datetime, itertools
from scipy import io as sciio
import numpy as np
from numpy.testing import assert_almost_equal
from math import *
from pybrain.structure import *
from pybrain.structure.modules.circularlayer import *
from pybrain.supervised.trainers import BackpropTrainer
from pybrain.datasets.supervised import SupervisedDataSet
import matplotlib.pyplot as plt
from config import * # configuration file

"""note that all configurations for a class should be in function __init__(), and take configuration parameters
from config.py
"""

class coordinates_data_files_list(object):
    def __init__(self,
                list_of_dir_of_coor_data_files = CONFIG_1 # this is the directory that holds corrdinates data files
                ):
        self._list_of_dir_of_coor_data_files = list_of_dir_of_coor_data_files
        self._list_of_coor_data_files = []
        for item in self._list_of_dir_of_coor_data_files:
            self._list_of_coor_data_files += subprocess.check_output(['find', item,'-name' ,'*coordinates.txt']).split('\n')[:-1]

        self._list_of_coor_data_files = list(set(self._list_of_coor_data_files))  # remove duplicates
        return

    def get_list_of_coor_data_files(self):
        return self._list_of_coor_data_files


class single_simulation_coordinates_file(object):
    """this object contains information of a generated coordinates file, including
     - filename
     - potential centers
     - force constants
     - num of coordinates
     - coordinates data
    """
    def __init__(self, filename):  # filename if the path to the file
        self._filename = filename
        self._force_constant = float(filename.split('biased_output_fc_')[1].split('_x1_')[0])
        self._potential_center = [float(filename.split('_x1_')[1].split('_x2_')[0]), float(filename.split('_x2_')[1].split('_coordinates.txt')[0])]
        self._num_of_coors = float(subprocess.check_output(['wc', '-l', filename]).split()[0])  # there would be some problems if using int
        self._coor_data = np.loadtxt(filename, float)
        assert (self._coor_data.shape[0] == self._num_of_coors)
        assert (self._coor_data.shape[1] == 21)
        return

class sutils(object):
    """sutils: simulation unilities
    this class contains some utility tools, that do not belong to **any object instance**
    """
    def __init__(self):
        return

    @staticmethod
    def get_cossin_of_a_dihedral_from_four_atoms(coord_1, coord_2, coord_3, coord_4):
        """each parameter is a 3D Cartesian coordinates of an atom"""
        coords_of_four = np.array([coord_1, coord_2, coord_3, coord_4])
        num_of_coordinates = 4
        diff_coordinates = coords_of_four[1:num_of_coordinates, :] - coords_of_four[0:num_of_coordinates - 1,:]  # bond vectors
        diff_coordinates_1=diff_coordinates[0:num_of_coordinates-2,:];diff_coordinates_2=diff_coordinates[1:num_of_coordinates-1,:]
        normal_vectors = np.cross(diff_coordinates_1, diff_coordinates_2)
        normal_vectors_normalized = np.array(map(lambda x: x / sqrt(np.dot(x,x)), normal_vectors))
        normal_vectors_normalized_1 = normal_vectors_normalized[0:num_of_coordinates-3, :]; normal_vectors_normalized_2 = normal_vectors_normalized[1:num_of_coordinates-2,:];
        diff_coordinates_mid = diff_coordinates[1:num_of_coordinates-2] # these are bond vectors in the middle (remove the first and last one), they should be perpendicular to adjacent normal vectors

        index = 0
        cos_of_angle = np.dot(normal_vectors_normalized_1[index], normal_vectors_normalized_2[index])
        sin_of_angle_vec = np.cross(normal_vectors_normalized_1[index], normal_vectors_normalized_2[index])
        sin_of_angle = sqrt(np.dot(sin_of_angle_vec, sin_of_angle_vec)) * np.sign(sum(sin_of_angle_vec) * sum(diff_coordinates_mid[index]));

        assert_almost_equal (cos_of_angle ** 2 + sin_of_angle ** 2, 1)
        return [cos_of_angle, sin_of_angle]

    @staticmethod
    def get_coordinates_of_atom_with_index(a_coodinate, index):
        """:param a_coodinate is coordinate of all 20 atoms"""
        return [a_coodinate[3 * index], a_coodinate[3 * index + 1], a_coodinate[3 * index + 2]]

    @staticmethod
    def get_cossin_from_a_coordinate(a_coordinate):
        # FIXME: how to write unit test for this function?
        total_num_of_residues = 20
        list_of_idx_four_atoms = map(lambda x: [3 * x, 3 * x + 1, 3 * x + 2, 3 * x + 3], range(total_num_of_residues)) \
                               + map(lambda x: [3 * x - 1, 3 * x, 3 * x + 1, 3 * x + 2], range(total_num_of_residues))
        list_of_idx_four_atoms = filter(lambda x: x[0] >= 0 and x[3] < 3 * total_num_of_residues, list_of_idx_four_atoms)

        result = []

        for item in list_of_idx_four_atoms:
            parameter_list = map(
                    lambda x: sutils.get_coordinates_of_atom_with_index(a_coordinate, x),
                    item
                    )
            [cos_value, sin_value] = sutils.get_cossin_of_a_dihedral_from_four_atoms(*parameter_list)
            # print(item)
            # print(cos_value, sin_value)
            result += [cos_value, sin_value]

        return result


    @staticmethod
    def get_many_cossin_from_coordinates(coordinates):
        return map(sutils.get_cossin_from_a_coordinate, coordinates)

    @staticmethod
    def get_many_cossin_from_coordiantes_in_list_of_files(list_of_files):
        result = []
        for item in list_of_files:
            coordinates = np.loadtxt(item)
            temp = sutils.get_many_cossin_from_coordinates(coordinates)
            result += temp

        return result

    @staticmethod
    def get_many_dihedrals_from_coordinates_in_file (list_of_files):
        # why we need to get dihedrals from a list of coordinate files?
        # because we will probably need to plot other files outside self._list_of_coor_data_files
        temp = sutils.get_many_cossin_from_coordiantes_in_list_of_files(list_of_files)
        return sutils.get_many_dihedrals_from_cossin(temp)

    @staticmethod
    def get_many_dihedrals_from_cossin(cossin):
        result = []
        for item in cossin:
            temp_angle = []
            assert (len(item) == 76)
            for idx_of_angle in range(38):
                temp_angle += [np.arccos(item[2 * idx_of_angle]) * np.sign(item[2 * idx_of_angle + 1])]

            assert (len(temp_angle) == 38)

            result += [temp_angle]

        assert (len(result) == len(cossin))

        return result

    @staticmethod
    def generate_coordinates_from_pdb_files(folder_for_pdb = CONFIG_12):
        filenames = subprocess.check_output(['find', folder_for_pdb, '-name' ,'*.pdb']).split('\n')[:-1]

        index_of_backbone_atoms = ['1', '2', '3', '17', '18', '19', '36', '37', '38', '57', '58', '59', '76', '77', '78', '93', '94', '95', '117', '118', '119', '136', '137', '138', '158', '159', '160', '170', '171', '172', '177', '178', '179', '184', '185', '186', '198', '199', '200', '209', '210', '211', '220', '221', '222', '227', '228', '229', '251', '252', '253', '265', '266', '267', '279', '280', '281', '293', '294', '295' ]
        assert (len(index_of_backbone_atoms) % 3 == 0)

        for input_file in filenames:
            print ('generating coordinates of ' + input_file)
            output_file = input_file[:-4] + '_coordinates.txt'

            with open(input_file) as f_in:
                with open(output_file, 'w') as f_out:
                    for line in f_in:
                        fields = line.strip().split()
                        if (fields[0] == 'ATOM' and fields[1] in index_of_backbone_atoms):
                            f_out.write(reduce(lambda x,y: x + '\t' + y, fields[6:9]))
                            f_out.write('\t')
                        elif fields[0] == "MODEL" and fields[1] != "1":
                            f_out.write('\n')

                    f_out.write('\n')  # last line
        print("Done generating coordinates files\n")
        return

    @staticmethod
    def get_boundary_points_2(list_of_points, num_of_bins = CONFIG_10, num_of_boundary_points = CONFIG_11,
                              periodic_boundary = CONFIG_18):
        '''This is another version of get_boundary_points() function'''

        x = [item[0] for item in list_of_points]
        y = [item[1] for item in list_of_points]

        hist_matrix, temp1 , temp2 = np.histogram2d(x,y, bins=[num_of_bins, num_of_bins])
        # add a set of zeros around this region
        hist_matrix = np.insert(hist_matrix, num_of_bins, np.zeros(num_of_bins), 0)
        hist_matrix = np.insert(hist_matrix, 0, np.zeros(num_of_bins), 0)
        hist_matrix = np.insert(hist_matrix, num_of_bins, np.zeros(num_of_bins + 2), 1)
        hist_matrix = np.insert(hist_matrix, 0, np.zeros(num_of_bins +2), 1)

        sum_of_neighbors = np.zeros(np.shape(hist_matrix)) # number of neighbors occupied with some points
        for i in range(np.shape(hist_matrix)[0]):
            for j in range(np.shape(hist_matrix)[1]):
                if i != 0: sum_of_neighbors[i,j] += hist_matrix[i - 1][j]
                if j != 0: sum_of_neighbors[i,j] += hist_matrix[i][j - 1]
                if i != np.shape(hist_matrix)[0] - 1: sum_of_neighbors[i,j] += hist_matrix[i + 1][j]
                if j != np.shape(hist_matrix)[1] - 1: sum_of_neighbors[i,j] += hist_matrix[i][j + 1]

        bin_width_0 = temp1[1]-temp1[0]
        bin_width_1 = temp2[1]-temp2[0]
        min_coor_in_PC_space_0 = temp1[0] - 0.5 * bin_width_0  # multiply by 0.5 since we want the center of the grid
        min_coor_in_PC_space_1 = temp2[0] - 0.5 * bin_width_1

        potential_centers = []

        # now sort these grids (that has no points in it)
        # based on total number of points in its neighbors
        index_of_grids = list(itertools.product(range(np.shape(hist_matrix)[0]), range(np.shape(hist_matrix)[1])))
        # print(index_of_grids)
        sorted_index_of_grids = sorted(index_of_grids, key = lambda x: sum_of_neighbors[x[0]][x[1]]) # sort based on histogram, return index values
        temp_count = 0
        for index in sorted_index_of_grids:
            if hist_matrix[index] == 0 and sum_of_neighbors[index] != 0:
                if temp_count >= num_of_boundary_points:
                    break
                else:
                    temp_count += 1
                    temp_potential_center = [round(min_coor_in_PC_space_0 + index[0] * bin_width_0, 2),
                                             round(min_coor_in_PC_space_1 + index[1] * bin_width_1, 2)]
                    if periodic_boundary:  # this is used for network with circularLayer
                        for temp_index in range(2):
                            if temp_potential_center[temp_index] < - np.pi:
                                temp_potential_center[temp_index] = round(temp_potential_center[temp_index] + 2 * np.pi, 2)
                            elif temp_potential_center[temp_index] > np.pi:
                                temp_potential_center[temp_index] = round(temp_potential_center[temp_index] - 2 * np.pi, 2)

                    potential_centers.append(temp_potential_center)

        return potential_centers

    @staticmethod
    def get_boundary_points_3_for_circular_network(list_of_points,
                                                   range_of_PCs = [[-np.pi, np.pi], [-np.pi, np.pi]],
                                                   num_of_bins = 10,
                                                   num_of_boundary_points = CONFIG_11,
                                                   preprocessing = True):
        '''This is another version of get_boundary_points() function
        it works for circular layer case
        :param preprocessing: if True, then more weight is not linear, this would be better based on experience
        '''

        x = [item[0] for item in list_of_points]
        y = [item[1] for item in list_of_points]

        hist_matrix, temp1 , temp2 = np.histogram2d(x,y, bins=[num_of_bins, num_of_bins], range=range_of_PCs)
        # following is the main algorithm to find boundary and holes
        # simply find the points that are lower than average of its 4 neighbors

        if preprocessing:
            hist_matrix = map(lambda x: map(lambda y: - np.exp(- y), x), hist_matrix)   # preprocessing process

        diff_with_neighbors = hist_matrix - 0.25 * (np.roll(hist_matrix, 1, axis=0) + np.roll(hist_matrix, -1, axis=0)
                                                  + np.roll(hist_matrix, 1, axis=1) + np.roll(hist_matrix, -1, axis=1))

        bin_width_0 = temp1[1] - temp1[0]
        bin_width_1 = temp2[1] - temp2[0]
        min_coor_in_PC_space_0 = temp1[0] + 0.5 * bin_width_0  # multiply by 0.5 since we want the center of the grid
        min_coor_in_PC_space_1 = temp2[0] + 0.5 * bin_width_1

        potential_centers = []

        # now sort these grids (that has no points in it)
        # based on total number of points in its neighbors
        index_of_grids = list(itertools.product(range(np.shape(hist_matrix)[0]), range(np.shape(hist_matrix)[1])))

        sorted_index_of_grids = sorted(index_of_grids, key = lambda x: diff_with_neighbors[x[0]][x[1]]) # sort based on histogram, return index values
        temp_count = 0
        for index in sorted_index_of_grids:
            if temp_count >= num_of_boundary_points:
                break
            else:
                temp_count += 1
                temp_potential_center = [round(min_coor_in_PC_space_0 + index[0] * bin_width_0, 2),
                                         round(min_coor_in_PC_space_1 + index[1] * bin_width_1, 2)]

                potential_centers.append(temp_potential_center)

        return potential_centers


class neural_network_for_simulation(object):
    """the neural network for simulation"""

    def __init__(self,
                 index,  # the index of the current network
                 data_set_for_training,
                 energy_expression_file = None,
                 training_data_interval = CONFIG_2,
                 in_layer_type = LinearLayer, hidden_layers_types = CONFIG_17,
                 out_layer_type = LinearLayer,  # different layers
                 node_num = CONFIG_3,  # the structure of ANN
                 network_parameters = CONFIG_4,  # includes [learningrate,momentum, weightdecay, lrdecay]
                 max_num_of_training = CONFIG_5,
                 filename_to_save_network = CONFIG_6,
                 network_verbose = False,
                 trainer = None
                 ):

        self._index = index
        self._data_set = data_set_for_training
        self._training_data_interval = training_data_interval
        if energy_expression_file is None:
            self._energy_expression_file = "../resources/energy_expression_%d.txt" %(index)
        else:
            self._energy_expression_file = energy_expression_file

        if not in_layer_type is None: self._in_layer_type = in_layer_type
        if not hidden_layers_types is None: self._hidden_layers_type = hidden_layers_types
        if not out_layer_type is None: self._out_layer_type = out_layer_type

        self._in_layer = None
        self._out_layer = None
        self._hidden_layers = None

        self._node_num = node_num
        self._network_parameters = network_parameters
        self._max_num_of_training = max_num_of_training
        if filename_to_save_network is None:
            self._filename_to_save_network = "../resources/network_%s.pkl" % str(self._index) # by default naming with its index
        else:
            self._filename_to_save_network = filename_to_save_network

        self._network_verbose = network_verbose

        self._trainer = trainer  # save the trainer so that we could train this network step by step later
        return

    def save_into_file(self, filename = CONFIG_6):
        if filename is None:
            filename = self._filename_to_save_network

        if os.path.isfile(filename):  # backup file if previous one exists
            os.rename(filename, filename.split('.pkl')[0] + "_bak_" + datetime.datetime.now().strftime("%Y_%m_%d_%H_%M_%S") + '.pkl')

        with open(filename, 'wb') as my_file:
            pickle.dump(self, my_file, pickle.HIGHEST_PROTOCOL)
        return

    def get_expression_of_network(self):
        """
        this function generates expression of PCs in terms of inputs
        """
        type_of_middle_hidden_layer = self._hidden_layers_type[1]

        connection_between_layers = self._connection_between_layers
        connection_with_bias_layers = self._connection_with_bias_layers

        node_num = self._node_num
        expression = ""

        # 1st part: network
        for i in range(2):
            expression = '\n' + expression
            mul_coef = connection_between_layers[i].params.reshape(node_num[i + 1], node_num[i])
            bias_coef = connection_with_bias_layers[i].params

            for j in range(np.size(mul_coef, 0)):                
                temp_expression = 'in_layer_%d_unit_%d = ' % (i + 1, j)

                for k in range(np.size(mul_coef, 1)):
                    temp_expression += ' %f * out_layer_%d_unit_%d +' % (mul_coef[j, k], i, k)

                temp_expression += ' %f;\n' % (bias_coef[j])
                expression = temp_expression + expression  # order of expressions matter in OpenMM

            if i == 1 and type_of_middle_hidden_layer == CircularLayer:
                for j in range(np.size(mul_coef, 0) / 2):
                    temp_expression = 'out_layer_%d_unit_%d = ( in_layer_%d_unit_%d ) / radius_of_circular_pair_%d;\n' % \
                                      (i + 1, 2 * j, i + 1, 2 * j, j)
                    temp_expression += 'out_layer_%d_unit_%d = ( in_layer_%d_unit_%d ) / radius_of_circular_pair_%d;\n' % \
                                      (i + 1, 2 * j + 1, i + 1, 2 * j + 1, j)
                    temp_expression += 'radius_of_circular_pair_%d = sqrt( in_layer_%d_unit_%d * in_layer_%d_unit_%d + in_layer_%d_unit_%d * in_layer_%d_unit_%d );\n'  \
                                    % (j, i + 1, 2 * j, i + 1, 2 * j , i + 1, 2 * j + 1, i + 1, 2 * j + 1)

                    expression = temp_expression + expression
            else:
                for j in range(np.size(mul_coef, 0)):
                    temp_expression = 'out_layer_%d_unit_%d = tanh( in_layer_%d_unit_%d );\n' % (i + 1, j, i + 1, j)
                    expression = temp_expression + expression

        # 2nd part: relate PCs to network
        if type_of_middle_hidden_layer == CircularLayer:
            temp_expression = 'PC0 = acos( out_layer_2_unit_0 ) * ( step( out_layer_2_unit_1 ) - 0.5) * 2;\n'
            temp_expression += 'PC1 = acos( out_layer_2_unit_2 ) * ( step( out_layer_2_unit_3 ) - 0.5) * 2;\n'
            expression = temp_expression + expression
        elif type_of_middle_hidden_layer == TanhLayer:
            temp_expression = 'PC0 = out_layer_2_unit_0;\nPC1 = out_layer_2_unit_1;\n'
            expression = temp_expression + expression

        # 3rd part: definition of inputs
        index_of_backbone_atoms = [2, 5, 7, 9, 15, 17, 19]
        for i in range(len(index_of_backbone_atoms) - 3):
            index_of_coss = i
            index_of_sins = i + 4
            expression += 'out_layer_0_unit_%d = raw_layer_0_unit_%d;\n' % (index_of_coss, index_of_coss)
            expression += 'out_layer_0_unit_%d = raw_layer_0_unit_%d;\n' % (index_of_sins, index_of_sins)
            expression += 'raw_layer_0_unit_%d = cos(dihedral_angle_%d);\n' % (index_of_coss, i)
            expression += 'raw_layer_0_unit_%d = sin(dihedral_angle_%d);\n' % (index_of_sins, i)
            expression += 'dihedral_angle_%d = dihedral(p%d, p%d, p%d, p%d);\n' % (i, index_of_backbone_atoms[i], index_of_backbone_atoms[i+1],index_of_backbone_atoms[i+2],index_of_backbone_atoms[i+3])


        return expression

    def write_expression_into_file(self, out_file = None):
        if out_file is None: out_file = self._energy_expression_file

        expression = self.get_expression_of_network()
        with open(out_file, 'w') as f_out:
            f_out.write(expression)
        return

    def get_mid_result(self, input_data=None):
        if input_data is None: input_data = self._data_set
        connection_between_layers = self._connection_between_layers
        connection_with_bias_layers = self._connection_with_bias_layers

        node_num = self._node_num
        temp_mid_result = range(4)
        temp_mid_result_in = range(4)
        mid_result = []

        data_as_input_to_network = input_data

        hidden_and_out_layers = self._hidden_layers + [self._out_layer]

        for item in data_as_input_to_network:
            for i in range(4):
                mul_coef = connection_between_layers[i].params.reshape(node_num[i + 1], node_num[i]) # fix node_num
                bias_coef = connection_with_bias_layers[i].params
                previous_result = item if i == 0 else temp_mid_result[i - 1]
                temp_mid_result_in[i] = np.dot(mul_coef, previous_result) + bias_coef
                output_of_this_hidden_layer = range(len(temp_mid_result_in[i]))  # initialization
                hidden_and_out_layers[i]._forwardImplementation(temp_mid_result_in[i], output_of_this_hidden_layer)
                temp_mid_result[i] = output_of_this_hidden_layer

            mid_result.append(copy.deepcopy(temp_mid_result)) # note that should use deepcopy
        return mid_result

    def get_PCs(self, input_data = None):
        """
        write an independent function for getting PCs, since it is different for TanhLayer, and CircularLayer
        """
        if input_data is None: input_data = self._data_set
        type_of_middle_hidden_layer = self._hidden_layers_type[1]
        temp_mid_result = self.get_mid_result(input_data=input_data)
        mid_result_1 = [item[1] for item in temp_mid_result]
        if type_of_middle_hidden_layer == TanhLayer:
            PCs = mid_result_1
        elif type_of_middle_hidden_layer == CircularLayer:
            PCs = [[acos(item[0]) * np.sign(item[1]), acos(item[2]) * np.sign(item[3])] for item in mid_result_1]

        assert (len(PCs[0]) == 2)

        return PCs

    def train(self):

        ####################### set up autoencoder begin #######################
        node_num = self._node_num

        in_layer = (self._in_layer_type)(node_num[0], "IL")
        hidden_layers = [(self._hidden_layers_type[0])(node_num[1], "HL1"),
                         (self._hidden_layers_type[1])(node_num[2], "HL2"),
                         (self._hidden_layers_type[2])(node_num[3], "HL3")]
        bias_layers = [BiasUnit("B1"),BiasUnit("B2"),BiasUnit("B3"),BiasUnit("B4")]
        out_layer = (self._out_layer_type)(node_num[4], "OL")

        self._in_layer = in_layer
        self._out_layer = out_layer
        self._hidden_layers = hidden_layers

        layers_list = [in_layer] + hidden_layers + [out_layer]

        molecule_net = FeedForwardNetwork()

        molecule_net.addInputModule(in_layer)
        for item in (hidden_layers + bias_layers):
            molecule_net.addModule(item)

        molecule_net.addOutputModule(out_layer)

        connection_between_layers = range(4); connection_with_bias_layers = range(4)

        for i in range(4):
            connection_between_layers[i] = FullConnection(layers_list[i], layers_list[i+1])
            connection_with_bias_layers[i] = FullConnection(bias_layers[i], layers_list[i+1])
            molecule_net.addConnection(connection_between_layers[i])  # connect two neighbor layers
            molecule_net.addConnection(connection_with_bias_layers[i])

        molecule_net.sortModules()  # this is some internal initialization process to make this module usable

        ####################### set up autoencoder end #######################

        trainer = BackpropTrainer(molecule_net, learningrate=self._network_parameters[0],
                                                momentum=self._network_parameters[1],
                                                weightdecay=self._network_parameters[2],
                                                lrdecay=self._network_parameters[3],
                                                verbose=self._network_verbose)
        data_set = SupervisedDataSet(node_num[0], node_num[4])

        sincos = self._data_set[::self._training_data_interval]  # pick some of the data to train
        data_as_input_to_network = sincos

        for item in data_as_input_to_network:
            data_set.addSample(item, item)

        print('start training network with index = %d, training maxEpochs = %d\n' % (self._index, self._max_num_of_training))
        trainer.trainUntilConvergence(data_set, maxEpochs=self._max_num_of_training)

        self._connection_between_layers = connection_between_layers
        self._connection_with_bias_layers = connection_with_bias_layers

        print('Done training network with index = %d, training maxEpochs = %d\n' % (self._index, self._max_num_of_training))
        self._trainer = trainer
        return

    def get_training_error(self):
        # it turns out that this error info cannot be a good measure of the quality of the autoencoder
        input_data = np.array(self._data_set)
        output_data = np.array([item[3] for item in self.get_mid_result()])
        return np.linalg.norm(input_data - output_data) / sqrt(self._node_num[0] * len(input_data))

    def get_fraction_of_variance_explained(self):
        input_data = np.array(self._data_set)

        output_data = np.array([item[3] for item in self.get_mid_result()])
        var_of_input = sum(np.var(input_data, axis=0))
        var_of_output = sum(np.var(output_data, axis=0))
        return var_of_output / var_of_input

    def generate_mat_file_for_WHAM_reweighting(self, list_of_coor_data_files):
        # FIXME: this one does not work quite well for circular layer case, need further processing
        force_constants = []
        harmonic_centers = []
        window_counts = []
        coords = []
        umbOP = []
        for item in list_of_coor_data_files:
            # print('processing %s' %item)
            temp_force_constant = float(item.split('biased_output_fc_')[1].split('_x1_')[0])
            force_constants += [[temp_force_constant, temp_force_constant]]
            harmonic_centers += [[float(item.split('_x1_')[1].split('_x2_')[0]), float(item.split('_x2_')[1].split('_coordinates.txt')[0])]]
            temp_window_count = float(subprocess.check_output(['wc', '-l', item]).split()[0])  # there would be some problems if using int
            window_counts += [temp_window_count]
            temp_mid_result = self.get_mid_result(sutils.get_many_cossin_from_coordiantes_in_list_of_files([item]))
            temp_coor = [a[1] for a in temp_mid_result]
            assert(temp_window_count == len(temp_coor))  # ensure the number of coordinates is window_count
            coords += temp_coor
            temp_angles = sutils.get_many_dihedrals_from_coordinates_in_file([item])
            temp_umbOP = [a[1:3] for a in temp_angles]
            assert(temp_window_count == len(temp_umbOP))
            assert(2 == len(temp_umbOP[0]))
            umbOP += temp_umbOP

        max_of_coor = map(lambda x: round(x, 1) + 0.1, map(max, zip(*coords)))
        min_of_coor = map(lambda x: round(x, 1) - 0.1, map(min, zip(*coords)))
        interval = 0.1

        window_counts = np.array(window_counts)
        sciio.savemat('WHAM_nD__preprocessor.mat', {'window_counts': window_counts,
            'force_constants': force_constants, 'harmonic_centers': harmonic_centers,
            'coords': coords, 'dim': 2.0, 'temperature': 300.0, 'periodicity': [[0.0],[0.0]],
            'dF_tol': 0.0001,
            'min_gap_max_ORIG': [[min_of_coor[0], interval, max_of_coor[0]], [min_of_coor[1], interval, max_of_coor[1]]]
            })
        sciio.savemat('umbrella_OP.mat',
            {'umbOP': umbOP
            })
        return


class plotting(object):
    """this class implements different plottings
    """

    def __init__(self, network):
        assert isinstance(network, neural_network_for_simulation)
        self._network = network
        pass

    def plotting_with_coloring_option(self, plotting_space,  # means "PC" space or "phi-psi" space
                                            network=None,
                                            cossin_data_for_plotting=None,
                                            color_option='pure',
                                            other_coloring=None,
                                            title=None,
                                            axis_ranges=None,
                                            contain_colorbar=True
                                      ):
        """
        by default, we are using training data, and we also allow external data input
        """
        #TODO: plotting for circular layer network
        if network is None: network = self._network
        if cossin_data_for_plotting is None:
            cossin_data = self._network._data_set
        else:
            cossin_data = cossin_data_for_plotting

        if plotting_space == "PC":
            PCs_to_plot = network.get_PCs(input_data= cossin_data)

            (x, y) = ([item[0] for item in PCs_to_plot], [item[1] for item in PCs_to_plot])
            labels = ["PC1", "PC2"]

        elif plotting_space == "phipsi":
            temp_dihedrals = sutils.get_many_dihedrals_from_cossin(cossin_data)

            (x,y) = ([item[1] for item in temp_dihedrals], [item[2] for item in temp_dihedrals])
            labels = ["phi", "psi"]

        # coloring
        if color_option == 'pure':
            coloring = 'red'
        elif color_option == 'step':
            coloring = range(len(x))
        elif color_option == 'phi':
            coloring = [item[1] for item in sutils.get_many_dihedrals_from_cossin(cossin_data)]
        elif color_option == 'psi':
            coloring = [item[2] for item in sutils.get_many_dihedrals_from_cossin(cossin_data)]
        elif color_option == 'other':
            coloring = other_coloring

        fig, ax = plt.subplots()
        im = ax.scatter(x,y, c=coloring)
        ax.set_xlabel(labels[0])
        ax.set_ylabel(labels[1])
        ax.set_title(title)

        if not axis_ranges is None:
            ax.set_xlim(axis_ranges[0])
            ax.set_ylim(axis_ranges[1])

        if contain_colorbar:
            fig.colorbar(im, ax=ax)

        return fig, ax, im


class simulation_management(object):
    def __init__(self, mynetwork,
                 num_of_simulation_steps = CONFIG_8,
                 force_constant_for_biased = CONFIG_9
                 ):
        self._mynetwork = mynetwork
        self._num_of_simulation_steps = num_of_simulation_steps
        self._force_constant_for_biased = force_constant_for_biased
        return

    def get_todo_list_of_commands_for_simulations(self,list_of_potential_center = None,
                                                  num_of_simulation_steps = None,
                                                  energy_expression_file=None,
                                                  force_constant_for_biased = None,
                                                  file_to_store_command_list = 'simulation_command_todo_list.txt',
                                                  is_write_into_file = True):
        '''this function creates a list of commands that should be done later,
        either in local machines or on the cluster,
        if it should be done in the cluster, "auto_qsub" will be responsible for it
        '''
        temp_mid_result = self._mynetwork.get_mid_result()
        PCs_of_network = [item[1] for item in temp_mid_result]
        assert (len(PCs_of_network[0]) == 2)

        if list_of_potential_center is None:
            list_of_potential_center = sutils.get_boundary_points_3_for_circular_network(list_of_points= PCs_of_network)
        if num_of_simulation_steps is None:
            num_of_simulation_steps = self._num_of_simulation_steps
        if energy_expression_file is None:
            energy_expression_file = self._mynetwork._energy_expression_file
            filename_of_energy_expression = energy_expression_file.split('resources/')[1]
        if force_constant_for_biased is None:
            force_constant_for_biased = self._force_constant_for_biased

        todo_list_of_commands_for_simulations = []

        for potential_center in list_of_potential_center:
            parameter_list = (str(CONFIG_16), str(num_of_simulation_steps), str(force_constant_for_biased),
                            str(potential_center[0]), str(potential_center[1]),
                            'network_' + str(self._mynetwork._index),
                            filename_of_energy_expression)

            command = "python ../src/biased_simulation.py %s %s %s %s %s %s %s" % parameter_list
            todo_list_of_commands_for_simulations += [command]

        if is_write_into_file:
            with open(file_to_store_command_list, 'w') as f_out:
                for item in todo_list_of_commands_for_simulations:
                    f_out.write(str(item))
                    f_out.write('\n')

        return todo_list_of_commands_for_simulations


    def create_sge_files_for_simulation(self,list_of_potential_center = None,
                                        num_of_simulation_steps = None,
                                        energy_expression_file=None,
                                        force_constant_for_biased = None):

        PCs_of_network = self._mynetwork.get_PCs()
        assert (len(PCs_of_network[0]) == 2)

        if list_of_potential_center is None:
            list_of_potential_center = sutils.get_boundary_points_3_for_circular_network(list_of_points= PCs_of_network)
        if num_of_simulation_steps is None:
            num_of_simulation_steps = self._num_of_simulation_steps
        if energy_expression_file is None:
            energy_expression_file = self._mynetwork._energy_expression_file
            filename_of_energy_expression = energy_expression_file.split('resources/')[1]
        if force_constant_for_biased is None:
            force_constant_for_biased = self._force_constant_for_biased

        for potential_center in list_of_potential_center:

            parameter_list = (str(CONFIG_16), str(num_of_simulation_steps), str(force_constant_for_biased),
                            str(potential_center[0]), str(potential_center[1]),
                            'network_' + str(self._mynetwork._index),
                            filename_of_energy_expression)

            file_name = "../sge_files/job_biased_%s_%s_%s_%s_%s_%s_%s.sge" % parameter_list
            command = "python ../src/biased_simulation.py %s %s %s %s %s %s %s" % parameter_list
            # with open("temp_command_file_%d.txt" % (self._mynetwork._index), 'a') as temp_command_f:  # FIXME: use better implementation later
            #     temp_command_f.write('nohup  ' + command + " &\n")

            print("creating %s" % file_name)

            content_for_sge_files = '''#!/bin/bash

#$ -S /bin/bash           # use bash shell
#$ -V                     # inherit the submission environment
#$ -cwd                   # start job in submission directory

#$ -m ae                 # email on abort, begin, and end
#$ -M wei.herbert.chen@gmail.com         # email address

#$ -q all.q               # queue name
#$ -l h_rt=%s       # run time (hh:mm:ss)
####$ -l hostname=compute-0-3

%s

echo "This job is DONE!"

exit 0
''' % (CONFIG_19, command)

            with open(file_name, 'w') as f_out:
                f_out.write(content_for_sge_files)
                f_out.write("\n")

        return


    # @staticmethod
    # def run_one_command(filename = 'simulation_command_todo_list.txt', run_method = 'local'):
    #     '''
    #     this function picks the first command in the todo list and run it,
    #     :param run_method: 'local' means running the command in local machine, 'cluster' means running in cluster
    #     TODO:
    #     '''
    #     with open(filename, 'r') as in_file:
    #         all_commands = in_file.read().split('\n')[:-1]
    #
    #     first_command = all_commands[0]
    #     if run_method == 'local':
    #         subprocess.check_output(first_command.split())  # run this command locally
    #     elif run_method == 'cluster':
    #         pass
    #         # TODO
    #     else:
    #         pass
    #         # TODO
    #
    #
    #     return



    @staticmethod
    def get_num_of_running_jobs():
        output = subprocess.check_output(['qstat'])
        num_of_running_jobs = len(re.findall('weichen9', output))
        print('checking number of running jobs = %d\n' % num_of_running_jobs)
        return num_of_running_jobs

    @staticmethod
    def submit_sge_jobs_and_archive_files(job_file_lists,
                                          num,  # num is the max number of jobs submitted each time
                                          flag_of_whether_to_record_qsub_commands = False
                                          ):
        dir_to_archive_files = '../sge_files/archive/'

        if not os.path.exists(dir_to_archive_files):
            os.makedirs(dir_to_archive_files)

        assert(os.path.exists(dir_to_archive_files))

        for item in job_file_lists[0:num]:
            subprocess.check_output(['qsub', item])
            print('submitting ' + str(item))
            subprocess.check_output(['mv', item, dir_to_archive_files]) # archive files
        return

    @staticmethod
    def get_sge_files_list():
        result = filter(lambda x: x[-3:] == "sge",subprocess.check_output(['ls', '../sge_files']).split('\n'))
        result = map(lambda x: '../sge_files/' + x, result)
        return result

    @staticmethod
    def submit_new_jobs_if_there_are_too_few_jobs(num):
        if simulation_management.get_num_of_running_jobs() < num:
            job_list = simulation_management.get_sge_files_list()
            simulation_management.submit_sge_jobs_and_archive_files(job_list, num)
        return

    @staticmethod
    def monitor_status_and_submit_periodically(num,
                                               num_of_running_jobs_when_allowed_to_stop = 0,
                                               monitor_mode = 'normal',  # monitor_mode determines whether it can go out of first while loop
                                               ):
        if monitor_mode == 'normal':
            min_num_of_unsubmitted_jobs = 0
        elif monitor_mode == 'always_wait_for_submit':
            min_num_of_unsubmitted_jobs = -1

        num_of_unsubmitted_jobs = len(simulation_management.get_sge_files_list())
        # first check if there are unsubmitted jobs
        while num_of_unsubmitted_jobs > min_num_of_unsubmitted_jobs:
            time.sleep(10)
            try:
                simulation_management.submit_new_jobs_if_there_are_too_few_jobs(num)
                num_of_unsubmitted_jobs = len(simulation_management.get_sge_files_list())
            except:
                print("not able to submit jobs!\n")

        # then check if all jobs are done
        while simulation_management.get_num_of_running_jobs() > num_of_running_jobs_when_allowed_to_stop:
            time.sleep(10)
        return

    @staticmethod
    def is_job_running_on_cluster(job_sgefile_name):
        output = subprocess.check_output(['qstat', '-r'])
        return job_sgefile_name in output

    @staticmethod
    def check_whether_job_finishes_successfully(job_sgefile_name, latest_version = True):
        """
        return value:
        0: finishes successfully
        1: finishes with exception
        2: aborted due to time limit or other reason
        -1: job does not exist
        """
        job_finished_message = 'This job is DONE!\n'
        # first we check whether the job finishes
        if simulation_management.is_job_running_on_cluster(job_sgefile_name):
            return 0  # not finished
        else:
            all_files_in_this_dir = subprocess.check_output(['ls']).split()

            out_file_list = filter(lambda x: job_sgefile_name in x and ".o" in x, all_files_in_this_dir)
            err_file_list = filter(lambda x: job_sgefile_name in x and ".e" in x, all_files_in_this_dir)

            if len(out_file_list) == 0 or len(err_file_list) == 0:
                return -1   # job does not exist

            if latest_version:
                job_serial_number_list = map(lambda x: int(x.split('.sge.o')[1]), out_file_list)
                job_serial_number_of_latest_version = max(job_serial_number_list)
                latest_out_file = filter(lambda x: str(job_serial_number_of_latest_version) in x, out_file_list)[0]
                latest_err_file = filter(lambda x: str(job_serial_number_of_latest_version) in x, err_file_list)[0]
                with open(latest_out_file, 'r') as out_f:
                    out_content = out_f.readlines()
                with open(latest_err_file, 'r') as err_f:
                    err_content = err_f.readlines()
                    err_content = filter(lambda x: x[:4] != 'bash', err_content)  # ignore error info starting with "bash"

                if (job_finished_message in out_content) and (len(err_content) != 0):
                    return 1  # ends with exception
                elif not job_finished_message in out_content:
                    return 2  # aborted due to time limit or other reason
            else:
                # TODO: handle this case
                return


class iteration(object):
    def __init__(self, index,
                 network=None # if you want to start with existing network, assign value to "network"
                 ):
        self._index = index
        self._network = network

    def train_network_and_save(self, training_interval=None, num_of_trainings = CONFIG_13):
        '''num_of_trainings is the number of trainings that we are going to run, and 
        then pick one that has the largest Fraction of Variance Explained (FVE),
        by doing this, we might avoid network with very poor quality
        '''
        if training_interval is None: training_interval = self._index  # to avoid too much time on training
        my_file_list = coordinates_data_files_list(list_of_dir_of_coor_data_files=['../target']).get_list_of_coor_data_files()
        data_set = sutils.get_many_cossin_from_coordiantes_in_list_of_files(my_file_list)

        max_FVE = 0
        current_network = None
        for item in range(num_of_trainings):
            temp_network = neural_network_for_simulation(index=self._index,
                                                         data_set_for_training= data_set,
                                                         training_data_interval=training_interval,
                                                        )

            temp_network.train()
            print("temp FVE = %f" % (temp_network.get_fraction_of_variance_explained()))
            if temp_network.get_fraction_of_variance_explained() > max_FVE:
                max_FVE = temp_network.get_fraction_of_variance_explained()
                print("max_FVE = %f" % max_FVE)
                assert(max_FVE > 0)
                current_network = copy.deepcopy(temp_network)

        current_network.save_into_file()
        self._network = current_network
        return

    def prepare_simulation(self):
        self._network.write_expression_into_file()

        manager = simulation_management(self._network)
        manager.create_sge_files_for_simulation()
        return

    def run_simulation(self):
        manager = simulation_management(self._network)
        manager.monitor_status_and_submit_periodically(num = CONFIG_14,
                                        num_of_running_jobs_when_allowed_to_stop = CONFIG_15)
        sutils.generate_coordinates_from_pdb_files()
        return


class simulation_with_ANN_main(object):
    def __init__(self, num_of_iterations = 1,
                 initial_iteration=None,  # this is where we start with
                 training_interval = None,
                 ):
        self._num_of_iterations = num_of_iterations
        self._initial_iteration = initial_iteration
        self._training_interval = training_interval
        return

    def run_one_iteration(self, one_iteration):
        if one_iteration is None:
            one_iteration = iteration(1, network=None)
        if one_iteration._network is None:
            one_iteration.train_network_and_save(training_interval = self._training_interval)   # train it if it is empty

        one_iteration.prepare_simulation()
        one_iteration.run_simulation()
        print('running this iteration #index = %d' % one_iteration._index)
        return

    def run_mult_iterations(self, num=None):
        if num is None: num = self._num_of_iterations

        current_iter = self._initial_iteration
        for item in range(num):
            self.run_one_iteration(current_iter)
            next_index = current_iter._index + 1
            current_iter = iteration(next_index, None)

        return

class single_biased_simulation_data(object):
    '''TODO: This class is not completed'''
    def __init__(self, my_network, file_for_single_biased_simulation_coor):
        '''my_network is the corresponding network for this biased simulation'''
        self._file_for_single_biased_simulation_coor = file_for_single_biased_simulation_coor
        self._my_network = my_network
        self._potential_center = [float(file_for_single_biased_simulation_coor.split('_x1_')[1].split('_x2_')[0]), \
                                  float(file_for_single_biased_simulation_coor.split('_x2_')[1].split('_coordinates.txt')[0])]
        self._force_constant = float(file_for_single_biased_simulation_coor.split('biased_output_fc_')[1].split('_x1_')[0])
        self._number_of_data = float(subprocess.check_output(['wc', '-l', file_for_single_biased_simulation_coor]).split()[0])
        return

    def get_center_of_data_cloud_in_this_biased_simulation(self):
        cossin = sutils.get_many_cossin_from_coordiantes_in_list_of_files([self._file_for_single_biased_simulation_coor])
        temp_mid_result = self._my_network.get_mid_result(input_data = cossin)
        PCs = [item[1] for item in temp_mid_result]
        assert(len(PCs[0]) == 2)
        assert(len(PCs) == self._number_of_data)
        PCs_transpose = zip(*PCs)
        center_of_data_cloud = map(lambda x: sum(x) / len(x), PCs_transpose)
        return center_of_data_cloud

    def get_offset_between_potential_center_and_data_cloud_center(self):
        '''see if the push in this biased simulation actually works, large offset means it
        does not work well
        '''
        PCs_average = self.get_center_of_data_cloud_in_this_biased_simulation()
        offset = [PCs_average[0] - self._potential_center[0], PCs_average[1] - self._potential_center[1]]
        return offset

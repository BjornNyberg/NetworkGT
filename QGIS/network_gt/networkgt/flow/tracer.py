import numpy as np
import scipy.sparse as sps
import porepy as pp

from flow import Flow

class Tracer(object):

    # post process variables
    tracer = "tracer"
    flux = "darcy_flux"

    # discretization operator name
    discr = pp.Upwind
    coupling = pp.UpwindCoupling
    mass = pp.MassMatrix

    # ------------------------------------------------------------------------------#

    def __init__(self, gb, model="tracer", flow_model="flow"):

        self.gb = gb
        self.data = None
        self.bc_flag = None
        self.assembler = None

        # discretization class variables
        self.model = model
        self.flow_model = flow_model

        self.discr_name = self.model + "_tracer"
        self.coupling_name = self.discr_name + "_coupling"
        self.mass_name = self.model + "_mass"

        self.variable = self.model + "_variable"
        self.mortar = self.model + "_lambda"

        # class used to get the names from the flow problem
        self.flow = Flow(flow_model)

    # ------------------------------------------------------------------------------#

    def set_data(self, data, bc_flag):
        self.data = data
        self.bc_flag = bc_flag
        self.time_step = data["end_time"]/float(data["num_steps"])
        self.all_time = np.arange(self.data["num_steps"]) * self.time_step

        # set the data for the nodes
        self._set_data_nodes()
        # set the data for the edges, if present
        if self.gb.num_graph_edges():
            self._set_data_edges()

        # assembler
        variables = [self.variable, self.mortar]
        self.assembler = pp.Assembler(self.gb, active_variables=variables)

    # ------------------------------------------------------------------------------#

    def solve(self):
        # consturct the matrices
        self.assembler.discretize()
        block_A, block_b = self.assembler.assemble_matrix_rhs(add_matrices=False)

        # unpack the matrices just computed
        coupling_name = self.coupling_name + (
            "_" + self.mortar + "_" + self.variable + "_" + self.variable
        )
        discr_name = self.discr_name + "_" + self.variable
        mass_name = self.mass_name + "_" + self.variable

        # extract the matrices
        M = block_A[mass_name]

        if self.gb.size() > 1:
            A = block_A[discr_name] + block_A[coupling_name]
            b = block_b[discr_name] + block_b[coupling_name]
        else:
            A = block_A[discr_name]
            b = block_b[discr_name]

        M_A = M + A
        tr = np.zeros(b.size, dtype=np.float)

        for time_step in np.arange(self.data["num_steps"]):
            # solve the problem
            tr = sps.linalg.spsolve(M_A, M*tr + b)

            # distribute the variables
            self.assembler.distribute_variable(tr)

            # split the variables
            var_name = self.variable + "_" + str(time_step)
            for g, d in self.gb:
                d[pp.STATE][var_name] = d[pp.STATE][self.variable]

    # ------------------------------------------------------------------------------#

    def _set_data_nodes(self):
        """ Method to set the data for the nodes (grids) of the grid bucket

        """
        for g, d in self.gb:

            param = {}
            param_mass = {}

            unity = np.ones(g.num_cells)
            zeros = np.zeros(g.num_cells)
            empty = np.empty(0)

            d["tol"] = self.data["tol"]

            # Boundaries
            b_faces = g.tags["domain_boundary_faces"].nonzero()[0]
            if b_faces.size:
                labels, bc_val = self.bc_flag(self.gb, g, self.data, self.data["tol"])
                param["bc"] = pp.BoundaryCondition(g, b_faces, labels)
            else:
                bc_val = np.zeros(g.num_faces)
                param["bc"] = pp.BoundaryCondition(g, empty, empty)

            param["bc_values"] = bc_val
            pp.initialize_data(g, d, self.discr_name, param)
            d[pp.PARAMETERS][self.discr_name][self.flux] = d[pp.STATE][self.flow.flux]

            param_mass["mass_weight"] = 1. / self.time_step
            pp.initialize_data(g, d, self.mass_name, param_mass)

            # set the primary variable
            d[pp.PRIMARY_VARIABLES] = {self.variable: {"cells": 1}}
            # set the discretization
            node_discr = self.discr(self.discr_name)
            node_mass = self.mass(self.mass_name)
            d[pp.DISCRETIZATION] = {self.variable: {self.discr_name: node_discr,
                                                    self.mass_name: node_mass}}
            # set the discretization matrix
            d[pp.DISCRETIZATION_MATRICES] = {self.discr_name: {},
                                             self.mass_name: {}}

    # ------------------------------------------------------------------------------#

    def _set_data_edges(self):
        # define the interface terms to couple the grids
        for e, d in self.gb.edges():
            g_slave, g_master = self.gb.nodes_of_edge(e)
            # set the primary variable
            d[pp.PRIMARY_VARIABLES] = {self.mortar: {"cells": 1}}
            # define the coupling
            edge_coupling = self.coupling(self.discr_name)
            # set the discretization of the coupling
            d[pp.COUPLING_DISCRETIZATION] = {
                self.coupling_name: {
                    g_slave: (self.variable, self.discr_name),
                    g_master: (self.variable, self.discr_name),
                    e: (self.mortar, edge_coupling)}}
            # set the discretization matrix
            d[pp.DISCRETIZATION_MATRICES] = {self.discr_name: {}}
            d[pp.PARAMETERS] = {self.discr_name: {}}
            d[pp.PARAMETERS][self.discr_name][self.flux] = d[pp.STATE][self.flow.mortar]

    # ------------------------------------------------------------------------------#

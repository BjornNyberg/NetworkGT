import numpy as np
import scipy.sparse as sps
import porepy as pp

class Flow(object):

    # ------------------------------------------------------------------------------#

    # post process variables
    pressure = "pressure"
    flux = "darcy_flux"  # it has to be this one
    P0_flux = "P0_darcy_flux"
    norm_flux = "norm_flux"
    azimuth = "azimuth"

    # discretization operator
    discr = pp.Tpfa

    # ------------------------------------------------------------------------------#

    def __init__(self, gb, model="flow"):

        self.gb = gb
        self.data = None
        self.bc_flag = None
        self.assembler = None

        # discretization class variables
        self.model = model
        self.discr_name = self.model + "_flux"
        self.coupling_name = self.discr_name + "_coupling"

        # discretization variables
        self.variable = self.model + "_variable"
        self.mortar = self.model + "_lambda"

    # ------------------------------------------------------------------------------#

    def set_data(self, data, bc_flag):
        """ Set the data of the problem
        """
        self.data = data
        self.bc_flag = bc_flag

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

        # in the case the fractures are scaled modify the problem
        if self.data.get("length_ratio", None) is not None:
            for g, d in self.gb:
                if g.dim == 1:
                    ratio = self.data["length_ratio"][g.frac_num]
                    d[pp.DISCRETIZATION_MATRICES][self.model]["flux"] *= ratio
                    d[pp.DISCRETIZATION_MATRICES][self.model]["bound_flux"] *= ratio
                    d[pp.DISCRETIZATION_MATRICES][self.model]["bound_pressure_face"] *= ratio
                    d[pp.DISCRETIZATION_MATRICES][self.model]["bound_pressure_cell"] *= ratio

        A, b = self.assembler.assemble_matrix_rhs()

        # solve the problem
        p = sps.linalg.spsolve(A, b)

        # distribute the variables
        self.assembler.distribute_variable(p)

        # split the variables
        for g, d in self.gb:
            d[pp.STATE][self.pressure] = d[pp.STATE][self.variable]
            d[pp.STATE][self.P0_flux] = np.zeros(g.num_cells)
            d[pp.PARAMETERS][self.model][self.flux] = np.zeros(g.num_faces)

        # reconstruct the Darcy flux
        pp.fvutils.compute_darcy_flux(self.gb, keyword=self.model, d_name=self.flux,
                                      p_name=self.pressure, lam_name=self.mortar)

        # split the darcy flux on each grid-bucket grid
        for _, d in self.gb:
            d[pp.STATE][self.flux] = d[pp.PARAMETERS][self.model][self.flux]

        for e, d in self.gb.edges():
            _, g_master = self.gb.nodes_of_edge(e)
            if g_master.dim == 1:
                ratio = self.data["length_ratio"][g_master.frac_num]
                d[pp.PARAMETERS][self.model][self.flux] *= ratio
            d[pp.STATE][self.mortar] = d[pp.PARAMETERS][self.model][self.flux]

        # export the P0 flux reconstruction
        pp.project_flux(self.gb, pp.MVEM(self.model), self.flux, self.P0_flux, self.mortar)

        # compute the module of the flow velocity and the azimuth
        for g, d in self.gb:
            P0_flux = d[pp.STATE][self.P0_flux]

            norm = np.sqrt(np.einsum("ij,ij->j", P0_flux, P0_flux))
            d[pp.STATE][self.norm_flux] = norm

            north = self.data["north"] / np.linalg.norm(self.data["north"])
            P0_flux_dir = np.divide(P0_flux, norm)

            azimuth = np.arctan2(P0_flux_dir[1, :], P0_flux_dir[0, :]) - \
                      np.arctan2(north[1], north[0]);

            d[pp.STATE][self.azimuth] = azimuth

    # ------------------------------------------------------------------------------#

    def _set_data_nodes(self):
        """ Method to set the data for the nodes (grids) of the grid bucket

        """
        for g, d in self.gb:

            param = {}

            d["Aavatsmark_transmissibilities"] = True
            d["tol"] = self.data["tol"]

            # assign permeability
            if g.dim == 2:
                perm = pp.SecondOrderTensor(kxx=self.data["kxx"], kyy=self.data["kyy"], kxy=self.data["kxy"])
                param["second_order_tensor"] = perm
            elif g.dim == 1:
                k = self.data["k"][g.frac_num]
                perm = pp.SecondOrderTensor(kxx=k*np.ones(g.num_cells))
                param["second_order_tensor"] = perm

            # Boundaries
            b_faces = g.tags["domain_boundary_faces"].nonzero()[0]
            if b_faces.size:
                labels, bc_val = self.bc_flag(self.gb, g, self.data, self.data["tol"])
                param["bc"] = pp.BoundaryCondition(g, b_faces, labels)
            else:
                bc_val = np.zeros(g.num_faces)
                param["bc"] = pp.BoundaryCondition(g, np.empty(0), np.empty(0))

            param["bc_values"] = bc_val
            pp.initialize_data(g, d, self.model, param)

            # set the primary variable
            d[pp.PRIMARY_VARIABLES] = {self.variable: {"cells": 1}}
            # set the discretization
            node_discr = self.discr(self.model)
            d[pp.DISCRETIZATION] = {self.variable: {self.discr_name: node_discr}}
            # set the discretization matrix
            d[pp.DISCRETIZATION_MATRICES] = {self.model: {}}

    # ------------------------------------------------------------------------------#

    def _set_data_edges(self):
        """ Method to set the data for the edges (mortar grids) of the grid bucket
        """
        raise NotImplementedError("To be implemented")

#################################################################################

class Flow_Model1(Flow):
    """ Implement the flux continuity among objects
    """
    # ------------------------------------------------------------------------------#

    coupling = pp.FluxPressureContinuity

    def __init__(self, gb, model="flow"):
        Flow.__init__(self, gb, model)

    # ------------------------------------------------------------------------------#

    def _set_data_edges(self):
        """ Method to set the data for the edges (mortar grids) of the grid bucket
        """
        # define the interface terms to couple the grids
        for e, d in self.gb.edges():
            g_slave, g_master = self.gb.nodes_of_edge(e)
            # set the primary variable
            d[pp.PRIMARY_VARIABLES] = {self.mortar: {"cells": 1}}
            # define the coupling
            node_discr = self.discr(self.model)
            edge_coupling = self.coupling(self.model, node_discr)
            # set the discretization of the coupling
            d[pp.COUPLING_DISCRETIZATION] = {
                self.coupling_name: {
                    g_slave: (self.variable, self.discr_name),
                    g_master: (self.variable, self.discr_name),
                    e: (self.mortar, edge_coupling)}}
            # set the discretization matrix
            d[pp.DISCRETIZATION_MATRICES] = {self.model: {}}
            d[pp.PARAMETERS] = {self.model: {}}

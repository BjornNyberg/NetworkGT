"""
Module for extending the Upwind, MPFA and MassMatrix discretizations in Porepy to handle
implicit Euler time-stepping. Flux terms are multiplied by time step and the mass term
has a rhs contribution from the previous time step.
See the parent discretizations for further documentation.
"""
import porepy as pp
import numpy as np
import scipy.sparse as sps


class ImplicitMassMatrix(pp.MassMatrix):
    """
    Return rhs contribution based on the previous solution, which is stored in the
    pp.STATE field of the data dictionary.
    """

    def __init__(self, keyword="flow", variable="pressure"):
        """ Set the discretization, with the keyword used for storing various
        information associated with the discretization. The time discretisation also
        requires the previous solution, thus the variable needs to be specified.

        Paramemeters:
            keyword (str): Identifier of all information used for this
                discretization.
        """
        super().__init__(keyword)
        self.variable = variable

    def assemble_rhs(self, g, data):
        """ Overwrite MassMatrix method to return the correct rhs for an IE time
        discretization, e.g. of the Biot problem.
        """
        matrix_dictionary = data[pp.DISCRETIZATION_MATRICES][self.keyword]
        previous_solution = data[pp.STATE][self.variable]

        return matrix_dictionary["mass"] * previous_solution


class ImplicitMpfa(pp.Mpfa):
    """
    Multiply all contributions by the time step.
    """

    def assemble_matrix_rhs(self, g, data):
        """ Overwrite MPFA method to be consistent with the Biot dt convention.
        """
        a, b = super().assemble_matrix_rhs(g, data)
        dt = data[pp.PARAMETERS][self.keyword]["time_step"]
        a = a * dt
        b = b * dt
        return a, b

    def assemble_int_bound_flux(
        self, g, data, data_edge, cc, matrix, rhs, self_ind, use_slave_proj=False
    ):
        """
        Overwrite the MPFA method to be consistent with the Biot dt convention
        """
        dt = data[pp.PARAMETERS][self.keyword]["time_step"]

        div = g.cell_faces.T

        bound_flux = data[pp.DISCRETIZATION_MATRICES][self.keyword]["bound_flux"]
        # Projection operators to grid
        mg = data_edge["mortar_grid"]

        if use_slave_proj:
            proj = mg.mortar_to_slave_int()
        else:
            proj = mg.mortar_to_master_int()

        if g.dim > 0 and bound_flux.shape[0] != g.num_faces:
            # If bound flux is gven as sub-faces we have to map it from sub-faces
            # to faces
            hf2f = pp.fvutils.map_hf_2_f(nd=1, g=g)
            bound_flux = hf2f * bound_flux
        if g.dim > 0 and bound_flux.shape[1] != proj.shape[0]:
            raise ValueError(
                """Inconsistent shapes. Did you define a
            sub-face boundary condition but only a face-wise mortar?"""
            )

        cc[self_ind, 2] += dt * div * bound_flux * proj

    def assemble_int_bound_source(self, g, data, data_edge, cc, matrix, rhs, self_ind):
        """ Abstract method. Assemble the contribution from an internal
        boundary, manifested as a source term.

        The intended use is when the internal boundary is coupled to another
        node in a mixed-dimensional method. Specific usage depends on the
        interface condition between the nodes; this method will typically be
        used to impose flux continuity on a lower-dimensional domain.

        Implementations of this method will use an interplay between the grid on
        the node and the mortar grid on the relevant edge.

        Parameters:
            g (Grid): Grid which the condition should be imposed on.
            data (dictionary): Data dictionary for the node in the
                mixed-dimensional grid.
            data_edge (dictionary): Data dictionary for the edge in the
                mixed-dimensional grid.
            cc (block matrix, 3x3): Block matrix for the coupling condition.
                The first and second rows and columns are identified with the
                master and slave side; the third belongs to the edge variable.
                The discretization of the relevant term is done in-place in cc.
            matrix (block matrix 3x3): Discretization matrix for the edge and
                the two adjacent nodes.
            rhs (block_array 3x1): Right hand side contribution for the edge and
                the two adjacent nodes.
            self_ind (int): Index in cc and matrix associated with this node.
                Should be either 1 or 2.

        """
        mg = data_edge["mortar_grid"]

        proj = mg.mortar_to_slave_int()
        dt = data[pp.PARAMETERS][self.keyword]["time_step"]
        cc[self_ind, 2] -= proj * dt


class ImplicitTpfa(pp.Tpfa):
    """
    Multiply all contributions by the time step.

    Implementation note: This is a copy of ImplicitMpfa, modified to inherit from Tpfa.
    A unified implementation would have been preferrable.

    """

    def assemble_matrix_rhs(self, g, data):
        """ Overwrite MPFA method to be consistent with the Biot dt convention.
        """
        a, b = super().assemble_matrix_rhs(g, data)
        dt = data[pp.PARAMETERS][self.keyword]["time_step"]
        a = a * dt
        b = b * dt
        return a, b

    def assemble_int_bound_flux(
        self, g, data, data_edge, cc, matrix, rhs, self_ind, use_slave_proj=False
    ):
        """
        Overwrite the MPFA method to be consistent with the Biot dt convention
        """
        dt = data[pp.PARAMETERS][self.keyword]["time_step"]

        div = g.cell_faces.T

        bound_flux = data[pp.DISCRETIZATION_MATRICES][self.keyword]["bound_flux"]
        # Projection operators to grid
        mg = data_edge["mortar_grid"]

        if use_slave_proj:
            proj = mg.mortar_to_slave_int()
        else:
            proj = mg.mortar_to_master_int()

        if g.dim > 0 and bound_flux.shape[0] != g.num_faces:
            # If bound flux is gven as sub-faces we have to map it from sub-faces
            # to faces
            hf2f = pp.fvutils.map_hf_2_f(nd=1, g=g)
            bound_flux = hf2f * bound_flux
        if g.dim > 0 and bound_flux.shape[1] != proj.shape[0]:
            raise ValueError(
                """Inconsistent shapes. Did you define a
            sub-face boundary condition but only a face-wise mortar?"""
            )

        cc[self_ind, 2] += dt * div * bound_flux * proj

    def assemble_int_bound_source(self, g, data, data_edge, cc, matrix, rhs, self_ind):
        """ Abstract method. Assemble the contribution from an internal
        boundary, manifested as a source term.

        The intended use is when the internal boundary is coupled to another
        node in a mixed-dimensional method. Specific usage depends on the
        interface condition between the nodes; this method will typically be
        used to impose flux continuity on a lower-dimensional domain.

        Implementations of this method will use an interplay between the grid on
        the node and the mortar grid on the relevant edge.

        Parameters:
            g (Grid): Grid which the condition should be imposed on.
            data (dictionary): Data dictionary for the node in the
                mixed-dimensional grid.
            data_edge (dictionary): Data dictionary for the edge in the
                mixed-dimensional grid.
            cc (block matrix, 3x3): Block matrix for the coupling condition.
                The first and second rows and columns are identified with the
                master and slave side; the third belongs to the edge variable.
                The discretization of the relevant term is done in-place in cc.
            matrix (block matrix 3x3): Discretization matrix for the edge and
                the two adjacent nodes.
            rhs (block_array 3x1): Right hand side contribution for the edge and
                the two adjacent nodes.
            self_ind (int): Index in cc and matrix associated with this node.
                Should be either 1 or 2.

        """
        mg = data_edge["mortar_grid"]

        proj = mg.mortar_to_slave_int()
        dt = data[pp.PARAMETERS][self.keyword]["time_step"]
        cc[self_ind, 2] -= proj * dt


class ImplicitUpwind(pp.Upwind):
    """
    Multiply all contributions by the time step and advection weight.
    """

    def assemble_matrix_rhs(self, g, data):
        if g.dim == 0:
            data["flow_faces"] = sps.csr_matrix([0.0])
            return sps.csr_matrix([0.0]), np.array([0.0])

        parameter_dictionary = data[pp.PARAMETERS][self.keyword]
        dt = parameter_dictionary["time_step"]
        w = parameter_dictionary["advection_weight"] * dt
        a, b = super().assemble_matrix_rhs(g, data)
        a = a * w
        b = b * w
        return a, b


class ImplicitUpwindCoupling(pp.UpwindCoupling):
    """
    Multiply the advective mortar fluxes by the time step and advection weight.
    """

    def assemble_matrix_rhs(
        self, g_master, g_slave, data_master, data_slave, data_edge, matrix
    ):
        """
        Construct the matrix (and right-hand side) for the coupling conditions.
        Note: the right-hand side is not implemented now.

        Parameters:
            matrix: Uncoupled discretization matrix.
            g_master: grid of higher dimension
            g_slave: grid of lower dimension
            data_master: dictionary which stores the data for the higher dimensional
                grid
            data_slave: dictionary which stores the data for the lower dimensional
                grid
            data: dictionary which stores the data for the edges of the grid
                bucket

        Returns:
            cc: block matrix which store the contribution of the coupling
                condition. See the abstract coupling class for a more detailed
                description.
        """

        # Normal component of the velocity from the higher dimensional grid

        # @ALL: This should perhaps be defined by a globalized keyword
        parameter_dictionary_master = data_master[pp.PARAMETERS][self.keyword]
        lam_flux = data_edge[pp.PARAMETERS][self.keyword]["darcy_flux"]
        dt = parameter_dictionary_master["time_step"]
        w = parameter_dictionary_master["advection_weight"] * dt
        # Retrieve the number of degrees of both grids
        # Create the block matrix for the contributions
        g_m = data_edge["mortar_grid"]

        # We know the number of dofs from the master and slave side from their
        # discretizations
        dof = np.array([matrix[0, 0].shape[1], matrix[1, 1].shape[1], g_m.num_cells])
        cc = np.array([sps.coo_matrix((i, j)) for i in dof for j in dof])
        cc = cc.reshape((3, 3))

        # Projection from mortar to upper dimenional faces
        hat_P_avg = g_m.master_to_mortar_avg()
        # Projection from mortar to lower dimensional cells
        check_P_avg = g_m.slave_to_mortar_avg()

        # mapping from upper dim cellls to faces
        # The mortars always points from upper to lower, so we don't flip any
        # signs
        div = np.abs(pp.numerics.fv.fvutils.scalar_divergence(g_master))

        # Find upwind weighting. if flag is True we use the upper weights
        # if flag is False we use the lower weighs
        flag = (lam_flux > 0).astype(float)
        not_flag = 1 - flag

        # assemble matrices
        # Transport out of upper equals lambda
        cc[0, 2] = div * hat_P_avg.T

        # transport out of lower is -lambda
        cc[1, 2] = -check_P_avg.T

        # Discretisation of mortars
        # CHANGE from UpwindCoupling: multiply the discretization of the advective
        # mortar fluxes by dt and advection weight (e.g. heat capacity)

        # If fluid flux(lam_flux) is positive we use the upper value as weight,
        # i.e., T_masterat * fluid_flux = lambda.
        # We set cc[2, 0] = T_masterat * fluid_flux
        cc[2, 0] = sps.diags(w * lam_flux * flag) * hat_P_avg * div.T

        # If fluid flux is negative we use the lower value as weight,
        # i.e., T_check * fluid_flux = lambda.
        # we set cc[2, 1] = T_check * fluid_flux
        cc[2, 1] = sps.diags(w * lam_flux * not_flag) * check_P_avg

        # The rhs of T * fluid_flux = lambda
        # Recover the information for the grid-grid mapping
        cc[2, 2] = -sps.eye(g_m.num_cells)

        if data_master["node_number"] == data_slave["node_number"]:
            # All contributions to be returned to the same block of the
            # global matrix in this case
            cc = np.array([np.sum(cc, axis=(0, 1))])

        # rhs is zero
        rhs = np.squeeze([np.zeros(dof[0]), np.zeros(dof[1]), np.zeros(dof[2])])
        matrix += cc
        return matrix, rhs

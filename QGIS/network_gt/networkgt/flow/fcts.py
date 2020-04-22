import numpy as np
import porepy as pp

# --------------------------------------------------------------------------- #

def read_network(file_name, **kwargs):
    """
    Read the global network and return the biggest one
    """

    # read the csv file pp format
    network, frac_id = pp.fracture_importer.network_2d_from_csv(file_name, return_frac_id=True, **kwargs)

    pts_shift = np.amin(network.pts, axis=1)
    pts_shift = np.atleast_2d(pts_shift).T

    # shift the points more in the origin
    network.pts -= pts_shift

    # define the domain as bounding box on the fractures
    network.domain = pp.bounding_box.from_points(network.pts, overlap=kwargs["tol"])

    return network, frac_id, pts_shift

    ##### we might have differente unconnected networks, split them
    ####sub_networks = network.connected_networks()

    ##### NOTE: we keep the biggest network, meaning the one with bigger diagonal of the bounding box
    ####diam = np.zeros(sub_networks.size)
    ####for idx, sub_network in enumerate(sub_networks):
    ####    # remove unused points in the network
    ####    sub_network.purge_pts()

    ####    # compute the diameter of the current network
    ####    b_box = pp.bounding_box.from_points(sub_network.pts)
    ####    diam[idx] = np.sqrt((b_box["xmax"] - b_box["xmin"])**2 +
    ####                        (b_box["ymax"] - b_box["ymin"])**2)

    ####    # update the domain as the bounding box
    ####    sub_network.domain = b_box

    ##### remove dangling end

    ##### return the selected network
    ####return sub_networks[np.argmax(diam)]

# --------------------------------------------------------------------------- #

# Read the grid
def read_cart_grid(nx, ny, lx=1, ly=1):
    gb = pp.meshing.cart_grid([], [nx, ny], physdims=[lx, ly])
    gb.compute_geometry()
    return gb

# --------------------------------------------------------------------------- #

def argsort_cart_grid(nx, ny):
    """ Return the cell mapping according to qgis way of passing the input data.
    """
    order_qgis = np.arange(nx*ny).reshape((nx, ny))[:, ::-1].T
    order_qgis = order_qgis.flatten()
    return order_qgis, np.argsort(order_qgis)

# --------------------------------------------------------------------------- #

def bc_flag(gb, g, data, tol):
    """
    The dictionary data requires the following parameters:
    - flow_direction, possible values:
            left_to_right, right_to_left, bottom_to_top, and top_to_bottom
    - low_value
    - high_value
    """
    b_faces, b_low, b_high = _bc_dir(gb, g, data["flow_direction"], tol)

    # define the labels and values for the boundary faces
    labels = np.array(["neu"] * b_faces.size)
    labels[np.logical_or(b_low, b_high)] = "dir"

    if data["low_value"] >= data["high_value"]:
        raise ValueError("The low value has to be smaller than the high value in the boundary")

    bc_val = np.zeros(g.num_faces)
    bc_val[b_faces[b_low]] = data["low_value"]
    bc_val[b_faces[b_high]] = data["high_value"]

    return labels, bc_val

# --------------------------------------------------------------------------- #

def _bc_dir(gb, g, flow, tol):

    b_faces = g.tags["domain_boundary_faces"].nonzero()[0]
    b_face_centers = g.face_centers[:, b_faces]
    min_vals, max_vals = gb.bounding_box()

    if flow == "left_to_right":
        b_low = b_face_centers[0, :] > max_vals[0] - tol
        b_high = b_face_centers[0, :] < min_vals[0] + tol
    elif flow == "right_to_left":
        b_high = b_face_centers[0, :] > max_vals[0] - tol
        b_low = b_face_centers[0, :] < min_vals[0] + tol
    elif flow == "bottom_to_top":
        b_low = b_face_centers[1, :] > max_vals[1] - tol
        b_high = b_face_centers[1, :] < min_vals[1] + tol
    elif flow == "top_to_bottom":
        b_high = b_face_centers[1, :] > max_vals[1] - tol
        b_low = b_face_centers[1, :] < min_vals[1] + tol
    else:
        ValueError("Direction not defined properly")

    return b_faces, b_low, b_high

# --------------------------------------------------------------------------- #

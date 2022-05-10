import torch
import torch.nn.functional as F
import numpy as np

from .diff_operators import gradient


def triangle_area(triag_verts):
    """
    Computes the area of triangles given by their vertices

    Args:
        triag_verts (torch.Tensor): tensor with shape [*, 3, 3] with the vertices of each triangle
    
    Returns:
        torch.Tensor: tensor with shape [triag_verts.shape[0]] with the area of each triangle
    """
    edge1 = triag_verts[:, 0] - triag_verts[:, 1]
    edge2 = triag_verts[:, 1] - triag_verts[:, 2]

    return torch.norm(torch.cross(edge1, edge2), dim=1) / 2


def normalize_open3d_geometry(geometry, border=0):
    """
    Normalizes the open3d geometry to lie inside [-(1 - border), 1 - border]^3 by centering its bounding box
    to (0,0,0) and scaling uniformly using its largest axis as the inverse of the scale

    Args:
        geometry (open3d.geometry): The geometry to normalize
        border (optional float): This should be in [0, 1). Default value is 0.
    """
    aabb = geometry.get_axis_aligned_bounding_box()
    geometry.translate(-aabb.get_center())
    geometry.scale((1 - border) * 2 / aabb.get_max_extent(), np.zeros((3,1)))


def normalize_trimesh(mesh, border=0):
    """
    Normalizes a trimesh to lie inside [-(1 - border), 1 - border]^3 by centering its bounding box
    to (0,0,0) and scaling uniformly using its largest axis as the inverse of the scale

    Args:
        mesh (trimesh.Trimesh): The geometry to normalize
        border (optional float): This should be in [0, 1). Default value is 0.
    """
    bounds = mesh.bounds
    bounds_center = bounds.mean(0)
    max_extent = mesh.extents.max()
    mesh.apply_translation(-bounds_center)
    mesh.apply_scale((1 - border) * 2 / max_extent)    


def project_on_surface(model, samples, num_steps):
    samples = samples.detach()
    
    for i in range(num_steps):
        samples.requires_grad = True
        sdf_pred = model(samples)
        
        grad = gradient(sdf_pred, samples)
        samples  = samples.detach()
        sdf_pred = sdf_pred.detach()
        grad     = grad.detach()
        
        samples.addcmul_(F.normalize(grad, dim=1), sdf_pred, value=-1)
        
    return samples, sdf_pred, grad


def tangent_grad(grad, normal):
    n_comp = (grad * normal).sum(-1, keepdim=True)
    res = torch.addcmul(grad, n_comp, normal, value=-1)
    res.div_(-n_comp)
    return res


def lerp(x0, x1, t):
    y = torch.addcmul(x0, t, x0, value=-1)
    y.addcmul_(t, x1)
    return y


def slerp(x0, x1, t):
    # TODO: fix this, it gives nan
    dot = (x0 * x1).sum(-1)
    theta = torch.acos(dot, out=dot)
    sin_theta = torch.sin(theta)
    m0 = torch.sin((1-t) * theta) / sin_theta
    res = m0.unsqueeze(-1) * x0
    m1 = torch.sin(t * theta) / sin_theta
    res.addcmul_(m1.unsqueeze(-1), x1)
    return res


def smoothfall(x, radius=1, return_derivative=False):
    x = 1 - x / radius
    x_sq = x ** 2
    y = 3 * x_sq - 2 * x_sq * x

    if return_derivative:
        dy = 6 * (x_sq - x) / radius
        return y, dy
    else:
        return y

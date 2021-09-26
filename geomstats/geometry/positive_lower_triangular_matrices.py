"""The manifold of lower triangular matrices with positive diagonal elements"""

import math

import geomstats.backend as gs
from geomstats.geometry.base import OpenSet
from geomstats.geometry.general_linear import GeneralLinear
from geomstats.geometry.matrices import Matrices
from geomstats.geometry.riemannian_metric import RiemannianMetric
from geomstats.geometry.lower_triangular_matrices import LowerTriangularMatrices


class PositiveLowerTriangularMatrices(OpenSet):
    """Class for the manifold of lower triangular matrices with positive diagonal elements.

    Parameters
    ----------
    n : int
        Integer representing the shape of the matrices: n x n.

    References
        ----------
        .. [TP2019] . "Riemannian Geometry of Symmetric
        Positive Definite Matrices Via Cholesky Decomposition"
        SIAM journal on Matrix Analysis and Applications , 2019.
         https://arxiv.org/abs/1908.09326
    """

    def __init__(self, n, **kwargs):
        super(PositiveLowerTriangularMatrices, self).__init__(
            dim=int(n * (n + 1) / 2),
            metric=(CholeskyMetric(n)),
            ambient_space=LowerTriangularMatrices(n),
            **kwargs
        )
        self.n = n

    def belongs(self, mat, atol=gs.atol):
        """Check if a matrix is lower triangular matrix with
        positive diagonal elements

        Parameters
        ----------
        mat : array-like, shape=[..., n, n]
            Matrix to be checked.
        atol : float
            Tolerance.
            Optional, default: backend atol.

        Returns
        -------
        belongs : array-like, shape=[...,]
            Boolean denoting if mat is an SPD matrix.
        """
        is_lower_triangular = self.ambient_space.belongs(mat, atol)
        diagonal = gs.diagonal(mat)
        is_positive = gs.all(diagonal > 0, axis=-1)
        belongs = gs.logical_and(is_lower_triangular, is_positive)
        return belongs

    def projection(self, point):
        """Project a matrix to the cholesksy space.

        First it is projected to space lower triangular matrices
        and then diagonal elements are exponentiated to make it positive

        Parameters
        ----------
        point : array-like, shape=[..., n, n]
            Matrix to project.

        Returns
        -------
        projected: array-like, shape=[..., n, n]
            SPD matrix.
        """
        vec_diag = gs.exp(gs.diagonal(point, axis1=-2, axis2=-1))
        diag = gs.vec_to_diag(vec_diag)
        strictly_lower_triangular = Matrices.to_lower_triangular(point)
        projection = diag + strictly_lower_triangular
        return projection

    def gram(self, point):
        """Compute gram matrix of rows

        Gram_matrix is mapping from point to point.point^{T}.
        This is diffeomorphism between cholesky space and spd manifold

        Parameters
        ----------
        point : array-like, shape=[..., n, n]
            element in cholesky space

        Returns
        -------
        projected: array-like, shape=[..., n, n]
            SPD matrix.
        """
        return gs.einsum("...ij,...kj->...ik", point, point)

    @classmethod
    def differential_gram(cls, tanget_vec, base_point):
        """Compute gram matrix of rows

        Gram_matrix is mapping from point to point.point^{T}.
        This is diffeomorphism between cholesky space and spd manifold

        Parameters
        ----------
        tangent_vec : array_like, shape=[..., n, n]
            Tangent vector at base point.
        base_point : array_like, shape=[..., n, n]
            Base point.

        Returns
        -------
        differential_gram : array-like, shape=[..., n, n]
            Differential of the matrix exponential.
        """
        mat1 = gs.einsum("...ij,...kj->...ik", tanget_vec, base_point)
        mat2 = gs.einsum("...ij,...kj->...ik", base_point, tanget_vec)
        return mat1 + mat2

    @classmethod
    def inverse_differential_gram(cls, tanget_vec, base_point):
        """Compute gram matrix of rows

        Gram_matrix is mapping from point to point.point^{T}.
        This is diffeomorphism between PositiveLowerTriangular manifold
        and SPD manifold

        Parameters
        ----------
        tangent_vec : array_like, shape=[..., n, n]
            Tangent vector at base point.
        base_point : array_like, shape=[..., n, n]
            Base point.

        Returns
        -------
        inverse_differential_gram : array-like, shape=[..., n, n]
            Inverse of the differential of gram.
        """
        inv_base_point = gs.linalg.inv(base_point)
        inv_tranpose_base_point = Matrices.transpose(inv_base_point)
        aux1 = gs.einsum(
            "...ij,...jk,...kl->...il",
            inv_base_point,
            tanget_vec,
            inv_tranpose_base_point,
        )
        aux2 = Matrices.to_strictly_lower_triangular(aux1)
        aux3 = 0.5 * Matrices.to_diagonal(aux1)
        inverse_differential_gram = Matrices.mul(base_point, aux2 + aux3)
        return inverse_differential_gram


class CholeskyMetric(RiemannianMetric):
    """Class for the cholesky metric on the cholesky space."""

    def __init__(self, n):
        """Build the CholeskyMetric

        Parameters
        ----------
        n : int
            Integer representing the shape of the matrices: n x n.


        References
        ----------
        .. [TP2019] . "Riemannian Geometry of Symmetric
        Positive Definite Matrices Via Cholesky Decomposition"
        SIAM journal on Matrix Analysis and Applications , 2019.
         https://arxiv.org/abs/1908.09326
        """
        dim = int(n * (n + 1) / 2)
        super(CholeskyMetric, self).__init__(
            dim=dim, signature=(dim, 0), default_point_type="matrix"
        )
        self.n = n

    def diag_inner_product(self, tangent_vec_a, tangent_vec_b, base_point):
        """Compute the inner product using only diagonal elements.

        Parameters
        ----------
        tangent_vec_a : array-like, shape=[..., n, n]
            Tangent vector at base point.
        tangent_vec_b : array-like, shape=[..., n, n]
            Tangent vector at base point.
        base_point : array-like, shape=[..., n, n]
            Base point.

        Returns
        -------
        ip_diagonal : array-like, shape=[...]
            Inner-product.
        """

        inv_sqrt_diagonal = gs.power(gs.diagonal(base_point), -2)
        ip_diagonal = gs.einsum(
            "...ii,...ii ,...i->...", tangent_vec_a, tangent_vec_b, inv_sqrt_diagonal
        )
        return ip_diagonal

    def strictly_lower_inner_product(self, tangent_vec_a, tangent_vec_b, base_point):
        """Compute the inner product using only strictly lower triangular elements.

        Parameters
        ----------
        tangent_vec_a : array-like, shape=[..., n, n]
            Tangent vector at base point.
        tangent_vec_b : array-like, shape=[..., n, n]
            Tangent vector at base point.
        base_point : array-like, shape=[..., n, n]
            Base point.

        Returns
        -------
        ip_sl : array-like, shape=[...]
            Inner-product.
        """
        sl_tagnet_vec_a = gs.tril_to_vec(tangent_vec_a)
        sl_tagnet_vec_b = gs.tril_to_vec(tangent_vec_b)
        ip_sl = gs.einsum("...i, ...i-> ....", sl_tagnet_vec_a, sl_tagnet_vec_b)
        return ip_sl

    def inner_product(self, tangent_vec_a, tangent_vec_b, base_point):
        """Compute the inner product using only strictly lower triangular elements.


        Compute the inner-product of tangent_vec_a and tangent_vec_b
        at point base_point using the cholesky Riemannian metric.

        Parameters
        ----------
        tangent_vec_a : array-like, shape=[..., n, n]
            Tangent vector at base point.
        tangent_vec_b : array-like, shape=[..., n, n]
            Tangent vector at base point.
        base_point : array-like, shape=[..., n, n]
            Base point.

        Returns
        -------
        inner_product : array-like, shape=[...]
            Inner-product.
        """
        diag_inner_product = self.diag_inner_product(
            tangent_vec_a, tangent_vec_b, base_point
        )
        strictly_lower_inner_product = self.strictly_lower_inner_product(
            tangent_vec_a, tangent_vec_b, base_point
        )
        return diag_inner_product + strictly_lower_inner_product

    def exp(self, tangent_vec, base_point, **kwargs):
        """Compute the Cholesky exponential map.

        Compute the Riemannian exponential at point base_point
        of tangent vector tangent_vec wrt the Cholesky metric.
        This gives a lower triangular matrix with positive elements.

        Parameters
        ----------
        tangent_vec : array-like, shape=[..., n, n]
            Tangent vector at base point.
        base_point : array-like, shape=[..., n, n]
            Base point.

        Returns
        -------
        exp : array-like, shape=[..., n, n]
            Riemannian exponential.
        """
        sl_base_point = Matrices.to_strictly_lower_triangular(base_point)
        sl_tangent_vec = Matrices.to_strictly_lower_triangular(tangent_vec)
        diag_base_point = Matrices.diagonal(base_point)
        diag_tangent_vec = Matrices.diagonal(tangent_vec)
        diag_product_expm = gs.exp(gs.divide(diag_tangent_vec, diag_base_point))

        sl_exp = sl_base_point + sl_tangent_vec
        diag_exp = gs.vec_to_diag(diag_base_point * diag_product_expm)
        exp = sl_exp + diag_exp
        return exp

    def log(self, point, base_point, **kwargs):
        """Compute the Cholesky logarithm map.

        Compute the Riemannian logarithm at point base_point,
        of point wrt the Cholesky metric.
        This gives a tangent vector at point base_point.

        Parameters
        ----------
        point : array-like, shape=[..., n, n]
            Point.
        base_point : array-like, shape=[..., n, n]
            Base point.

        Returns
        -------
        log : array-like, shape=[..., n, n]
            Riemannian logarithm.
        """
        sl_base_point = Matrices.to_strictly_lower_triangular(base_point)
        sl_point = Matrices.to_strictly_lower_triangular(point)
        diag_base_point = Matrices.diagonal(base_point)
        diag_point = Matrices.diagonal(point)
        diag_product_logm = gs.log(gs.divide(diag_point, diag_base_point))

        sl_log = sl_point - sl_base_point
        diag_log = gs.vec_to_diag(diag_base_point * diag_product_logm)
        log = sl_log + diag_log
        return log

    def squared_dist(self, point_a, point_b, **kwargs):
        """Compute the Cholesky Metric squared distance.

        Compute the Riemannian squared distance between point_a and point_b.

        Parameters
        ----------
        point_a : array-like, shape=[..., n, n]
            Point.
        point_b : array-like, shape=[..., n, n]
            Point.

        Returns
        -------
        _ : array-like, shape=[...]
            Riemannian squared distance.
        """
        log_diag_a = gs.log(Matrices.diagonal(point_a))
        log_diag_b = gs.log(Matrices.diagonal(point_b))
        diag_diff = log_diag_a - log_diag_b
        squared_dist_diag = gs.sum((diag_diff) ** 2)

        sl_a = Matrices.to_strictly_lower_triangular(point_a)
        sl_b = Matrices.to_strictly_lower_triangular(point_b)
        sl_diff = sl_a - sl_b
        squared_dist_sl = Matrices.frobenius_product(sl_diff, sl_diff)
        return squared_dist_sl + squared_dist_diag

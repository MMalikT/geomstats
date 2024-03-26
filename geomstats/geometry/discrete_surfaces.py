"""Discrete Surfaces with Elastic metrics.

Lead authors: Emmanuel Hartman, Adele Myers.
"""

import math

import geomstats.backend as gs
from geomstats.geometry.euclidean import Euclidean
from geomstats.geometry.manifold import Manifold
from geomstats.geometry.matrices import Matrices
from geomstats.geometry.riemannian_metric import RiemannianMetric
from geomstats.numerics.geodesic import ExpSolver, PathStraightening
from geomstats.numerics.optimizers import ScipyMinimize
from geomstats.numerics.path import UniformlySampledDiscretePath
from geomstats.vectorization import get_batch_shape


class DiscreteSurfaces(Manifold):
    r"""Space of parameterized discrete surfaces.

    Each surface is sampled with fixed `n_vertices` vertices and `n_faces`
    faces in :math:`\mathbb{R}^3`.

    Each individual surface is represented by a 2d-array of shape
    `[n_vertices, 3]`. This space corresponds to the space of immersions
    defined below, i.e. the
    space of smooth functions from a template to manifold :math:`M`
    into :math:`\mathbb{R}^3`, with non-vanishing Jacobian.

    .. math::
        Imm(M,\mathbb{R}^3)=\{ f \in C^{\infty}(M, \mathbb{R}^3)
        \|Df(x)\|\neq 0 \forall x \in M \}.

    Parameters
    ----------
    faces : integer array-like, shape=[n_faces, 3]
        Triangulation of the surface.
        Each face is given by 3 indices that indicate its vertices.
    """

    def __init__(
        self,
        faces,
        equip=True,
    ):
        ambient_dim = 3
        self.ambient_manifold = Euclidean(dim=ambient_dim)
        self.faces = faces
        self.n_faces = len(faces)
        self.n_vertices = int(gs.amax(self.faces) + 1)
        self.shape = (self.n_vertices, ambient_dim)
        super().__init__(
            dim=self.n_vertices * ambient_dim,
            shape=(self.n_vertices, 3),
            equip=equip,
        )

    @staticmethod
    def default_metric():
        """Metric to equip the space with if equip is True."""
        return ElasticMetric

    def belongs(self, point, atol=gs.atol):
        """Evaluate whether a point belongs to the manifold.

        Checks that vertices are inputed in proper form and are
        consistent with the mesh structure.

        Parameters
        ----------
        point : array-like, shape=[..., n_vertices, 3]
            Surface, as the 3D coordinates of the vertices of its triangulation.
        atol : float
            Absolute tolerance.
            Optional, default: backend atol.

        Returns
        -------
        belongs : array-like, shape=[...,]
            Boolean evaluating if point belongs to the space of discrete
            surfaces.
        """
        belongs = self.shape == point.shape[-self.point_ndim :]
        shape = point.shape[: -self.point_ndim]
        if belongs:
            return gs.ones(shape, dtype=bool)
        return gs.zeros(shape, dtype=bool)

    def is_tangent(self, vector, base_point, atol=gs.atol):
        """Check whether the vector is tangent at base_point.

        Tangent vectors are identified with points of the vector space so
        this checks the shape of the input vector.

        Parameters
        ----------
        vector : array-like, shape=[..., n_vertices, 3]
            Vector, i.e. a 3D vector field on the surface.
        base_point : array-like, shape=[..., n_vertices, 3]
            Surface, as the 3D coordinates of the vertices of its triangulation.
        atol : float
            Absolute tolerance.
            Optional, default: backend atol.

        Returns
        -------
        is_tangent : array-like, shape=[...,]
            Boolean denoting if vector is a tangent vector at the base point.
        """
        belongs = self.belongs(vector, atol)
        if base_point is not None and base_point.ndim > vector.ndim:
            return gs.broadcast_to(belongs, base_point.shape[: -self.point_ndim])
        return belongs

    def to_tangent(self, vector, base_point):
        """Project a vector to a tangent space of the manifold.

        Parameters
        ----------
        vector : array-like, shape=[..., n_vertices, 3]
            Vector, i.e. a 3D vector field on the surface.
        base_point : array-like, shape=[..., n_vertices, 3]
            Surface, as the 3D coordinates of the vertices of its triangulation.

        Returns
        -------
        tangent_vec : array-like, shape=[..., *point_shape]
            Tangent vector at base point.
        """
        return gs.copy(vector)

    def projection(self, point):
        """Project a point to the manifold.

        Parameters
        ----------
        point : array-like, shape=[..., n_vertices, 3]
            Surface, as the 3D coordinates of the vertices of its triangulation..

        Returns
        -------
        _ : array-like, shape=[..., n_vertices, 3]
            Point.
        """
        return gs.copy(point)

    def random_point(self, n_samples=1):
        """Sample discrete surfaces.

        This sample random discrete surfaces with the correct number of vertices.

        Parameters
        ----------
        n_samples : int
            Number of surfaces to sample.
            Optional, Default=1

        Returns
        -------
        vertices : array-like, shape=[n_samples, n_vertices, 3]
            Vertices for a batch of points in the space of discrete surfaces.
        """
        vertices = self.ambient_manifold.random_point(n_samples * self.n_vertices)
        vertices = gs.reshape(vertices, (n_samples, self.n_vertices, 3))
        return vertices[0] if n_samples == 1 else vertices

    def _vertices(self, point):
        """Extract 3D vertices coordinates corresponding to each face.

        Parameters
        ----------
        point : array-like, shape=[..., n_vertices, 3]
            Surface, as the 3D coordinates of the vertices of its triangulation.

        Returns
        -------
        vertices : tuple of vertex_0, vertex_1, vertex_2 where:
            vertex_i : array-like, shape=[..., n_faces, 3]
                3D coordinates of the ith vertex of that face.
        """
        slc = tuple([slice(None)] * len(point.shape[:-2]))
        face_coordinates = point[*slc, self.faces]
        return (
            face_coordinates[*slc, :, 0],
            face_coordinates[*slc, :, 1],
            face_coordinates[*slc, :, 2],
        )

    def _triangle_areas(self, point):
        """Compute triangle areas for each face of the surface.

        Heron's formula gives the triangle's area in terms of its sides a b c:,
        As the square root of the product s(s - a)(s - b)(s - c),
        where s is the semiperimeter of the triangle s = (a + b + c)/2.

        Parameters
        ----------
        point : array-like, shape=[..., n_vertices, 3]
             Surface, as the 3D coordinates of the vertices of its triangulation.

        Returns
        -------
        _ : array-like, shape=[..., n_faces, 1]
            Triangle area of each face.
        """
        vertex_0, vertex_1, vertex_2 = self._vertices(point)
        len_edge_12 = gs.linalg.norm((vertex_1 - vertex_2), axis=-1)
        len_edge_02 = gs.linalg.norm((vertex_0 - vertex_2), axis=-1)
        len_edge_01 = gs.linalg.norm((vertex_0 - vertex_1), axis=-1)
        half_perimeter = 0.5 * (len_edge_12 + len_edge_02 + len_edge_01)
        return gs.sqrt(
            (
                half_perimeter
                * (half_perimeter - len_edge_12)
                * (half_perimeter - len_edge_02)
                * (half_perimeter - len_edge_01)
            ).clip(min=1e-6)
        )

    def vertex_areas(self, point):
        """Compute vertex areas for a triangulated surface.

        Vertex area is the area of all of the triangles who are in contact (incident)
        with a specific vertex, according to the formula:
        vertex_areas = 2 * sum_incident_areas / 3.0

        Parameters
        ----------
        point : array-like, shape=[..., n_vertices, 3]
             Surface, as the 3D coordinates of the vertices of its triangulation.

        Returns
        -------
        vertex_areas :  array-like, shape=[..., n_vertices]
            Vertex area for each vertex.
        """
        batch_shape = point.shape[:-2]
        n_vertices = point.shape[-2]
        n_faces = self.faces.shape[0]

        area = self._triangle_areas(point)

        id_vertices = gs.broadcast_to(
            gs.reshape(self.faces, (-1,)), batch_shape + (math.prod(self.faces.shape),)
        )
        val = gs.reshape(
            gs.broadcast_to(gs.expand_dims(area, axis=-2), batch_shape + (3, n_faces)),
            batch_shape + (-1,),
        )
        incident_areas = gs.zeros(batch_shape + (n_vertices,), dtype=val.dtype)

        incident_areas = gs.scatter_add(
            incident_areas,
            dim=-1,
            index=id_vertices,
            src=val,
        )
        return 2 * incident_areas / 3.0

    def normals(self, point):
        """Compute normals at each face of a triangulated surface.

        Normals are the cross products between edges of each face
        that are incident to its x-coordinate.

        Parameters
        ----------
        point : array-like, shape=[..., n_vertices, 3]
            Surface, as the 3D coordinates of the vertices of its triangulation.

        Returns
        -------
        normals_at_point : array-like, shape=[..., n_faces, 3]
            Normals of each face of the mesh.
        """
        vertex_0, vertex_1, vertex_2 = self._vertices(point)
        return 0.5 * gs.cross(vertex_1 - vertex_0, vertex_2 - vertex_0)

    def surface_one_forms(self, point):
        """Compute the vector valued one-forms.

        The one forms are evaluated at the faces of a triangulated surface.

        A one-form is represented by the two vectors (01) and (02) at each face
        of vertices 0, 1, 2.

        Parameters
        ----------
        point : array-like, shape=[..., n_vertices, 3]
             Surface, as the 3D coordinates of the vertices of its triangulation.

        Returns
        -------
        one_forms_bp : array-like, shape=[..., n_faces, 2, 3]
            One form evaluated at each face of the triangulated surface.
        """
        vertex_0, vertex_1, vertex_2 = self._vertices(point)
        return gs.stack([vertex_1 - vertex_0, vertex_2 - vertex_0], axis=-2)

    def face_areas(self, point):
        """Compute the areas for each face of a triangulated surface.

        The corresponds to the volume area for the surface metric, that is
        the volume area of the pullback metric of the immersion defining the
        surface metric.

        Parameters
        ----------
        point : array-like, shape=[..., n_vertices, 3]
            Surface, as the 3D coordinates of the vertices of its triangulation.

        Returns
        -------
        _ : array-like, shape=[..., n_faces,]
            Area computed at each face of the triangulated surface.
        """
        surface_metrics_bp = self.surface_metric_matrices(point)
        return gs.sqrt(gs.linalg.det(surface_metrics_bp))

    @staticmethod
    def _surface_metric_matrices_from_one_forms(one_forms):
        """Compute the surface metric matrices directly from the one_forms.

        This function is useful for efficiency purposes.

        Parameters
        ----------
        one_forms : array-like, shape=[..., n_faces, 2, 3]
            One form evaluated at each face of the triangulated surface.

        Returns
        -------
        metric_mats : array-like, shape=[..., n_faces, 2, 2]
            Surface metric matrices evaluated at each face of
            the triangulated surface.
        """
        return gs.matmul(one_forms, Matrices.transpose(one_forms))

    def surface_metric_matrices(self, point):
        """Compute the surface metric matrices.

        The matrices are evaluated at the faces of a triangulated surface.

        The surface metric is the pullback metric of the immersion q
        defining the surface, i.e. of
        the map q: M -> R3, where M is the parameterization manifold.

        Parameters
        ----------
        point : array like, shape=[..., n_vertices, 3]
            Surface, as the 3D coordinates of the vertices of its triangulation.

        Returns
        -------
        metric_mats : array-like, shape=[..., n_faces, 2, 2]
            Surface metric matrices evaluated at each face of
            the triangulated surface.
        """
        one_forms = self.surface_one_forms(point)
        return self._surface_metric_matrices_from_one_forms(one_forms)

    def laplacian(self, point):
        r"""Compute the mesh Laplacian operator of a triangulated surface.

        Denoting q the surface, i.e. the point in the DiscreteSurfaces manifold,
        the laplacian at :math:`q` is defined as the operator:
        :math:`\Delta_q = - Tr(g_q^{-1} \nabla^2)`
        where :math:`g_q` is the surface metric matrix of :math:`q`.

        Parameters
        ----------
        point :  array-like, shape=[..., n_vertices, 3]
            Surface, as the 3D coordinates of the vertices of its triangulation.

        Returns
        -------
        _laplacian : callable
            Function that evaluates the mesh Laplacian operator at a
            tangent vector field to the surface.
        """
        n_vertices, n_faces = point.shape[-2], self.faces.shape[0]
        vertex_0, vertex_1, vertex_2 = self._vertices(point)
        len_edge_12 = gs.linalg.norm((vertex_1 - vertex_2), axis=-1)
        len_edge_02 = gs.linalg.norm((vertex_0 - vertex_2), axis=-1)
        len_edge_01 = gs.linalg.norm((vertex_0 - vertex_1), axis=-1)

        half_perimeter = 0.5 * (len_edge_12 + len_edge_02 + len_edge_01)
        area = gs.sqrt(
            (
                half_perimeter
                * (half_perimeter - len_edge_12)
                * (half_perimeter - len_edge_02)
                * (half_perimeter - len_edge_01)
            ).clip(min=1e-6)
        )
        sq_len_edge_12, sq_len_edge_02, sq_len_edge_01 = (
            len_edge_12 * len_edge_12,
            len_edge_02 * len_edge_02,
            len_edge_01 * len_edge_01,
        )
        cot_12 = (sq_len_edge_02 + sq_len_edge_01 - sq_len_edge_12) / area
        cot_02 = (sq_len_edge_12 + sq_len_edge_01 - sq_len_edge_02) / area
        cot_01 = (sq_len_edge_12 + sq_len_edge_02 - sq_len_edge_01) / area
        cot = gs.stack([cot_12, cot_02, cot_01], axis=-1)
        cot /= 2.0
        id_vertices_120 = self.faces[:, [1, 2, 0]]
        id_vertices_201 = self.faces[:, [2, 0, 1]]
        id_vertices = gs.reshape(
            gs.stack([id_vertices_120, id_vertices_201], axis=0), (2, n_faces * 3)
        )

        cot_flatten = gs.expand_dims(gs.reshape(cot, point.shape[:-2] + (-1,)), axis=-1)

        def _laplacian(tangent_vec):
            """Evaluate the mesh Laplacian operator.

            The operator is evaluated at a tangent vector at point to the
            manifold of DiscreteSurfaces. In other words, the operator is
            evaluated at a vector field defined on the surface point.

            Parameters
            ----------
            tangent_vec : array-like, shape=[..., n_vertices, 3]
                Tangent vector to the manifold at the base point that is the
                triangulated surface. This tangent vector is a vector field
                on the triangulated surface.

            Returns
            -------
            laplacian_at_tangent_vec: array-like, shape=[..., n_vertices, 3]
                Mesh Laplacian operator of the triangulated surface applied
                to one its tangent vector tangent_vec.
            """
            batch_shape = get_batch_shape(2, point, tangent_vec)
            slc = tuple([slice(None)] * len(batch_shape))

            tangent_vec_diff = (
                tangent_vec[*slc, id_vertices[0]] - tangent_vec[*slc, id_vertices[1]]
            )

            values = gs.einsum(
                "...bd,...bd->...bd",
                gs.broadcast_to(cot_flatten, batch_shape + (n_faces * 3, 3)),
                tangent_vec_diff,
            )

            laplacian_at_tangent_vec = gs.zeros(
                batch_shape + (n_vertices, 3), dtype=values.dtype
            )

            id_vertices_201 = id_vertices[1, :]
            id_vertices_201 = gs.broadcast_to(
                id_vertices_201, batch_shape + id_vertices_201.shape
            )

            for i_dim in range(3):
                laplacian_at_tangent_vec[*slc, :, i_dim] = gs.scatter_add(
                    input=laplacian_at_tangent_vec[*slc, :, i_dim],
                    dim=-1,
                    index=id_vertices_201,
                    src=values[*slc, :, i_dim],
                )
            return laplacian_at_tangent_vec

        return _laplacian


class ElasticMetric(RiemannianMetric):
    """Elastic metric defined by a family of second order Sobolev metrics.

    Each individual discrete surface is represented by a 2D-array of shape
    `[n_vertices, 3]`. See [HSKCB2022]_ for details.

    The parameters a0, a1, b1, c1, d1, a2 (detailed below) are non-negative weighting
    coefficients for the different terms in the metric.

    Parameters
    ----------
    space : DiscreteSurfaces
        Instantiated DiscreteSurfaces manifold.
    a0 : float
        First order parameter.
        Default: 1.
    a1 : float
        Stretching parameter.
        Default: 1.
    b1 : float
        Shearing parameter.
        Default: 1.
    c1 : float
        Bending parameter.
        Default: 1.
    d1 : float
        Additonal first order parameter.
        Default: 1.
    a2 : float
        Second order parameter.
        Default: 1.

    References
    ----------
    .. [HSKCB2022] "Elastic shape analysis of surfaces with second-order
        Sobolev metrics: a comprehensive numerical framework".
        arXiv:2204.04238 [cs.CV], 25 Sep 2022
    """

    def __init__(self, space, a0=1.0, a1=1.0, b1=1.0, c1=1.0, d1=1.0, a2=1.0):
        super().__init__(space=space)
        self.a0 = a0
        self.a1 = a1
        self.b1 = b1
        self.c1 = c1
        self.d1 = d1
        self.a2 = a2

        self.exp_solver = DiscreteSurfacesExpSolver(space, n_steps=10)

        optimizer = ScipyMinimize(
            method="L-BFGS-B",
            jac="autodiff",
            options={"disp": False, "ftol": 0.001},
        )
        self.log_solver = PathStraightening(space, n_nodes=10, optimizer=optimizer)

    def _inner_product_a0(self, tangent_vec_a, tangent_vec_b, vertex_areas_bp):
        r"""Compute term of order 0 within the inner-product.

        Denote h and k the tangent vectors a and b respectively.
        Denote q the base point, i.e. the surface.

        The equation of the inner-product is:
        :math:`\int_M (G_{a_0} + G_{a_1} + G_{b_1} + G_{c_1} + G_{d_1} + G_{a_2})vol_q`.

        This method computes :math:`G_{a_0} = a_0 <h, k>`,
        with notations taken from [HSKCB2022]_.

        Parameters
        ----------
        tangent_vec_a : array-like, shape=[..., n_vertices, 3]
            Tangent vector at base point.
        tangent_vec_b : array-like, shape=[..., n_vertices, 3]
            Tangent vector at base point.
        vertex_areas : array-like, shape=[..., n_vertices, 1]
            Vertex areas for each vertex of the base_point.

        Returns
        -------
        _ : array-like, shape=[...,]
            Term of order 0, and coefficient a0, of the inner-product.

        References
        ----------
        .. [HSKCB2022] "Elastic shape analysis of surfaces with second-order
            Sobolev metrics: a comprehensive numerical framework".
            arXiv:2204.04238 [cs.CV], 25 Sep 2022.
        """
        return self.a0 * gs.sum(
            vertex_areas_bp
            * gs.einsum("...bi,...bi->...b", tangent_vec_a, tangent_vec_b),
            axis=-1,
        )

    def _inner_product_a1(self, ginvdga, ginvdgb, areas_bp):
        r"""Compute a1 term of order 1 within the inner-product.

        Denote h and k the tangent vectors a and b respectively.
        Denote q the base point, i.e. the surface.

        The equation of the inner-product is:
        :math:`\int_M (G_{a_0} + G_{a_1} + G_{b_1} + G_{c_1} + G_{d_1} + G_{a_2})vol_q`.

        This method computes :math:`G_{a_1} = a_1.g_q^{-1} <dh_m, dk_m>`,
        with notations taken from [HSKCB2022]_.

        Parameters
        ----------
        ginvdga : array-like, shape=[n_faces, 2, 2]
            Product of the inverse of the surface metric matrices
            with their differential at a.
        ginvdgb : array-like, shape=[n_faces, 2, 2]
            Product of the inverse of the surface metric matrices
            with their differential at b.
        areas_bp : array-like, shape=[n_faces,]
            Areas of the faces of the surface given by the base point.

        Returns
        -------
        _ : array-like, shape=[...,]
            Term of order 0, and coefficient a1, of the inner-product.

        References
        ----------
        .. [HSKCB2022] "Elastic shape analysis of surfaces with second-order
            Sobolev metrics: a comprehensive numerical framework".
            arXiv:2204.04238 [cs.CV], 25 Sep 2022.
        """
        return self.a1 * gs.sum(
            gs.einsum("...bii->...b", gs.matmul(ginvdga, ginvdgb)) * areas_bp,
            axis=-1,
        )

    def _inner_product_b1(self, ginvdga, ginvdgb, areas_bp):
        r"""Compute b1 term of order 1 within the inner-product.

        Denote h and k the tangent vectors a and b respectively.
        Denote q the base point, i.e. the surface.

        The equation of the inner-product is:
        :math:`\int_M (G_{a_0} + G_{a_1} + G_{b_1} + G_{c_1} + G_{d_1} + G_{a_2})vol_q`.

        This method computes :math:`G_{b_1} = b_1.g_q^{-1} <dh_+, dk_+>`,
        with notations taken from [HSKCB2022]_.

        Parameters
        ----------
        ginvdga : array-like, shape=[n_faces, 2, 2]
            Product of the inverse of the surface metric matrices
            with their differential at a.
        ginvdgb : array-like, shape=[n_faces, 2, 2]
            Product of the inverse of the surface metric matrices
            with their differential at b.
        areas_bp : array-like, shape=[n_faces,]
            Areas of the faces of the surface given by the base point.

        Returns
        -------
        _ : array-like, shape=[...,]
            Term of order 0, and coefficient b1, of the inner-product.

        References
        ----------
        .. [HSKCB2022] "Elastic shape analysis of surfaces with second-order
            Sobolev metrics: a comprehensive numerical framework".
            arXiv:2204.04238 [cs.CV], 25 Sep 2022.
        """
        return self.b1 * gs.sum(
            gs.einsum("...bii->...b", ginvdga)
            * gs.einsum("...bii->...b", ginvdgb)
            * areas_bp,
            axis=-1,
        )

    def _inner_product_c1(self, point_a, point_b, normals_bp, areas_bp):
        r"""Compute c1 term of order 1 within the inner-product.

        Denote h and k the tangent vectors a and b respectively.
        Denote q the base point, i.e. the surface.

        The equation of the inner-product is:
        :math:`\int_M (G_{a_0} + G_{a_1} + G_{b_1} + G_{c_1} + G_{d_1} + G_{a_2})vol_q`.

        This method computes :math:`G_{c_1} = c_1.g_q^{-1} <dh_\perp, dk_\perp>`,
        with notations taken from [HSKCB2022]_.

        Parameters
        ----------
        point_a : array-like, shape=[..., n_vertices, 3]
            Point a corresponding to tangent vec a.
        point_b : array-like, shape=[..., n_vertices, 3]
            Point b corresponding to tangent vec b.
        normals_bp : array-like, shape=[n_faces, 3]
            Normals of each face of the surface given by the base point.
        areas_bp : array-like, shape=[n_faces,]
            Areas of the faces of the surface given by the base point.

        Returns
        -------
        _ : array-like, shape=[...,]
            Term of order 0, and coefficient c1, of the inner-product.

        References
        ----------
        .. [HSKCB2022] "Elastic shape analysis of surfaces with second-order
            Sobolev metrics: a comprehensive numerical framework".
            arXiv:2204.04238 [cs.CV], 25 Sep 2022.
        """
        dna = self._space.normals(point_a) - normals_bp
        dnb = self._space.normals(point_b) - normals_bp
        return self.c1 * gs.sum(
            gs.einsum("...bi,...bi->...b", dna, dnb) * areas_bp, axis=-1
        )

    def _inner_product_d1(
        self, one_forms_a, one_forms_b, one_forms_bp, areas_bp, inv_surface_metrics_bp
    ):
        r"""Compute d1 term of order 1 within the inner-product.

        Denote h and k the tangent vectors a and b respectively.
        Denote q the base point, i.e. the surface.

        The equation of the inner-product is:
        :math:`\int_M (G_{a_0} + G_{a_1} + G_{b_1} + G_{c_1} + G_{d_1} + G_{a_2})vol_q`.

        This method computes :math:`G_{d_1} = d_1.g_q^{-1} <dh_0, dk_0>`,
        with notations taken from [HSKCB2022]_.

        Parameters
        ----------
        one_forms_a : array-like, shape=[n_points, n_faces, 2, 3]
            One forms at point a corresponding to tangent vec a.
        one_forms_b : array-like, shape=[n_points, n_faces, 2, 3]
            One forms at point b corresponding to tangent vec b.
        one_forms_bp : array-like, shape=[n_faces, 2, 3]
            One forms at base point.
        areas_bp : array-like, shape=[n_faces,]
            Areas of the faces of the surface given by the base point.
        inv_surface_metrics_bp : array-like, shape=[n_faces, 2, 2]
            Inverses of the surface metric matrices at each face.

        Returns
        -------
        _ : array-like, shape=[...,]
            Term of order 0, and coefficient d1, of the inner-product.

        References
        ----------
        .. [HSKCB2022] "Elastic shape analysis of surfaces with second-order
            Sobolev metrics: a comprehensive numerical framework".
            arXiv:2204.04238 [cs.CV], 25 Sep 2022.
        """
        one_forms_bp_t = Matrices.transpose(one_forms_bp)

        one_forms_a_t = Matrices.transpose(one_forms_a)
        xa = one_forms_a_t - one_forms_bp_t

        xa_0 = gs.matmul(
            gs.matmul(one_forms_bp_t, inv_surface_metrics_bp),
            gs.matmul(Matrices.transpose(xa), one_forms_bp_t)
            - gs.matmul(one_forms_bp, xa),
        )

        one_forms_b_t = Matrices.transpose(one_forms_b)
        xb = one_forms_b_t - one_forms_bp_t
        xb_0 = gs.matmul(
            gs.matmul(one_forms_bp_t, inv_surface_metrics_bp),
            gs.matmul(Matrices.transpose(xb), one_forms_bp_t)
            - gs.matmul(one_forms_bp, xb),
        )

        return self.d1 * gs.sum(
            gs.einsum(
                "...bii->...b",
                gs.matmul(
                    xa_0,
                    gs.matmul(
                        inv_surface_metrics_bp,
                        Matrices.transpose(xb_0),
                    ),
                ),
            )
            * areas_bp,
            axis=-1,
        )

    def _inner_product_a2(
        self, tangent_vec_a, tangent_vec_b, base_point, vertex_areas_bp
    ):
        r"""Compute term of order 2 within the inner-product.

        Denote h and k the tangent vectors a and b respectively.
        Denote q the base point, i.e. the surface.

        The equation of the inner-product is:
        :math:`\int_M (G_{a_0} + G_{a_1} + G_{b_1} + G_{c_1} + G_{d_1} + G_{a_2})vol_q`.

        This method computes :math:`G_{a_2} = a_2 <\Delta_q h, \Delta_q k>`,
        with notations taken from [HSKCB2022]_.

        Parameters
        ----------
        tangent_vec_a : array-like, shape=[..., n_vertices, 3]
            Tangent vector at base point.
        tangent_vec_b : array-like, shape=[..., n_vertices, 3]
            Tangent vector at base point.
        base_point : array-like, shape=[n_vertices, 3]
            Base point, a surface i.e. the 3D coordinates of its vertices.
        vertex_areas_bp : array-like, shape=[n_vertices, 1]
            Vertex areas for each vertex of the base_point.

        Returns
        -------
        _ : array-like, shape=[...,]
            Term of order 2, and coefficient a2, of the inner-product.

        References
        ----------
        .. [HSKCB2022] "Elastic shape analysis of surfaces with second-order
            Sobolev metrics: a comprehensive numerical framework".
            arXiv:2204.04238 [cs.CV], 25 Sep 2022.
        """
        laplacian_at_base_point = self._space.laplacian(base_point)
        return self.a2 * gs.sum(
            gs.einsum(
                "...bi,...bi->...b",
                laplacian_at_base_point(tangent_vec_a),
                laplacian_at_base_point(tangent_vec_b),
            )
            / vertex_areas_bp,
            axis=-1,
        )

    def inner_product(self, tangent_vec_a, tangent_vec_b, base_point):
        r"""Compute inner product between two tangent vectors at a base point.

        The inner-product has 6 terms, where each term corresponds to
        one of the 6 hyperparameters a0, a1, b1, c1, d1, a2.

        We denote h and k the tangent vectors a and b respectively.
        We denote q the base point, i.e. the surface.

        The six terms of the inner-product are given by:
        :math:`\int_M (G_{a_0} + G_{a_1} + G_{b_1} + G_{c_1} + G_{d_1} + G_{a_2})vol_q`

        where:

        - :math:`G_{a_0} = a_0 <h, k>`
        - :math:`G_{a_1} = a_1.g_q^{-1} <dh_m, dk_m>`
        - :math:`G_{b_1} = b_1.g_q^{-1} <dh_+, dk_+>`
        - :math:`G_{c_1} = c_1.g_q^{-1} <dh_\perp, dk_\perp>`
        - :math:`G_{d_1} = d_1.g_q^{-1} <dh_0, dk_0>`
        - :math:`G_{a_2} = a_2 <\Delta_q h, \Delta_q k>`

        with notations taken from [HSKCB2022]_.

        Parameters
        ----------
        tangent_vec_a : array-like, shape=[..., n_vertices, 3]
            Tangent vector at base point.
        tangent_vec_b : array-like, shape=[..., n_vertices, 3]
            Tangent vector at base point.
        base_point : array-like, shape=[n_vertices, 3]
            Surface, as the 3D coordinates of the vertices of its triangulation.

        Returns
        -------
        inner_prod : array-like, shape=[...]
            Inner-product.

        References
        ----------
        .. [HSKCB2022] "Elastic shape analysis of surfaces with second-order
            Sobolev metrics: a comprehensive numerical framework".
            arXiv:2204.04238 [cs.CV], 25 Sep 2022.
        """
        inner_prod_a0 = 0.0
        inner_prod_a1 = 0.0
        inner_prod_a2 = 0.0
        inner_prod_b1 = 0.0
        inner_prod_c1 = 0.0
        inner_prod_d1 = 0.0

        if self.a0 > 0 or self.a2 > 0:
            vertex_areas_bp = self._space.vertex_areas(base_point)
            if self.a0 > 0:
                inner_prod_a0 = self._inner_product_a0(
                    tangent_vec_a, tangent_vec_b, vertex_areas_bp=vertex_areas_bp
                )
            if self.a2 > 0:
                inner_prod_a2 = self._inner_product_a2(
                    tangent_vec_a,
                    tangent_vec_b,
                    base_point=base_point,
                    vertex_areas_bp=vertex_areas_bp,
                )
        if self.a1 > 0 or self.b1 > 0 or self.c1 > 0 or self.b1 > 0:
            one_forms_bp = self._space.surface_one_forms(base_point)
            surface_metrics_bp = self._space._surface_metric_matrices_from_one_forms(
                one_forms_bp
            )
            areas_bp = gs.sqrt(gs.linalg.det(surface_metrics_bp))

            point_a = base_point + tangent_vec_a
            point_b = base_point + tangent_vec_b

            if self.c1 > 0:
                normals_bp = self._space.normals(base_point)
                inner_prod_c1 = self._inner_product_c1(
                    point_a, point_b, normals_bp, areas_bp
                )
            if self.d1 > 0 or self.b1 > 0 or self.a1 > 0:
                ginv_bp = gs.linalg.inv(surface_metrics_bp)
                one_forms_a = self._space.surface_one_forms(point_a)
                one_forms_b = self._space.surface_one_forms(point_b)
                if self.d1 > 0:
                    inner_prod_d1 = self._inner_product_d1(
                        one_forms_a,
                        one_forms_b,
                        one_forms_bp,
                        areas_bp=areas_bp,
                        inv_surface_metrics_bp=ginv_bp,
                    )

                if self.b1 > 0 or self.a1 > 0:
                    dga = (
                        gs.matmul(one_forms_a, Matrices.transpose(one_forms_a))
                        - surface_metrics_bp
                    )
                    dgb = (
                        gs.matmul(one_forms_b, Matrices.transpose(one_forms_b))
                        - surface_metrics_bp
                    )
                    ginvdga = gs.matmul(ginv_bp, dga)
                    ginvdgb = gs.matmul(ginv_bp, dgb)
                    if self.a1 > 0:
                        inner_prod_a1 = self._inner_product_a1(
                            ginvdga, ginvdgb, areas_bp
                        )
                    if self.b1 > 0:
                        inner_prod_b1 = self._inner_product_b1(
                            ginvdga, ginvdgb, areas_bp
                        )

        return (
            inner_prod_a0
            + inner_prod_a1
            + inner_prod_a2
            + inner_prod_b1
            + inner_prod_c1
            + inner_prod_d1
        )


class DiscreteSurfacesExpSolver(ExpSolver):
    """Class to solve the initial value problem (IVP) for exp.

    Implements methods from discrete geodesic calculus method.
    """

    def __init__(self, space, n_steps=10, optimizer=None):
        super().__init__(solves_ivp=True)
        self._space = space
        if optimizer is None:
            optimizer = ScipyMinimize(
                method="L-BFGS-B",
                jac="autodiff",
                options={"disp": False, "ftol": 0.00001},
            )

        self.n_steps = n_steps
        self.optimizer = optimizer

    def _objective(self, current_point, next_point):
        """Return objective function to compute the next point on the geodesic.

        Parameters
        ----------
        current_point : array-like, shape=[n_vertices, 3]
            Current point on the geodesic.
        next_point : array-like, shape=[n_vertices, 3]
            Next point on the geodesic.

        Returns
        -------
        energy_objective : callable
            Computes energy wrt next next point.
        """
        zeros = gs.zeros_like(current_point)

        def energy_objective(flat_next_next_point):
            """Compute the energy objective to minimize.

            Parameters
            ----------
            next_next_point : array-like, shape=[n_vertices*3]
                Next next point on the geodesic.

            Returns
            -------
            energy_tot : array-like, shape=[,]
                Energy objective to minimize.
            """
            next_next_point = gs.reshape(flat_next_next_point, self._space.shape)
            current_to_next = next_point - current_point
            next_to_next_next = next_next_point - next_point

            def _inner_product_with_current_to_next(tangent_vec):
                """Compute inner-product with tangent vector `current_to_next`.

                The tangent vector `current_to_next` is the vector going from the
                current point, i.e. discrete surface, to the next point on the
                geodesic that is being computed.
                """
                return self._space.metric.inner_product(
                    current_to_next, tangent_vec, current_point
                )

            def _inner_product_with_next_to_next_next(tangent_vec):
                """Compute inner-product with tangent vector `next_to_next_next`.

                The tangent vector `next_to_next_next` is the vector going from the
                next point, i.e. discrete surface, to the next next point on the
                geodesic that is being computed.
                """
                return self._space.metric.inner_product(
                    next_to_next_next, tangent_vec, next_point
                )

            def _norm(base_point):
                """Compute norm of `next_to_next_next` at the base_point.

                The tangent vector `next_to_next_next` is the vector going from the
                next point, i.e. discrete surface, to the next next point on the
                geodesic that is being computed.
                """
                return self._space.metric.squared_norm(next_to_next_next, base_point)

            _, energy_1 = gs.autodiff.value_and_grad(
                _inner_product_with_current_to_next,
                point_ndims=2,
            )(zeros)
            _, energy_2 = gs.autodiff.value_and_grad(
                _inner_product_with_next_to_next_next,
                point_ndims=2,
            )(zeros)
            _, energy_3 = gs.autodiff.value_and_grad(_norm, point_ndims=2)(next_point)

            energy_tot = 2 * energy_1 - 2 * energy_2 + energy_3
            return gs.sum(energy_tot**2)

        return energy_objective

    def _stepforward(self, current_point, next_point):
        """Compute the next point on the geodesic.

        Parameters
        ----------
        current_point : array-like, shape=[n_vertices, 3]
            Current point on the geodesic.
        next_point : array-like, shape=[n_vertices, 3]
            Next point on the geodesic.

        Returns
        -------
        next_next_point : array-like, shape=[n_vertices, 3]
            Next next point on the geodesic.
        """
        flat_initial_next_next_point = gs.flatten(
            (2 * (next_point - current_point) + current_point)
        )

        energy_objective = self._objective(current_point, next_point)

        sol = self.optimizer.minimize(
            energy_objective,
            flat_initial_next_next_point,
        )

        return gs.reshape(sol.x, self._space.shape)

    def _discrete_geodesic_ivp_single(self, tangent_vec, base_point):
        """Solve initial value problem (IVP).

        Given an initial tangent vector and an initial point,
        solve the geodesic equation.

        Parameters
        ----------
        tangent_vec : array-like, shape=[n_vertices, 3]
            Initial tangent vector.
        base_point : array-like, shape=[n_vertices, 3]
            Initial point, i.e. initial discrete surface.

        Returns
        -------
        geod : array-like, shape=[n_steps, n_vertices, 3]
            Discretized geodesic uniformly sampled.
        """
        next_point = base_point + tangent_vec / (self.n_steps - 1)
        geod = [base_point, next_point]
        for _ in range(2, self.n_steps):
            next_next_point = self._stepforward(geod[-2], geod[-1])
            geod.append(next_next_point)

        return gs.stack(geod, axis=0)

    def discrete_geodesic_ivp(self, tangent_vec, base_point):
        """Solve initial value problem (IVP).

        Given an initial tangent vector and an initial point,
        solve the geodesic equation.

        Parameters
        ----------
        tangent_vec : array-like, shape=[n_vertices, 3]
            Initial tangent vector.
        base_point : array-like, shape=[n_vertices, 3]
            Initial point, i.e. initial discrete surface.

        Returns
        -------
        geod : array-like, shape=[n_steps, n_vertices, 3]
            Discretized geodesic uniformly sampled.
        """
        if tangent_vec.ndim != base_point.ndim:
            tangent_vec, base_point = gs.broadcast_arrays(tangent_vec, base_point)

        is_batch = base_point.ndim > self._space.point_ndim
        if not is_batch:
            return self._discrete_geodesic_ivp_single(tangent_vec, base_point)

        return gs.stack(
            [
                self._discrete_geodesic_ivp_single(tangent_vec_, base_point_)
                for tangent_vec_, base_point_ in zip(tangent_vec, base_point)
            ]
        )

    def exp(self, tangent_vec, base_point):
        """Compute exponential map associated to the Riemmannian metric.

        Parameters
        ----------
        tangent_vec : array-like, shape=[..., n_vertices, 3]
            Tangent vector at the base point.
        base_point : array-like, shape=[..., n_vertices, 3]
            Point on the manifold, i.e.

        Returns
        -------
        point : array-like, shape=[..., n_vertices, 3]
            Point on the manifold.
        """
        discr_geod_path = self.discrete_geodesic_ivp(tangent_vec, base_point)
        return discr_geod_path[..., -1, :, :]

    def geodesic_ivp(self, tangent_vec, base_point):
        """Geodesic curve for initial value problem.

        Parameters
        ----------
        tangent_vec : array-like, shape=[..., n_vertices, 3]
            Initial tangent vector.
        base_point : array-like, shape=[..., n_vertices, 3]
            Initial point, i.e. initial discrete surface.

        Returns
        -------
        path : callable
            Time parametrized geodesic curve. `f(t)`.
        """
        discr_geod_path = self.discrete_geodesic_ivp(tangent_vec, base_point)
        return UniformlySampledDiscretePath(
            discr_geod_path, point_ndim=self._space.point_ndim
        )

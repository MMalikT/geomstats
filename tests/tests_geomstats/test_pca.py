"""Unit tests for Tangent PCA."""

import pytest

import geomstats.backend as gs
import tests.conftest
from geomstats.geometry.spd_matrices import SPDMatrices
from geomstats.geometry.special_euclidean import SpecialEuclidean
from geomstats.geometry.special_orthogonal import SpecialOrthogonal
from geomstats.learning.exponential_barycenter import ExponentialBarycenter
from geomstats.learning.pca import TangentPCA


@tests.conftest.np_and_autograd_only
class TestTangentPCA(tests.conftest.TestCase):
    _multiprocess_can_split_ = True

    def setup_method(self):
        self.so3 = SpecialOrthogonal(n=3, point_type="vector")
        self.spd = SPDMatrices(3)

        self.n_samples = 10

        self.X = self.so3.random_uniform(n_samples=self.n_samples)
        self.n_components = 2

    def test_tangent_pca_error(self):
        X = self.X
        tpca = TangentPCA(self.so3, n_components=self.n_components)
        tpca.fit(X)
        X_diff_size = gs.ones((self.n_samples, gs.shape(X)[1] + 1))
        with pytest.raises(ValueError):
            tpca.transform(X_diff_size)

    def test_tangent_pca(self):
        X = self.X
        tpca = TangentPCA(self.so3, n_components=gs.shape(X)[1])
        tpca.fit(X)
        self.assertEqual(tpca.n_features_, gs.shape(X)[1])

    def test_fit_mle(self):
        X = self.X
        tpca = TangentPCA(self.so3, n_components="mle")
        tpca.fit(X)
        self.assertEqual(tpca.n_features_, gs.shape(X)[1])

    def test_fit_to_target_explained_variance(self):
        X = self.spd.random_point(n_samples=5)
        target = 0.90
        tpca = TangentPCA(self.spd, n_components=target)
        tpca.fit(X)
        result = gs.cumsum(tpca.explained_variance_ratio_)[-1] > target
        expected = True
        self.assertAllClose(result, expected)

    def test_fit_matrix(self):
        expected = 2
        X = self.spd.random_point(n_samples=5)
        tpca = TangentPCA(space=self.spd, n_components=expected)
        tpca.fit(X)
        result = tpca.n_components_
        self.assertAllClose(result, expected)

    def test_fit_transform_matrix(self):
        expected = 2
        X = self.spd.random_point(n_samples=5)
        tpca = TangentPCA(space=self.spd, n_components=expected)
        tangent_projected_data = tpca.fit_transform(X)
        result = tangent_projected_data.shape[-1]
        self.assertAllClose(result, expected)

    def test_fit_inverse_transform_matrix(self):
        X = self.spd.random_point(n_samples=5)
        tpca = TangentPCA(space=self.spd)
        tangent_projected_data = tpca.fit_transform(X)
        result = tpca.inverse_transform(tangent_projected_data)
        expected = X
        self.assertAllClose(result, expected, atol=1e-6)

    def test_fit_transform_vector(self):
        expected = 2
        tpca = TangentPCA(space=self.so3, n_components=expected)
        tangent_projected_data = tpca.fit_transform(self.X)
        result = tangent_projected_data.shape[-1]
        self.assertAllClose(result, expected)

    def test_fit_inverse_transform_vector(self):
        tpca = TangentPCA(space=self.so3)
        tangent_projected_data = tpca.fit_transform(self.X)
        result = tpca.inverse_transform(tangent_projected_data)
        expected = self.X
        self.assertAllClose(result, expected)

    def test_fit_fit_transform_matrix(self):
        X = self.spd.random_point(n_samples=5)
        tpca = TangentPCA(space=self.spd)
        expected = tpca.fit_transform(X)
        result = tpca.fit(X).transform(X)
        self.assertAllClose(result, expected)

    def test_fit_matrix_se(self):
        se_mat = SpecialEuclidean(n=3, equip=False)

        X = se_mat.random_point(self.n_samples)

        tpca = TangentPCA(space=se_mat)
        tpca.mean_estimator = ExponentialBarycenter(se_mat)
        tangent_projected_data = tpca.fit_transform(X)
        result = tpca.inverse_transform(tangent_projected_data)
        expected = X
        self.assertAllClose(result, expected)

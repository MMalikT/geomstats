import geomstats.backend as gs
from geomstats.test.data import TestData

from .fiber_bundle import FiberBundleTestData
from .nfold_manifold import NFoldManifoldTestData
from .pullback_metric import PullbackDiffeoMetricTestData
from .quotient_metric import QuotientMetricTestData
from .riemannian_metric import RiemannianMetricTestData


class DiscreteCurvesStartingAtOriginTestData(NFoldManifoldTestData):
    skips = ("not_belongs",)
    fail_for_not_implemented_errors = False

    def interpolate_vec_test_data(self):
        return self.generate_vec_data_with_time()

    def length_vec_test_data(self):
        return self.generate_vec_data()

    def normalize_vec_test_data(self):
        return self.generate_vec_data()

    def normalize_is_unit_length_test_data(self):
        return self.generate_random_data()


class L2CurvesMetricTestData(RiemannianMetricTestData):
    fail_for_not_implemented_errors = False
    fail_for_autodiff_exceptions = False

    skips = (
        "christoffels_vec",
        "inner_product_derivative_matrix_vec",
        "metric_matrix_is_spd",
    )


class ElasticMetricTestData(PullbackDiffeoMetricTestData):
    fail_for_not_implemented_errors = False
    fail_for_autodiff_exceptions = False


class SRVMetricTestData(PullbackDiffeoMetricTestData):
    fail_for_not_implemented_errors = False
    fail_for_autodiff_exceptions = False


class SRVReparametrizationBundleTestData(FiberBundleTestData):
    fail_for_not_implemented_errors = False

    xfails = (
        "tangent_riemannian_submersion_after_horizontal_lift",
        "horizontal_lift_is_horizontal",
        "log_after_align_is_horizontal",
    )
    tolerances = {
        "align": {"atol": 1e-2},
        "align_in_same_fiber": {"atol": 1e-2},
        "log_after_align_is_horizontal": {"atol": 1e-2},
        "tangent_vector_projections_orthogonality_with_metric": {"atol": 5e-1},
        "vertical_projection_is_vertical": {"atol": 1e-1},
        "horizontal_projection_is_horizontal": {"atol": 1e-1},
        "horizontal_lift_is_horizontal": {"atol": 1e-1},
        "tangent_riemannian_submersion_after_vertical_projection": {"atol": 5e-1},
        "tangent_riemannian_submersion_after_horizontal_lift": {"atol": 5e-1},
    }

    def tangent_vector_projections_orthogonality_with_metric_test_data(self):
        return self.generate_random_data()

    def align_in_same_fiber_test_data(self):
        return self.generate_random_data()


class AlignerCmpTestData(TestData):
    N_RANDOM_POINTS = [1]
    trials = 1

    tolerances = {
        "align": {"atol": 0.6},
    }

    def align_test_data(self):
        parametrized_curve_a = lambda x: gs.transpose(
            gs.array([1 + 2 * gs.sin(gs.pi * x), 3 + 2 * gs.cos(gs.pi * x)])
        )
        parametrized_curve_b = lambda x: gs.transpose(
            gs.array([5 * gs.ones(len(x)), 4 * (1 - x) + 1])
        )
        data = [dict(curve_a=parametrized_curve_a, curve_b=parametrized_curve_b)]
        return self.generate_tests(data)


class SRVRotationBundleTestData(TestData):
    def align_test_data(self):
        return self.generate_random_data()


class SRVRotationReparametrizationBundleTestData(TestData):
    tolerances = {
        "align": {"atol": 1e-2},
    }
    xfails = ("align",)

    def align_test_data(self):
        return self.generate_random_data()


class SRVReparametrizationsQuotientMetricTestData(QuotientMetricTestData):
    trials = 1
    fail_for_autodiff_exceptions = False
    fail_for_not_implemented_errors = False


class SRVRotationsQuotientMetricTestData(QuotientMetricTestData):
    trials = 1
    fail_for_autodiff_exceptions = False
    fail_for_not_implemented_errors = False

    xfails = (
        # need to do a better check on the test
        "geodesic_bvp_reverse",
        "geodesic_boundary_points",
    )


class SRVRotationsAndReparametrizationsQuotientMetricTestData(QuotientMetricTestData):
    trials = 1
    fail_for_autodiff_exceptions = False
    fail_for_not_implemented_errors = False

    tolerances = {
        "dist_is_symmetric": {"atol": 1e-2},
        "squared_dist_is_symmetric": {"atol": 1e-2},
    }

    xfails = (
        # need to do a better check on the test
        "geodesic_bvp_reverse",
        "geodesic_boundary_points",
    )

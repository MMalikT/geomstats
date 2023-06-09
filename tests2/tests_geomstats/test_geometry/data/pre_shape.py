from .base import LevelSetTestData
from .fiber_bundle import FiberBundleTestData
from .quotient_metric import QuotientMetricTestData
from .riemannian_metric import RiemannianMetricTestData


class PreShapeSpaceTestData(LevelSetTestData):
    def is_centered_vec_test_data(self):
        return self.generate_vec_data()

    def center_vec_test_data(self):
        return self.generate_vec_data()

    def center_is_centered_test_data(self):
        return self.generate_random_data()


class PreShapeSpaceBundleTestData(FiberBundleTestData):
    skips = ("tangent_riemannian_submersion_after_horizontal_lift",)

    def vertical_projection_correctness_test_data(self):
        return self.generate_random_data()

    def horizontal_projection_correctness_test_data(self):
        return self.generate_random_data()

    def horizontal_projection_is_tangent_test_data(self):
        return self.generate_random_data()

    def alignment_is_symmetric_test_data(self):
        return self.generate_random_data()

    def integrability_tensor_identity_1_test_data(self):
        return self.generate_random_data()

    def integrability_tensor_identity_2_test_data(self):
        return self.generate_random_data()

    def integrability_tensor_alt_test_data(self):
        return self.generate_random_data()

    def integrability_tensor_derivative_is_alternate_test_data(self):
        return self.generate_random_data()

    def integrability_tensor_derivative_is_skew_symmetric_test_data(self):
        return self.generate_random_data()

    def integrability_tensor_derivative_reverses_hor_test_data(self):
        return self.generate_random_data()

    def integrability_tensor_derivative_reverses_ver_test_data(self):
        return self.generate_random_data()

    def integrability_tensor_derivative_parallel_vec_test_data(self):
        return self.generate_vec_data()

    def integrability_tensor_derivative_parallel_optimized_test_data(self):
        return self.generate_random_data()

    def iterated_integrability_tensor_derivative_parallel_vec_test_data(self):
        return self.generate_vec_data()

    def iterated_integrability_tensor_derivative_parallel_optimized_test_data(self):
        return self.generate_random_data()


class PreShapeMetricTestData(RiemannianMetricTestData):
    fail_for_not_implemented_errors = False
    fail_for_autodiff_exceptions = False


class KendallShapeMetricTestData(QuotientMetricTestData):
    fail_for_not_implemented_errors = False
    fail_for_autodiff_exceptions = False

    tolerances = {
        "parallel_transport_bvp_transported_is_tangent": {"atol": 1e-4},
        "parallel_transport_ivp_transported_is_tangent": {"atol": 1e-4},
    }

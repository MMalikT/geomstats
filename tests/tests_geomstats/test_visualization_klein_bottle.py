"""Unit tests for visualization."""

import geomstats.visualization as visualization
import matplotlib
import matplotlib.pyplot as plt
import tests.conftest
from geomstats.geometry.klein_bottle import KleinBottle

matplotlib.use("Agg")  # NOQA


class TestVisualization(tests.conftest.TestCase):
    """Class used to test Klein Bottle visualization."""

    def setup_method(self):
        """Set up figure for Klein Bottle visualization."""
        self.n_samples = 10
        self.KB = KleinBottle(equip=True)
        self.VKB = visualization.klein_bottle()

        plt.figure()

    def test_draw_points_kb(self):
        """Test drawing of 2D point cloud data."""
        points = self.KB.random_point(self.n_samples)
        self.VKB.add_points(points)
        self.VKB.draw_points(space="KB")
        self.VKB.clear_points(self)

    def test_plot_kb(self):
        """Test plotting of Klein Bottle visualization."""
        points = self.KB.random_point(self.n_samples)
        self.VKB.add_points(points)
        self.VKB.plot(self, coords_type="intrinsic")
        self.VKB.clear_points(self)
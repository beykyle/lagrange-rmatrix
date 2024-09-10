from numba import njit
from dataclasses import dataclass
from scipy.special import eval_legendre, gamma
import numpy as np

from ..utils import eval_assoc_legendre, constants, kinematics
from ..reactions import ProjectileTargetSystem
from ..rmatrix import Solver


@dataclass
class ElasticXS:
    r"""
    Holds differential cross section, analyzing power, total cross section and
    reaction cross secton, all at a given energy
    """

    dsdo: np.array
    Ay: np.array
    t: np.float64
    rxn: np.float64


class SpinOrbitInteraction:
    pass

class ElasticXSWorkspace:
    def __init__(
        self,
        projectile: tuple,
        target: tuple,
        sys: ProjectileTargetSystem,
        local_interaction_scalar,
        local_interaction_spin_orbit,
        Elab: np.float64,
        solver: Solver,
        smatrix_abs_tol: np.float64,
        angles: np.array,
    ):
        assert np.diff(angles) > 0 and angles[0] >= 0.0 and angles[-1] <= np.pi

        self.projectile = projectile
        self.target = target
        self.solver = solver
        self.free_matrices = self.solver.free_matrix(
            sys.channel_radii, sys.l, coupled=False
        )
        self.basis_boundary = self.solver.precompute_boundaries(sys.channel_radii[0:1])
        self.mu, self.Ecm, self.k, self.eta = kinematics.semi_relativistic_kinematics(
            sys.mass_target,
            sys.mass_projectile,
            Elab,
            sys.Zproj * sys.Ztarget,
        )
        self.channels = sys.uncoupled(self.Ecm, self.mu, self.k, self.eta)

        self.local_interaction_scalar = local_interaction_scalar
        self.local_interaction_spin_orbit = local_interaction_spin_orbit

        self.lmax = np.max(sys.l)
        self.angles = angles
        ls = self.sys.l[:, np.newaxis]
        self.interactions = []
        self.P_l_costheta = eval_legendre(ls, np.cos(self.angles))
        self.P_1_l_costheta = np.array(
            [eval_assoc_legendre(l, np.cos(self.angles)) for l in self.sys.l]
        )
        self.Zz = self.projectile[1] * self.target[1]
        if self.Zz > 0:
            self.k_c = constants.ALPHA * self.Zz * self.mu / constants.HBARC
            self.eta = self.k_c / self.k
            self.sigma_l = np.angle(gamma(1 + ls + 1j * self.eta))
            sin2 = np.sin(self.angles / 2) ** 2
            self.f_c = (
                -self.eta
                / (2 * self.k * sin2)
                * np.exp(
                    2j * self.sigma_l[0]
                    - 2j * self.eta * np.log(np.sin(self.angles / 2))
                )
            )
            self.rutherford = (
                10 * self.eta**2 / (4 * self.k**2 * np.sin(self.angles / 2) ** 4)
            )
        else:
            self.k_c = 0
            self.eta = 0
            self.sigma_l = np.angle(gamma(1 + ls + 1j * 0))
            self.f_c = 0.0 * np.exp(2j * self.sigma_l[0])
            self.rutherford = 0.0 / (np.sin(self.angles / 2) ** 4)

    def solve_and_get_xs(self, local_args=None):
        splus = np.zeros(self.lmax, dtype=np.complex128)
        sminus = np.zeros(self.lmax - 1, dtype=np.complex128)

        # s-wave
        _, S, _ = self.solver.solve(
            self.channels[0],
            self.asymptotics[0],
            local_interaction=self.local_interaction_scalar,
            local_args=local_args,
            free_matrix=self.free_matrices[0],
            basis_boundary=self.basis_boundary[0],
        )
        splus[0] = S[0, 0]
        # higher partial waves
        for l in range(1, self.lmax):
            _, Sp, _ = self.solver.solve(
                self.channels[l],
                self.asymptotics[l],
                local_interaction=self,  # TODO
                local_args=local_args,
                free_matrix=self.free_matrices[l],
                basis_boundary=self.basis_boundary[l],
            )

    def xs(self, Splus, Sminus):
        return ElasticXS(
            elastic_xs(
                self.k,
                self.angles,
                Splus,
                Sminus,
                self.P_l_costheta,
                self.P_1_l_costheta,
                self.f_c,
                self.sigma_l,
            )
        )

    def xs_rutherford_ratio(self, Splus, Sminus):
        xs = ElasticXS(
            elastic_xs(
                self.k,
                self.angles,
                Splus,
                Sminus,
                self.P_l_costheta,
                self.P_1_l_costheta,
                self.f_c,
                self.sigma_l,
            )
        )
        xs.dsdo /= self.rutherford
        return xs


@njit
def elastic_xs(
    k: float,
    angles: np.array,
    Splus: np.array,
    Sminus: np.array,
    P_l_theta: np.array,
    P_1_l_theta: np.array,
    f_c: np.array = 0,
    sigma_l: np.array = 0,
):
    a = np.zeros_like(angles, dtype=np.complex128) + f_c
    b = np.zeros_like(angles, dtype=np.complex128)

    # l = 0 only has j=1/2 contribution
    a += (1 - Splus[0]) * P_l_theta[0, :] * np.exp(2j * sigma_l[0]) / (2j * k)
    xsrxn = 1 - np.absolute(Splus[0])
    xst = 1 - np.real(Splus[0])  # only valid for neutral projectiles

    for l in range(1, Splus.shape[0]):
        a += (
            (2 * l + 1 - (l + 1) * Splus[l] - l * Sminus[l])
            * P_l_theta[l, :]
            * np.exp(2j * sigma_l[l])
            / (2j * k)
        )
        b += (
            (Sminus[l] - Splus[l])
            * P_1_l_theta[l, :]
            * np.exp(2j * sigma_l[l])
            / (2j * k)
        )
        xsrxn += (l + 1) * (1 - np.absolute(Splus[l])) + l * (
            1 - np.absolute(Sminus[l])
        )
        xst += (l + 1) * (1 - np.real(Splus[l])) + l * (1 - np.real(Sminus[l]))

    dsdo = np.real(a * np.conj(a) + b * np.conj(b)) * 10
    Ay = np.real(a * np.conj(b) + b * np.conj(a)) * 10 / dsdo
    xsrxn *= 10 * np.pi / k**2
    xst *= 10 * 2 * np.pi / k**2

    return dsdo, Ay, xst, xsrxn

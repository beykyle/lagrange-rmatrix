import numpy as np
from numba.experimental import jitclass
from numba import int32, float32

from .bloch_se import ProjectileTargetSystem
from .utils import eval_scaled_interaction, eval_scaled_nolocal_interaction, block


spec = [
    ("nbasis", int32),
    ("nchannels", int32),
    ("abscissa", float64[:]),
    ("nchannels", float64[:]),
]


@jitclass(spec)
class LagrangeRMatrixKernel:
    r"""
    Lagrange-Legendre mesh for the Bloch-Schroedinger equation following:
    Baye, D. (2015). The Lagrange-mesh method. Physics reports, 565, 1-107,
    with the only difference being the domain is scaled in each channel; e.g.
    r -> s_i = r * k_i, and each channel's equation is then divided by it's
    asymptotic kinetic energy in the channel T_i = E_inc - E_i
    """

    def __init__(self, nbasis, nchannels):
        """
        Constructs the Bloch-Schroedinger equation in a basis of nbasis
        Lagrange-Legendre functions shifted and scaled onto [0,k*a] and regulated by 1/k*r,
        and solved by direct matrix inversion.

        """
        self.nbasis = nbasis
        self.nchannels = nchannels

        # generate Lagrange-Legendre quadrature and weights shifted to [0,1] from [-1,1]
        x, w = np.polynomial.legendre.leggauss(self.nbasis)
        self.abscissa = 0.5 * (x + 1)
        self.weights = 0.5 * w

    def local_potential(self, n, m, a, interaction, energy, k):
        """
        evaluates the (n,m)th matrix element for the given local interaction
        """
        assert n <= self.nbasis and n >= 1
        assert m <= self.nbasis and m >= 1

        if n != m:
            return 0  # local potentials are diagonal

        xn = self.abscissa[n - 1]
        s = xn * a

        return eval_scaled_interaction(s, interaction, energy, k)

    def nonlocal_potential(self, n, m, a, interaction, energy, k):
        """
        evaluates the (n,m)th matrix element for the given non-local interaction
        """
        assert n <= self.nbasis and n >= 1
        assert m <= self.nbasis and m >= 1

        xn = self.abscissa[n - 1]
        xm = self.abscissa[m - 1]
        wn = self.weights[n - 1]
        wm = self.weights[m - 1]

        s = xn * a
        sp = xm * a

        utilde = eval_scaled_nolocal_interaction(s, sp, interaction, energy, k)

        return utilde * np.sqrt(wm * wn) * a

    def kinetic_bloch(self, n, m, l, a):
        """
        evaluates the (n,m)th matrix element for the kinetic energy + Bloch operator
        """
        assert n <= self.nbasis and n >= 1
        assert m <= self.nbasis and m >= 1

        xn, xm = self.abscissa[n - 1], self.abscissa[m - 1]
        N = self.nbasis

        if n == m:
            centrifugal = l * (l + 1) / (a * xn) ** 2
            # Eq. 3.128 in [Baye, 2015], scaled by 1/E and with r->s=kr
            return ((4 * N**2 + 4 * N + 3) * xn * (1 - xn) - 6 * xn + 1) / (
                3 * xn**2 * (1 - xn) ** 2
            ) / a**2 + centrifugal
        else:
            # Eq. 3.129 in [Baye, 2015], scaled by 1/E and with r->s=kr
            return (
                (-1.0) ** (n + m)
                * (
                    (N**2 + N + 1.0)
                    + (xn + xm - 2 * xn * xm) / (xn - xm) ** 2
                    - 1.0 / (1.0 - xn)
                    - 1.0 / (1.0 - xm)
                )
                / np.sqrt(xn * xm * (1.0 - xn) * (1.0 - xm))
                / a**2
            )

    def bloch_se_matrix(self, interactions, energies, ks, ls):
        sz = self.nbasis * self.nchannels
        C = np.zeros((sz, sz), dtype=np.cdouble)
        for i in range(self.nchannels):
            for j in range(self.nchannels):
                C[
                    i * self.nbasis : i * self.nbasis + self.nbasis,
                    j * self.nbasis : j * self.nbasis + self.nbasis,
                ] = self.single_channel_bloch_se_matrix(
                    i, j, interactions[i, j], energies[i], ks[i], ls[i]
                )
        return C

    def single_channel_bloch_se_matrix(self, i, j, interaction, energy, k, l):
        C = np.zeros((self.nbasis, self.nbasis), dtype=np.cdouble)
        # Eq. 6.10 in [Baye, 2015], scaled by 1/E and with r->s=kr
        # diagonal submatrices in channel space
        # include full bloch-SE
        if i == j:
            element = lambda n, m: (
                self.kinetic_bloch(n, m, i, j)
                + self.potential(n, m, i, j)
                + self.coulomb_potential(n, m, i, j)
                - (1.0 if n == m else 0.0)
            )
        # off-diagonal terms only include coupling potentials
        else:
            element = lambda n, m: self.potential(n, m, i, j)

        for n in range(1, self.nbasis + 1):
            for m in range(1, self.nbasis + 1):
                C[n - 1, m - 1] = element(n, m)

        return C

    def solve_coupled_channel(self, a, b, l, eta, Z_plus, Z_minus):
        """
        Returns the R-Matrix and the S-matrix, as well as the Green's function in Lagrange-Legendre
        coordinates

        For the coupled-channels case this follows:
        Descouvemont, P. (2016).
        An R-matrix package for coupled-channel problems in nuclear physics.
        Computer physics communications, 200, 199-219.
        """
        A = self.bloch_se_matrix(interaction)

        ach = np.diag(a)

        # b source term - basis functions evaluated at each channel radius

        # find Green's function explicitly in Lagrange-Legendre coords
        G = np.linalg.inv(A)

        # calculate R-matrix
        # Eq. 15 in [Descouvemont, 2016]
        R = np.zeros((self.nchannels, self.nchannels), dtype=np.cdouble)
        for i in range(self.nchannels):
            for j in range(self.nchannels):
                submatrix = block(G, (i, j), (self.nbasis, self.nbasis))
                b1 = b[i * self.nbasis : i * self.nbasis + self.nbasis]
                b2 = b[j * self.nbasis : j * self.nbasis + self.nbasis]
                R[i, j] = np.dot(b1, np.dot(submatrix, b2)) / (a[i, j] * a[i, j])

        S = solve(Z_plus, Z_minus)

        return R, S, G

    def solve_single_channel(self, a, b, l, eta):
        """
        Returns the R-Matrix and the S-matrix, as well as the Green's function in Lagrange-Legendre
        coordinates

        For the coupled-channels case this follows:
        Descouvemont, P. (2016).
        An R-matrix package for coupled-channel problems in nuclear physics.
        Computer physics communications, 200, 199-219.
        """
        A = self.bloch_se_matrix()

        # Eq. 6.11 in [Baye, 2015]
        # b = np.array([self.f(n, a) for n in range(1, self.nbasis + 1)])
        G = np.linalg.inv(A)
        x = np.dot(G, b)
        R = np.dot(x, b) / (a * a)
        S = smatrix(R, a, l, eta)
        return R, S, G

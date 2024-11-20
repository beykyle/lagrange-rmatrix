import numpy as np
from fractions import Fraction
from ..utils.angular_momentum import clebsch_gordan
from ..utils.constants import HBARC
from ..utils.free_solutions import (
    H_plus,
    H_minus,
    H_plus_prime,
    H_minus_prime,
)


# TODO
# combine channel and asymptotics into single class
# in PTS allow for getting channels either coupled or decoupled
# the coupling function should return an array of Channel objects, and a coupling matrix
# add tests for spin-orbit coupling and Ay

def build_channel_sets(lmax, s, level_spins, level_energies):
    r"""
    Returns:
        coupled_channel_sets (dict): a dictionary of dictionaries. The outer key is Jtot,
        and the inner key is Mtot, and the values are Channels2Body instances describing the
        coupled channel system for a given (Jtot,Mtot) pair. For every Jtot key in the outer
        dict, there are (2 Jtot +1) (Mtot, Channels2Body) key, value pairs in the corresponding
        inner dict
    """
    Jmin = max(0, np.min(level_spins) - s)
    Jmax = np.max(level_spins) + lmax + s
    coupled_channel_sets = {}
    for Jtot in np.arange(Jmin, Jmax, 1, dtype=Fraction):
        coupled_channel_sets[Jtot] = {}
        for Mtot in np.arange(-Jtot, Jtot,1):
            coupled_channel_sets[Jtot][Mtot] = Channels2Body(Jtot, Mtot, s, level_spins, level_energies)

    return coupled_channel_sets



class Channels2Body:
    r"""
    Represents the quantum numbers in a 2-body scattering channel in which the projectile
    is structureless and inert, but the target may be excited into energy eigenstates with
    finite spin.

    Attributes:
        Jtot (Fraction): total angular momentum of the channel
        Mtot (Fraction): total angular momentum projection of the channel
        lmax (int): truncation in orbital angular momentum
        s (Fraction): projectile spin
        level_spins (Fraction): total angular momenta of target eigenstates
        level_energies (float): energy eigenvalues of target
    """

    def __init__(self, Jtot, Mtot, lmax, s, level_spins, level_energies):
        assert level_spins.shape == level_energies.shape
        (self.n_levels,) = E.shape
        # iterate over levels
        self.I = []
        self.E = []
        self.l = []
        self.j = []
        self.s = []

        #TODO condense this, store coupling coeffs and channel values
        for En, In in zip(level_energies, level_spins):
            assert Jtot >= In
            # iterate over sum of projectile spin and orbital angular momentum
            for j in np.arange(Jtot - In, Jtot + In):
                # iterate over projection of level spin I
                for mI in np.arange(-In, In, 1):
                    mj = Mtot - mI
                    cg1 = clebsch_gordan(j, mj, In, mI, Jtot, Mtot)

                # iterate over orbital angular momentum
                for l in np.arange( np.abs(j - s), j + s, 1):
                    # and spin projection
                    for mS in np.arange(-s, s, 1):
                        ml = mj - mS
                        cg2 = clebsch_gordan(l,ml,s,ms,j,mj)

    def spin_orbit_coupling(self):
        return (1 / 2) * (self.j * (self.j + 1) - self.l * (self.l + 1) - self.s * (self.s + 1))


def scalar_couplings(Jtot):
    r"""single-channel scattering of two scalar particles, orbital angular momentum
    l equals total angular momentum J

    Parameters:
        Jtot (float) : total angular momentum

    Returns:
        quantum numbers (np.ndarray): quantum numbers (l) in each channel
        couplings (np.ndarray): 0 - there are only diagonal components in the
            partial wave expansion here
    """
    return np.array([[Jtot]]), np.array([[0.0]])


def spin_half_orbit_coupling(Jtot):
    r"""For a spin-1/2 nucleon scattering off a spin-0 nucleus with spin-orbit coupling,
    there are maximally 2 different total angular momentum couplings: l+1/2 and l-1/2.

    Parameters:
        Jtot (float) : total angular momentum

    Returns:
        quantum numbers (np.ndarray): quantum numbers (l) in each channel
        couplings (np.ndarray): coupling matrix (l dot s) between channels. This
            is a 2x2 diagonal matrix in jl space, whih gets multiplied by the spin-orbit
            term.
    """
    assert Jtot >= 1 / 2
    j21 = int(round(2 * Jtot - 1))
    if j21 == 2:
        # J = 1/2 -> l = 0, l dot s = 0
        return np.array([[0]]), np.array([[0.0]])
    else:
        channels = np.array([[Jtot - 1 / 2], [Jtot + 1 / 2]])
        couplings = np.diag([-Jtot - 3 / 2, Jtot + 1 / 2])
        return channels, couplings


def uncouple(channels, couplings):
    # only use for diaginal coupling matrix
    assert np.count_nonzero(couplings - np.diag(np.diagonal(couplings))) == a
    assert couplings.shape == (channels.size, channels.size)
    channels = [ch for ch in channels]
    couplings = [couplings[i, i] for i in range(len(channels))]
    return channels, couplings


class Asymptotics:
    r"""
    Stores the asymptotic behavior in a set of partial wave channels
    """

    def __init__(self, Hp, Hm, Hpp, Hmp):
        self.Hp = Hp
        self.Hm = Hm
        self.Hpp = Hpp
        self.Hmp = Hmp
        self.size = Hp.shape[0]

    def decouple(self):
        r"""
        If coupling is diagonal, this partial wave can be decoupled
        into individual Asymptotics objects
        """
        asym = []
        for i in range(self.size):
            asym.append(
                Asymptotics(
                    self.Hp[i : i + 1],
                    self.Hm[i : i + 1],
                    self.Hpp[i : i + 1],
                    self.Hmp[i : i + 1],
                )
            )
        return asym


class Channels:
    r"""
    Stores information about a set of channels at a given partial wave
    """

    def __init__(self, E, k, mu, eta, a, l, quantum_numbers, couplings):
        self.num_channels = quantum_numbers.shape[0]
        self.quantum_numbers = quantum_numbers
        self.couplings = couplings
        assert couplings.shape == (self.num_channels, self.num_channels)
        self.E = E
        self.k = k
        self.mu = mu
        self.eta = eta
        self.a = a
        self.l = l

        # classical channel velocity
        self.v = HBARC * self.k / self.mu

    def decouple(self):
        r"""
        If self.couplings is diagonal, this partial wave can be decoupled
        into self.size Channels objects
        """
        assert (
            np.count_nonzero(self.couplings - np.diag(np.diagonal(self.couplings))) == 0
        )
        couplings = np.diag(self.couplings)
        channels = []
        for i in range(self.size):
            channels.append(
                Channels(
                    self.E[i : i + 1],
                    self.k[i : i + 1],
                    self.mu[i : i + 1],
                    self.eta[i : i + 1],
                    self.a,
                    self.l[i : i + 1],
                    np.array([[couplings[i]]]),
                )
            )
        return channels


class ProjectileTargetSystem:
    r"""
    Stores physics parameters of asystem. Calculates useful parameters for each partial wave.
    """

    def __init__(
        self,
        channel_radius: np.float64,
        lmax: np.int64,
        mass_target: np.float64 = 0,
        mass_projectile: np.float64 = 0,
        Ztarget: np.float64 = 0,
        Zproj: np.float64 = 0,
        coupling=scalar_couplings,
        channel_levels=None,
    ):
        r"""
        @params
            channel_radius (np.float64):  dimensionless channel radius k_0 * radius
        """

        self.channel_radius = channel_radius
        self.lmax = lmax
        self.l = np.arange(0, lmax + 1, dtype=np.int64)
        self.couplings = [coupling(l) for l in self.l]

        if channel_levels is None:
            channel_levels = np.zeros(self.couplings[0].shape[0], dtype=np.float64)
        self.channel_levels = channel_levels

        self.mass_target = mass_target
        self.mass_projectile = mass_projectile
        self.Ztarget = Ztarget
        self.Zproj = Zproj

    def get_partial_wave_channels(
        self,
        Ecm,
        mu,
        k,
        eta,
    ):
        r"""
        For each partial wave, returns a Channels object describing the array of channels
        in each wave
        """

        channels = []
        asymptotics = []
        for l in range(0, self.lmax + 1):
            num_channels = self.couplings[l].shape[0]
            eta_array = uniform_array_from_scalar_or_array(eta, num_channels)
            channels.append(
                Channels(
                    uniform_array_from_scalar_or_array(Ecm, num_channels),
                    uniform_array_from_scalar_or_array(k, num_channels),
                    uniform_array_from_scalar_or_array(mu, num_channels),
                    eta_array,
                    self.channel_radius,
                    np.ones(num_channels) * l,
                    self.couplings[l],
                )
            )
            asymptotics.append(
                Asymptotics(
                    Hp=np.array(
                        [
                            H_plus(self.channel_radius, l, channel_eta)
                            for channel_eta in eta_array
                        ],
                        dtype=np.complex128,
                    ),
                    Hm=np.array(
                        [
                            H_minus(self.channel_radius, l, channel_eta)
                            for channel_eta in eta_array
                        ],
                        dtype=np.complex128,
                    ),
                    Hpp=np.array(
                        [
                            H_plus_prime(self.channel_radius, l, channel_eta)
                            for channel_eta in eta_array
                        ],
                        dtype=np.complex128,
                    ),
                    Hmp=np.array(
                        [
                            H_minus_prime(self.channel_radius, l, channel_eta)
                            for channel_eta in eta_array
                        ],
                        dtype=np.complex128,
                    ),
                )
            )

        return channels, asymptotics


def uniform_array_from_scalar_or_array(scalar_or_array, size):
    if isinstance(scalar_or_array, np.ndarray):
        return scalar_or_array
    elif isinstance(scalar_or_array, list):
        return np.array(scalar_or_array)
    else:
        return np.ones(size) * scalar_or_array

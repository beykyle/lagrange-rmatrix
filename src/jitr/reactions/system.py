from numba import float64, int64, complex128
from numba.experimental import jitclass
import numpy as np

from ..utils.free_solutions import (
    H_plus,
    H_minus,
    H_plus_prime,
    H_minus_prime,
)

channel_dtype = [
    ("size", int64),
    ("E", float64[:]),
    ("k", float64[:]),
    ("mu", float64[:]),
    ("eta", float64[:]),
    ("a", float64[:]),
    ("l", int64[:]),
    ("weight", float64[:]),
]

asymm_dtype = [
    ("Hp", complex128[:]),
    ("Hm", complex128[:]),
    ("Hpp", complex128[:]),
    ("Hmp", complex128[:]),
]


@jitclass(asymm_dtype)
class Asymptotics:
    def __init__(self, Hp, Hm, Hpp, Hmp):
        self.Hp = Hp
        self.Hm = Hm
        self.Hpp = Hpp
        self.Hmp = Hmp


@jitclass(channel_dtype)
class Channels:
    def __init__(self, E, k, mu, eta, a, l, weight):
        self.size = E.shape[0]
        self.E = E
        self.k = k
        self.mu = mu
        self.eta = eta
        self.a = a
        self.l = l
        self.weight = weight


class ProjectileTargetSystem:
    r"""
    Stores physics parameters of the system. Calculates useful parameters for each channel.
    """

    def __init__(
        self,
        channel_radii: float64[:],
        l: int64[:],
        mass_target: float64 = 0,
        mass_projectile: float64 = 0,
        Ztarget: float64 = 0,
        Zproj: float64 = 0,
        nchannels: int64 = 1,
        level_energies: float64[:] = None,
        incoming_weights: float64[:] = None,
    ):
        self.channel_radii = channel_radii
        if level_energies is None:
            level_energies = np.zeros(nchannels)

        if incoming_weights is None:
            incoming_weights = np.zeros(nchannels)
            incoming_weights[0] = 1

        self.level_energies = level_energies
        self.incoming_weights = incoming_weights
        self.l = l

        self.mass_target = mass_target
        self.mass_projectile = mass_projectile
        self.Ztarget = Ztarget
        self.Zproj = Zproj
        self.nchannels = nchannels

        assert l.shape == (nchannels,)
        assert channel_radii.shape == (nchannels,)
        assert level_energies.shape == (nchannels,)
        assert incoming_weights.shape == (nchannels,)

    def build_channels(
        self,
        Ecm,
        mu,
        k,
        eta,
    ):
        r"""
        Given the kinematic parameters as arrays of shape (nchannels,), returns a `Channels`
        object. If the kinematic parameters are input as scalars rather than arrays, assumes
        that they are the same in each channel.
        """
        if not isinstance(Ecm, np.ndarray):
            Ecm = np.ones(self.nchannels) * Ecm
        if not isinstance(mu, np.ndarray):
            mu = np.ones(self.nchannels) * mu
        if not isinstance(k, np.ndarray):
            k = np.ones(self.nchannels) * k
        if not isinstance(eta, np.ndarray):
            eta = np.ones(self.nchannels) * eta

        channels = Channels(
            Ecm,
            k,
            mu,
            eta,
            self.channel_radii,
            self.l,
            self.incoming_weights,
        )

        Hp = np.array(
            [
                H_plus(channels.a[i], channels.l[i], channels.eta[i])
                for i in range(channels.size)
            ],
            dtype=np.complex128,
        )
        Hm = np.array(
            [
                H_minus(channels.a[i], channels.l[i], channels.eta[i])
                for i in range(channels.size)
            ],
            dtype=np.complex128,
        )
        Hpp = np.array(
            [
                H_plus_prime(channels.a[i], channels.l[i], channels.eta[i])
                for i in range(channels.size)
            ],
            dtype=np.complex128,
        )
        Hmp = np.array(
            [
                H_minus_prime(channels.a[i], channels.l[i], channels.eta[i])
                for i in range(channels.size)
            ],
            dtype=np.complex128,
        )

        return channels, Asymptotics(Hp, Hm, Hpp, Hmp)

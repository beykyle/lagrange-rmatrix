import numpy as np
from matplotlib import pyplot as plt
from scipy.integrate import solve_ivp
from numba import njit
from jitr import (
    ProjectileTargetSystem,
    InteractionMatrix,
    ChannelData,
    LagrangeRMatrixSolver,
    woods_saxon_potential,
    coulomb_charged_sphere,
    delta,
    smatrix,
    schrodinger_eqn_ivp_order1,
)


@njit
def interaction(r, *params):
    (V0, W0, R0, a0, zz, RC) = params
    return woods_saxon_potential(r, (V0, W0, R0, a0)) + coulomb_charged_sphere(
        r, zz, RC
    )


def channel_radius_dependence_test():
    # Potential parameters
    V0 = 60  # real potential strength
    W0 = 20  # imag potential strength
    R0 = 4  # Woods-Saxon potential radius
    a0 = 0.5  # Woods-Saxon potential diffuseness
    params = (V0, W0, R0, a0)

    a_grid = np.linspace(10, 30, 50)
    delta_grid = np.zeros_like(a_grid, dtype=complex)

    ints = InteractionMatrix(1)
    ints.set_local_interaction(woods_saxon_potential)
    solver = LagrangeRMatrix(40, 1, sys, ecom=35)

    for i, a in enumerate(a_grid):
        sys = ProjectileTargetSystem(
            reduced_mass=np.array([939]),
            channel_radius=np.array([a]),
            l=np.array([0]),
        )
        channels = sys.build_channels()
        R, S, _, _ = solver.solve(ints, channels)
        delta, atten = delta(S)
        delta_grid[i] = delta + 1.0j * atten

    plt.plot(a_grid, np.real(delta_grid), label=r"$\mathfrak{Re}\,\delta_l$")
    plt.plot(a_grid, np.imag(delta_grid), label=r"$\mathfrak{Im}\,\delta_l$")
    plt.legend()
    plt.xlabel("channel radius [fm]")
    plt.ylabel(r"$\delta_l$ [degrees]")
    plt.show()


def local_interaction_example():
    E = 14.1
    nodes_within_radius = 5

    sys = ProjectileTargetSystem(
        reduced_mass=np.array([939]),
        channel_radius=np.array([nodes_within_radius * (2 * np.pi)]),
        l=np.array([1]),
        Ztarget=40,
        Zproj=1,
    )

    ch = sys.build_channels(E)

    # Lagrange-Mesh
    solver_lm = LagrangeRMatrix(40, 1, sys, ecom=E)

    # Woods-Saxon potential parameters
    V0 = 60  # real potential strength
    W0 = 20  # imag potential strength
    R0 = 4  # Woods-Saxon potential radius
    a0 = 0.5  # Woods-Saxon potential diffuseness
    params = (V0, W0, R0, a0, sys.Zproj * sys.Ztarget, R0)

    ints = InteractionMatrix(1)
    ints.set_local_interaction(interaction)

    s_values = np.linspace(0.01, sys.channel_radius, 200)
    r_values = s_values / channels[0].k

    # Runge-Kutta
    sol_rk = solve_ivp(
        lambda s, y,: utils.schrodinger_eqn_ivp_order1(
            s, y, ch[0], interaction_matrix.local_matrix[0, 0], params
        ),
        ch[0].domain,
        ch[0].initial_conditions(),
        dense_output=True,
        atol=1.0e-12,
        rtol=1.0e-12,
    ).sol
    u_rk = sol_rk(s_values)[0]
    R_rk = sol_rk(se.a)[0] / (se.a * sol_rk(se.a)[1])
    S_rk = smatrix(R_rk, se.a, se.l, se.eta)

    R_lm, S_lm, u_lm = solver_lm.solve_wavefunction()
    # R_lmp = u_lm(se.a) / (se.a * derivative(u_lm, se.a, dx=1.0e-6))
    u_lm = u_lm(r_values)

    delta_lm, atten_lm = delta(S_lm)
    delta_rk, atten_rk = delta(S_rk)

    # normalization and phase matching
    u_rk = u_rk * np.max(np.real(u_lm)) / np.max(np.real(u_rk)) * (-1j)

    print(f"k: {se.k}")
    print(f"R-Matrix RK: {R_rk:.3e}")
    print(f"R-Matrix LM: {R_lm:.3e}")
    # print(f"R-Matrix LMp: {R_lmp:.3e}")
    print(f"S-Matrix RK: {S_rk:.3e}")
    print(f"S-Matrix LM: {S_lm:.3e}")
    print(f"real phase shift RK: {delta_rk:.3e} degrees")
    print(f"real phase shift LM: {delta_lm:.3e} degrees")
    print(f"complex phase shift RK: {atten_rk:.3e} degrees")
    print(f"complex phase shift LM: {atten_lm:.3e} degrees")

    plt.plot(r_values, np.real(u_rk), "k", label="Runge-Kutta")
    plt.plot(r_values, np.imag(u_rk), ":k")

    plt.plot(r_values, np.real(u_lm), "r", label="Lagrange-Legendre")
    plt.plot(r_values, np.imag(u_lm), ":r")

    plt.legend()
    plt.xlabel(r"$r$ [fm]")
    plt.ylabel(r"$u_{%d} (r) $ [a.u.]" % se.l)
    plt.tight_layout()
    plt.show()


def rmse_RK_LM():
    r"""Test with simple Woods-Saxon plus coulomb without spin-orbit coupling"""

    lgrid = np.arange(0, nwaves - 1, 1)
    egrid = np.linspace(0.01, 100, 10)
    nodes_within_radius = 5

    # channels are the same except for l and uncoupled
    # so just set up a single channel system. We will set
    # incident energy and l later
    sys = ProjectileTargetSystem(
        np.array([939.0]),
        np.array([nodes_within_radius * (2 * np.pi)]),
        l=np.array([0]),
        Ztarget=40,
        Zproj=1,
        nchannels=1,
    )

    # Lagrange-Mesh solver, don't set the energy
    solver_lm = LagrangeRMatrixSolver(40, 1, sys, ecom=None)

    # use same interaction for all channels
    interaction_matrix = InteractionMatrix(1)
    interaction_matrix.set_local_interaction(interaction, 0, 0)

    # Woods-Saxon potential parameters
    V0 = 60  # real potential strength
    W0 = 20  # imag potential strength
    R0 = 4  # Woods-Saxon potential radius
    a0 = 0.5  # Woods-Saxon potential diffuseness
    RC = R0  # Coulomb cutoff

    params = (V0, W0, R0, a0, sys.Zproj * sys.Ztarget, RC)

    error_matrix = np.zeros((len(lgrid), len(egrid)), dtype=complex)

    for i, e in enumerate(egrid):
        for l in lgrid:
            sys.l = np.array([l])
            ch = sys.build_channels(e)
            a = ch[0].domain[1]

            # Runge-Kutta
            sol_rk = solve_ivp(
                lambda s, y,: schrodinger_eqn_ivp_order1(
                    s, y, ch[0], interaction_matrix.local_matrix[0, 0], params
                ),
                ch[0].domain,
                ch[0].initial_conditions(),
                dense_output=True,
                atol=1.0e-12,
                rtol=1.0e-9,
            ).sol

            R_rk = sol_rk(a)[0] / (a * sol_rk(a)[1])
            S_rk = smatrix(R_rk, a, l, ch[0].eta)

            # Lagrange-Legendre R-Matrix
            R_lm, S_lm, x, uext_boundary = solver_lm.solve(
                interaction_matrix, ch, args=params, ecom=e
            )

            # comparison between solvers
            delta_lm, atten_lm = delta(S_lm)
            delta_rk, atten_rk = delta(S_rk)

            err = 0 + 0j

            if np.fabs(delta_rk) > 1e-12:
                err += np.fabs(delta_lm - delta_rk)

            if np.fabs(atten_rk) > 1e-12:
                err += 1j * np.fabs(atten_lm - atten_rk)

            error_matrix[l, i] = err

    lines = []
    for l in lgrid:
        (p1,) = plt.plot(egrid, np.real(error_matrix[l, :]), label=r"$l = %d$" % l)
        (p2,) = plt.plot(egrid, np.imag(error_matrix[l, :]), ":", color=p1.get_color())
        lines.append([p1, p2])

    plt.ylabel(r"$\Delta \equiv | \delta^{\rm RK} - \delta^{\rm LM} |$ [degrees]")
    plt.xlabel(r"$E$ [MeV]")

    legend1 = plt.legend(
        lines[0], [r"$\mathfrak{Re}\, \Delta$", r"$\mathfrak{Im}\, \Delta$"], loc=0
    )
    plt.legend([l[0] for l in lines], [l[0].get_label() for l in lines], loc=1)
    plt.ylim([0, 1])
    plt.yscale("log")
    plt.gca().add_artist(legend1)
    plt.tight_layout()
    plt.show()


if __name__ == "__main__":
    channel_radius_dependence_test()
    local_interaction_example()
    rmse_RK_LM()

import numpy as np
from jitr import reactions, rmatrix
from jitr.reactions.potentials import woods_saxon_potential, coulomb_charged_sphere
from jitr.utils import kinematics, delta


# define interaction
def interaction(r, V0, W0, R0, a0, Zz):
    nuclear = woods_saxon_potential(r, V0, W0, R0, a0)
    coulomb = coulomb_charged_sphere(r, Zz, R0)
    return nuclear + coulomb


interaction_matrix = reactions.InteractionMatrix(1, local_arg_type=dict)
interaction_matrix.set_local_interaction(interaction)

# define system
E_lab = 35  # MeV
Ca48 = (28, 20)
proton = (1, 1)

sys = reactions.ProjectileTargetSystem(
    channel_radii=np.array([5 * np.pi]),
    l=np.array([0]),
    mass_target=kinematics.mass(*Ca48),
    mass_projectile=kinematics.mass(*proton),
    Ztarget=Ca48[1],
    Zproj=proton[1],
)
channels = sys.build_channels_kinematics(E_lab)

# set up solver
solver = rmatrix.Solver(nbasis=40)

# solve for a set of parameters
params = (42.0, 18.1, 4.8, 0.7, sys.Zproj * sys.Ztarget)
interaction_matrix.local_args[0, 0] = params
R, S, uext_boundary = solver.solve(interaction_matrix, channels)

# get phase shift in degrees
phase_shift, phase_attenuation = delta(S[0, 0])
print(f"phase shift: {phase_shift:1.3f} + i ({phase_attenuation:1.3f}) [degrees]")

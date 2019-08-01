"""`exotrace` core functionality."""
import matplotlib.pyplot as plt
import numpy as np


# __all__ = ['Ray', 'Star', 'Spot', 'Scene', 'intersect']


class Ray:
    """A Ray."""

    def __init__(self, origin, direction):
        """Initialize a Ray."""
        self.origin = origin
        self.direction = direction
        self.u = normalize(direction-origin)


class Star:
    """A Star."""

    def __init__(self, center, radius,
                 axis=np.array([0., 1., 0.]),
                 res=100):
        """Initialize a Star."""
        self.center = center
        self.radius = radius
        self.axis = normalize(axis)
        self.inc = 90.
        self.meridian = 0.
        self.res = res
        self.shape = (res, res)
        self.u1 = 0.
        self.u2 = 0.
        self.x = np.linspace(-radius, radius, res)
        self.y = np.linspace(-radius, radius, res)
        self.P = np.zeros((res, res, 3))
        self.N = np.zeros((res, res, 3))
        self.mu = np.zeros((res, res))
        self.r1 = np.zeros((res, res))
        self.theta1 = np.zeros((res, res))
        self.phi1 = np.zeros((res, res))
        self.r = np.zeros((res, res))
        self.theta = np.zeros((res, res))
        self.phi = np.zeros((res, res))
        self.lat = np.zeros((res, res))
        self.lon = np.zeros((res, res))
        self.flux = np.zeros((res, res))
        self.spots = np.array([])

    def add(self, spots, overwrite=False):
        """Add a feature."""
        if overwrite:
            self.spots = spots
        else:
            self.spots = np.append(self.spots, spots)

    def calc_flux(self):
        """Calculate the flux map."""
        self.flux = np.ones((self.res, self.res))
        self.flux = np.ma.masked_where(np.isnan(self.r), self.flux)
        for spot in self.spots:
            dist = haversine(self.lat, self.lon, spot.lat, spot.lon)
            spotted = np.ma.masked_where(dist <= spot.radius, dist)
            self.flux[spotted.mask] = spot.contrast

    def limb_darken(self):
        """Apply the quadratic limb darkening law."""
        self.flux = (self.flux -
                     self.u1*(self.flux - self.mu) -
                     self.u2*(self.flux - self.mu)**2)

    def rotate(self, angle):
        """Rotate about axis by a given angle in degrees."""
        self.meridian = (self.meridian + angle) % 360.
        if self.meridian > 180.:
            self.meridian -= 360.
        for j, i in np.ndindex(self.shape):
            self.P[j, i, :] = rotate_basis(self.P[j, i, :],
                                           gamma=np.radians(-angle))
        self.r = np.sqrt(np.sum(self.P**2, axis=2))
        self.theta = np.arccos(self.P[:, :, 2]/self.r)
        self.phi = np.arctan2(self.P[:, :, 0], self.P[:, :, 1])
        self.lat = np.degrees(self.theta-np.pi/2.)
        self.lon = np.degrees(self.phi)
        self.calc_flux()
        self.limb_darken()

    def set_meridian(self, new_meridian):
        """Set the meridian to a specified longitude in degrees."""
        angle = new_meridian-self.meridian
        self.rotate(angle)

    def set_inclination(self, new_inclination):
        """Set the inclination to a specified degree value."""
        angle = new_inclination - self.inc
        for j, i in np.ndindex(self.shape):
            self.P[j, i, :] = rotate_basis(self.P[j, i, :],
                                           alpha=np.radians(-angle))
        self.r = np.sqrt(np.sum(self.P**2, axis=2))
        self.theta = np.arccos(self.P[:, :, 2]/self.r)
        self.phi = np.arctan2(self.P[:, :, 0], self.P[:, :, 1])
        self.lat = np.degrees(self.theta-np.pi/2.)
        self.lon = np.degrees(self.phi)
        self.calc_flux()
        self.limb_darken()
        self.inc = new_inclination


class Spot:
    """A Spot."""

    def __init__(self, lat, lon, radius, contrast):
        """Initialize a Spot."""
        self.lat = np.float(lat)
        self.lon = np.float(lon)
        self.radius = np.float(radius)
        self.contrast = np.float(contrast)


class Scene:
    """A Scene."""

    def __init__(self, bodies=np.array([]), res=100):
        """Initialize a Scene."""
        self.bodies = bodies
        self.res = res
        self.shape = (res, res)
        self.get_extent()

        self.flux = np.ones(self.shape)*np.nan
        self.body = get_none_array(self.shape)
        self.mu = np.ones(self.shape)*np.nan
        self.t = np.ones(self.shape)*np.inf

    def add(self, bodies):
        """Add bodies to Scene."""
        self.bodies = np.append(self.bodies, bodies)
        self.get_extent()

    def get_extent(self):
        """Get the extent of the Scene."""
        if len(self.bodies) > 0:
            xmin = np.min([body.center[0]-body.radius for body in self.bodies])
            xmax = np.max([body.center[0]+body.radius for body in self.bodies])
            ymin = np.min([body.center[1]-body.radius for body in self.bodies])
            ymax = np.max([body.center[1]+body.radius for body in self.bodies])
            zmax = np.max([body.center[2]+body.radius for body in self.bodies])
        else:
            xmin, xmax = -1, 1
            ymin, ymax = -1, 1
            zmax = np.inf
        self.extent = (np.min([xmin, ymin]), np.max([xmax, ymax]))
        self.x = np.linspace(*self.extent, self.res)
        self.y = np.linspace(*self.extent, self.res)
        self.zmax = zmax

    def trace(self):
        """Perform the ray trace."""
        for j, i in np.ndindex(self.shape):
            ray = Ray(origin=np.array([self.x[i], self.y[j], self.zmax]),
                      direction=np.array([self.x[i], self.y[j], 0.]))
            t_min = np.inf
            for body in self.bodies:
                t = intersect(ray, body)
                if t >= t_min:
                    continue
                t_min = t
                self.body[j, i] = body
                P = ray.origin + ray.u*t
                # N = normalize(P-body.center)
                mu = (np.dot(ray.origin-P, P-body.center) /
                      (np.linalg.norm(ray.origin-P) *
                       np.linalg.norm(P-body.center)))
        #         self.N[j, i] = N
                self.t[j, i] = t
                self.flux[j, i] = 1.
                self.mu[j, i] = mu

    def show(self, array='flux'):
        """Show a property of the Scene."""
        arrays = {'flux': self.flux,
                  'mu': self.mu,
                  't': self.t}
        cmaps = {'flux': 'viridis',
                 'mu': 'viridis',
                 't': 'viridis'}
        values = arrays[array]
        cmap = cmaps[array]
        fig, ax = plt.subplots()
        im = ax.imshow(values, origin='lower', cmap=cmap)
        ax.set_xlabel('x (pixel)')
        ax.set_ylabel('y (pixel)')
        plt.colorbar(im, label=array)
        plt.show()


def normalize(x):
    """Normalize a vector."""
    x /= np.linalg.norm(x)
    return x


def intersect(Ray, Star):
    """
    Intersection of a ray and a sphere.

    See: https://en.wikipedia.org/wiki/Line-sphere_intersection
    """
    a = np.dot(Ray.u, Ray.u)
    origin_center = Ray.origin - Star.center
    b = 2*np.dot(Ray.u, origin_center)
    c = np.dot(origin_center, origin_center) - Star.radius**2
    discriminant = b**2 - 4*a*c
    if discriminant >= 0:
        t1 = (-b + np.sqrt(discriminant))/2.
        t2 = (-b - np.sqrt(discriminant))/2.
        t1, t2 = np.min([t1, t2]), np.max([t1, t2])
        if t1 >= 0:
            return t1
        else:
            return t2
    return np.inf


def angle_between(v0, v1):
    """Determine the angle between two vectors."""
    v0 = normalize(v0)
    v1 = normalize(v1)
    theta = np.arccos(np.dot(v0, v1))
    return theta


def get_Euler_angles(u, theta):
    """
    Get the Euler angles for a specified rotation about an axis.

    Adapted from `starry` jupyter notebook.
    """
    ux, uy, uz = u[0], u[1], u[2]
    # Numerical tolerance
    tol = 1e-16
    if theta == 0:
        theta = tol
    if ux == 0 and uy == 0:
        ux = tol
        uy = tol

    # Elements of the transformation matrix
    costheta = np.cos(theta)
    sintheta = np.sin(theta)
    RA01 = ux * uy * (1 - costheta) - uz * sintheta
    RA02 = ux * uz * (1 - costheta) + uy * sintheta
    RA11 = costheta + uy * uy * (1 - costheta)
    RA12 = uy * uz * (1 - costheta) - ux * sintheta
    RA20 = uz * ux * (1 - costheta) - uy * sintheta
    RA21 = uz * uy * (1 - costheta) + ux * sintheta
    RA22 = costheta + uz * uz * (1 - costheta)

    # Determine the Euler angles
    if ((RA22 < -1 + tol) and (RA22 > -1 - tol)):
        cosbeta = -1
        sinbeta = 0
        cosgamma = RA11
        singamma = RA01
        cosalpha = 1
        sinalpha = 0
    elif ((RA22 < 1 + tol) and (RA22 > 1 - tol)):
        cosbeta = 1
        sinbeta = 0
        cosgamma = RA11
        singamma = -RA01
        cosalpha = 1
        sinalpha = 0
    else:
        cosbeta = RA22
        sinbeta = np.sqrt(1 - cosbeta ** 2)
        norm1 = np.sqrt(RA20 * RA20 + RA21 * RA21)
        norm2 = np.sqrt(RA02 * RA02 + RA12 * RA12)
        cosgamma = -RA20 / norm1
        singamma = RA21 / norm1
        cosalpha = RA02 / norm2
        sinalpha = RA12 / norm2
    alpha = np.arctan2(sinalpha, cosalpha)
    beta = np.arctan2(sinbeta, cosbeta)
    gamma = np.arctan2(singamma, cosgamma)

    return alpha, beta, gamma


def rotate_basis(P, alpha=0., beta=0., gamma=0.):
    """Rotate coordinate basis for point P by specified angles."""
    Rx = np.array([[1., 0., 0.],
                  [0., np.cos(alpha), -np.sin(alpha)],
                  [0., np.sin(alpha), np.cos(alpha)]])
    Ry = np.array([[np.cos(beta), 0., np.sin(beta)],
                  [0., 1., 0.],
                  [-np.sin(beta), 0., np.cos(beta)]])
    Rz = np.array([[np.cos(gamma), -np.sin(gamma), 0.],
                  [np.sin(gamma), np.cos(gamma), 0.],
                  [0., 0., 1]])
    R = Rz @ Ry @ Rx
    return R @ P


def rotate_axis_angle(P, u, theta):
    """Rotate coordinate around axis u by angle theta."""
    u = normalize(u)
    costheta = np.cos(theta)
    sintheta = np.sin(theta)
    ux, uy, uz = u[0], u[1], u[2]
    R = np.array([[costheta + ux**2*(1.-costheta),
                   ux*uy*(1.-costheta) - uz*sintheta,
                   ux*uz*(1.-costheta) + uy*sintheta],
                  [uy*ux*(1.-costheta) + uz*sintheta,
                   costheta + uy**2*(1.-costheta),
                   uy*uz*(1.-costheta) - ux*sintheta],
                  [uz*ux*(1.-costheta) - uy*sintheta,
                   uz*uy*(1.-costheta) + ux*sintheta,
                   costheta + uz**2*(1.-costheta)]])
    return R @ P


def haversine(lat1, lon1, lat2, lon2):
    """
    Calculate the great circle distance between two points.

    (Points specified in decimal degrees)

    Returns distance in degress
    """
    lat1, lon1 = np.radians(lat1), np.radians(lon1)
    lat2, lon2 = np.radians(lat2), np.radians(lon2)
    dlon = lon2 - lon1
    dlat = lat2 - lat1
    a = np.sin(dlat/2.)**2 + np.cos(lat1) * np.cos(lat2) * np.sin(dlon/2.)**2
    dist = 2*np.arcsin(np.sqrt(a))
    return np.degrees(dist)


def get_none_array(shape):
    """Get a numpy array of Nones with the specified shape."""
    arr = None
    for dim in shape:
        arr = [arr]*dim
    return np.array(arr)

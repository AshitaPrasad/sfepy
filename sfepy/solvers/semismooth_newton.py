from sfepy.base.base import *
from sfepy.base.log import Log
from sfepy.solvers.solvers import NonlinearSolver
from sfepy.solvers.nls import Newton, conv_test

class SemismoothNewton(Newton):
    r"""
    The semi-smooth Newton method for solving problems of the following
    structure:

    .. math::
        \begin{split}
          & F(y) = 0 \\
          & A(y) \ge 0 \;,\ B(y) \ge 0 \;,\ \langle A(y), B(y) \rangle = 0
        \end{split}

    The function :math:`F(y)` represents the smooth part of the problem.

    Regular step: :math:`y \leftarrow y - J(y)^{-1} Phi(y)`

    Steepest descent step: :math:`y \leftarrow y - \beta J(y) Phi(y)`

    Notes
    -----
    Although fun_smooth_grad() computes the gradient of the smooth part only,
    it should return the global matrix, where the non-smooth part is
    uninitialized, but pre-allocated.
    """
    name = 'nls.semismooth_newton'

    _colors = {'regular' : 'g', 'steepest_descent' : 'k'}

    def _get_error(self, vec):
        return err

    def __call__(self, vec_x0, conf=None, fun_smooth=None, fun_smooth_grad=None,
                 fun_a=None, fun_a_grad=None, fun_b=None, fun_b_grad=None,
                 lin_solver=None, status=None):

        conf = get_default(conf, self.conf)

        fun_smooth = get_default(fun_smooth, self.fun_smooth)
        fun_smooth_grad = get_default(fun_smooth_grad, self.fun_smooth_grad)
        fun_a = get_default(fun_a, self.fun_a)
        fun_a_grad = get_default(fun_a_grad, self.fun_a_grad)
        fun_b = get_default(fun_b, self.fun_b)
        fun_b_grad = get_default(fun_b_grad, self.fun_b_grad)

        lin_solver = get_default( lin_solver, self.lin_solver )
        status = get_default( status, self.status )

        time_stats = {}

        vec_x = vec_x0.copy()
        vec_x_last = vec_x0.copy()
        vec_dx = None

        if self.log is not None:
            self.log.plot_vlines(color='r', linewidth=1.0)

        err0 = -1.0
        err_last = -1.0
        it = 0
        step_mode = 'regular'
        r_last = None
        reuse_matrix = False
        while 1:

            ls = 1.0
            vec_dx0 = vec_dx;
            i_ls = 0
            while 1:
                tt = time.clock()

                try:
                    vec_smooth_r = fun_smooth(vec_x)
                    vec_a_r = fun_a(vec_x)
                    vec_b_r = fun_b(vec_x)

                except ValueError, exc:
                    vec_smooth_r = vec_semismooth_r = None
                    ok = False

                else:
                    # Semi-smooth equation.
                    vec_semismooth_r = nm.sqrt(vec_a_r**2.0 + vec_b_r**2.0) \
                                       - (vec_a_r + vec_b_r)
                    r_last = (vec_smooth_r, vec_a_r, vec_b_r, vec_semismooth_r)
                    ok = True

                time_stats['rezidual'] = time.clock() - tt

                if ok:
                    vec_r = nm.r_[vec_smooth_r, vec_semismooth_r]

                    try:
                        err = nla.norm(vec_r)
                    except:
                        output('infs or nans in the residual:', vec_semismooth_r)
                        output(nm.isfinite(vec_semismooth_r).all())
                        debug()

                    if self.log is not None:
                        self.log(err, it)

                    if it == 0:
                        err0 = err;
                        break

                    if err < (err_last * conf.ls_on):
                        step_mode = 'regular'
                        break

                    else:
                        output('%s step line search' % step_mode)

                        red = conf.ls_red;
                        output('iter %d, (%.5e < %.5e) (new ls: %e)'\
                               % (it, err, err_last * conf.ls_on, red * ls))

                else: # Failed to compute rezidual.
                    red = conf.ls_red_warp;
                    output('rezidual computation failed for iter %d'
                           ' (new ls: %e)!' % (it, red * ls))
                    if (it == 0):
                        raise RuntimeError('giving up...')
                        
                if ls < conf.ls_min:
                    if not ok:
                        raise RuntimeError('giving up...')

                    if step_mode == 'regular':
                        output('restore previous state')
                        vec_x = vec_x_last.copy()
                        vec_smooth_r, vec_a_r, vec_b_r, vec_semismooth_r = r_last
                        err = err_last
                        reuse_matrix = True                        

                        step_mode = 'steepest_descent'

                    else:
                        output('linesearch failed, continuing anyway')

                    break

                ls *= red;

                vec_dx = ls * vec_dx0;
                vec_x = vec_x_last.copy() - vec_dx

                i_ls += 1

            # End residual loop.

            output('%s step' % step_mode)

            if self.log is not None:
                self.log.plot_vlines([1],
                                     color=self._colors[step_mode],
                                     linewidth=0.5)

            err_last = err;
            vec_x_last = vec_x.copy()

            condition = conv_test(conf, it, err, err0)
            if condition >= 0:
                break

            tt = time.clock()

            if not reuse_matrix:
                ok, mtx_jac = self.compute_jacobian(vec_x, fun_smooth_grad,
                                                    fun_a_grad, fun_b_grad,
                                                    vec_smooth_r,
                                                    vec_a_r, vec_b_r)

            else:
                ok = True
                reuse_matrix = False

            time_stats['matrix'] = time.clock() - tt

            if not ok:
                raise RuntimeError('giving up...')

            tt = time.clock() 

            if step_mode == 'regular':
                vec_dx = lin_solver(vec_r, mtx=mtx_jac)

                vec_e = mtx_jac * vec_dx - vec_r
                lerr = nla.norm(vec_e)
                if lerr > (conf.eps_a * conf.lin_red):
                    output('linear system not solved! (err = %e)' % lerr)

                    output('switching to steepest descent step')
                    step_mode = 'steepest_descent'
                    vec_dx = mtx_jac.T * vec_r

                    debug()

            else:
                vec_dx = mtx_jac.T * vec_r

            time_stats['solve'] = time.clock() - tt

            for kv in time_stats.iteritems():
                output( '%10s: %7.2f [s]' % kv )

            vec_x -= vec_dx
            it += 1

        if status is not None:
            status['time_stats'] = time_stats
            status['err0'] = err0
            status['err'] = err
            status['condition'] = condition

        if conf.log.plot is not None:
            if self.log is not None:
                self.log(save_figure=conf.log.plot)

        return vec_x

    def compute_jacobian(self, vec_x, fun_smooth_grad, fun_a_grad, fun_b_grad,
                         vec_smooth_r, vec_a_r, vec_b_r):
        conf = self.conf

        try:
            mtx_jac = fun_smooth_grad(vec_x)
            mtx_a = fun_a_grad(vec_x)
            mtx_b = fun_b_grad(vec_x)

        except ValueError:
            ok = False

        else:
            ok = True

            n_s = vec_smooth_r.shape[0]
            n_ns = vec_a_r.shape[0]

            aa = nm.abs(vec_a_r)
            ab = nm.abs(vec_b_r)
            iz = nm.where((aa < (conf.macheps * max(aa.max(), 1.0)))
                          & (ab < (conf.macheps * max(ab.max(), 1.0))))[0]
            inz = nm.setdiff1d(nm.arange(n_ns), iz)

            output('non_active/active: %d/%d' % (len(inz), len(iz)))

            mul_a = nm.empty_like(vec_a_r)
            mul_b = nm.empty_like(mul_a)

            # Non-active part of the jacobian.
            if len(inz) > 0:
                a_r_nz = vec_a_r[inz]
                b_r_nz = vec_b_r[inz]

                sqrt_ab = nm.sqrt(a_r_nz**2.0 + b_r_nz**2.0)
                mul_a[inz] = (a_r_nz / sqrt_ab) - 1.0
                mul_b[inz] = (b_r_nz / sqrt_ab) - 1.0

            # Active part of the jacobian.
            if len(iz) > 0:
                vec_z = nm.zeros_like(vec_x)
                vec_z[n_s+iz] = 1.0

                mtx_a_z = mtx_a[iz]
                mtx_b_z = mtx_b[iz]

                sqrt_ab = nm.empty_like(vec_a_r)
                for ir in range(len(iz)):
                    row_a_z = mtx_a_z[ir]
                    row_b_z = mtx_b_z[ir]
                    sqrt_ab[ir] = nm.sqrt((row_a_z * row_a_z.T).todense()
                                          + (row_b_z * row_b_z.T).todense())
                mul_a[iz] = ((mtx_a_z * vec_z) / sqrt_ab) - 1.0
                mul_b[iz] = ((mtx_b_z * vec_z) / sqrt_ab) - 1.0
 
            # Assume the same sparsity structure!
            for ir in range(n_ns):
                ij0 = mtx_jac.indptr[n_s+ir]
                ij1 = mtx_jac.indptr[n_s+ir+1]
                i0 = mtx_a.indptr[ir]
                i1 = mtx_a.indptr[ir+1]
                assert_((ij1-ij0) == (i1 - i0))
                assert_((mtx_b.indptr[ir+1] - mtx_b.indptr[ir]) == (i1 - i0))

                val = ((mul_a[ir] * mtx_a.data[i0:i1])
                       + (mul_b[ir] * mtx_b.data[i0:i1]))
                mtx_jac.data[ij0:ij1] = val

        return ok, mtx_jac
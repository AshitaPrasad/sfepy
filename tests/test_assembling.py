# c: 14.04.2008, r: 14.04.2008
from sfepy.fem.periodic import *

filename_mesh = '../database/tests/plane.mesh'

material_2 = {
    'name' : 'm',
    'region' : 'Omega',
    'values' : {'K' : [[3.0, 0.1], [0.3, 1.0]]},
}

field_1 = {
    'name' : 'pressure',
    'dim' : (1,1),
    'domain' : 'Omega',
    'bases' : {'Omega' : '2_3_P2'}
}

variables = {
    'p' : ('unknown field', 'pressure', 0),
    'q' : ('test field', 'pressure', 'p'),
    'r' : ('parameter field', 'pressure', 'p'),
}

region_1000 = {
    'name' : 'Omega',
    'select' : 'all',
}

region_1 = {
    'name' : 'Left',
    'select' : 'nodes in (x < -0.499)',
}
region_10 = {
    'name' : 'LeftStrip',
    'select' : 'nodes in (x < -0.499) & (y > -0.199) & (y < 0.199)',
}
region_11 = {
    'name' : 'LeftFix',
    'select' : 'r.Left -n r.LeftStrip',
}
region_2 = {
    'name' : 'Right',
    'select' : 'nodes in (x > 0.499)',
}
region_20 = {
    'name' : 'RightStrip',
    'select' : 'nodes in (x > 0.499) & (y > -0.199) & (y < 0.199)',
}
region_21 = {
    'name' : 'RightFix',
    'select' : 'r.Right -n r.RightStrip',
}

ebcs = {
    't_left' : ('LeftFix', {'p.0' : 5.0}),
    't_right' : ('RightFix', {'p.0' : 0.0}),
}

epbc_10 = {
    'name' : 'periodic_x',
    'region' : ['LeftStrip', 'RightStrip'],
    'dofs' : {'p.0' : 'p.0'},
    'match' : 'match_y_line',
}

functions = {
    'match_y_line' : (match_y_line,),
}

integral_1 = {
    'name' : 'i1',
    'kind' : 'v',
    'quadrature' : 'gauss_o2_d2',
}

integral_2 = {
    'name' : 'isurf',
    'kind' : 's',
    'quadrature' : 'gauss_o1_d1',
}

equations = {
    'eq' : """dw_diffusion.i1.Omega( m.K, q, p ) = 0"""
}

solver_0 = {
    'name' : 'ls',
    'kind' : 'ls.scipy_direct',
}

solver_1 = {
    'name' : 'newton',
    'kind' : 'nls.newton',

    'i_max'      : 1,
    'eps_a'      : 1e-10,
    'eps_r'      : 1.0,
    'macheps'   : 1e-16,
    'lin_red'    : 1e-2, # Linear system error < (eps_a * lin_red).
    'ls_red'     : 0.1,
    'ls_red_warp' : 0.001,
    'ls_on'      : 1.1,
    'ls_min'     : 1e-5,
    'check'     : 0,
    'delta'     : 1e-6,
    'is_plot'    : False,
    'problem'   : 'nonlinear', # 'nonlinear' or 'linear' (ignore i_max)
}

fe = {
    'chunk_size' : 1000
}

from sfepy.base.testing import TestCommon

##
# c: 14.04.2008
class Test( TestCommon ):

    ##
    # c: 14.04.2008, r: 14.04.2008
    def from_conf( conf, options ):
        import os.path as op
        from sfepy.solvers.generic import solve_stationary

        problem, vec, data = solve_stationary( conf )
        name = op.join( options.out_dir,
                        op.splitext( op.basename( __file__ ) )[0] + '.vtk' )
        problem.save_state( name, vec )

        test = Test( problem = problem, vec = vec, data = data,
                     conf = conf, options = options )
        return test
    from_conf = staticmethod( from_conf )

    
    ##
    # c: 14.04.2008, r: 14.04.2008
    def test_vector_matrix( self ):
        from sfepy.fem import eval_term_op
        problem  = self.problem

        problem.conf.edit('variables', self.conf.get_raw('variables'))
        problem.set_variables()
        problem.set_equations()
        problem.time_update()

        state = problem.create_state_vector()
        problem.apply_ebc( state )

        aux1 = eval_term_op( state, "dw_diffusion.i1.Omega( m.K, q, p )",
                           problem, dw_mode = 'vector' )
        aux1g = problem.variables.make_full_vec( aux1 )
        problem.time_update( conf_ebc = {}, conf_epbc = {} )
        mtx = eval_term_op( state, "dw_diffusion.i1.Omega( m.K, q, p )",
                          problem, dw_mode = 'matrix' )
        aux2g = mtx * state
        problem.time_update( conf_ebc = self.conf.ebcs,
                            conf_epbc = self.conf.epbcs )
        aux2 = problem.variables.strip_state_vector( aux2g, follow_epbc = True )

        ret = self.compare_vectors( aux1, aux2,
                                   label1 = 'vector mode',
                                   label2 = 'matrix mode' )
        if not ret:
            self.report( 'variable %s: failed' % var_name )

        return ret

    def test_surface_evaluate(self):
        problem = self.problem
        
        problem.conf.edit('variables', {'p' : ('unknown field', 'pressure', 0)})
        problem.set_variables()
##         print self.conf.variables
##         print problem.variables.names
        
        p = problem.create_state_vector()
        p.fill(1.0)

        expr = 'd_surface_integrate.isurf.Left( p )'
        val = problem.evaluate(expr, p=p)
        ok1 = nm.abs(val - 1.0) < 1e-15
        self.report('with unknown: %s, value: %s, ok: %s' \
                    % (expr, val, ok1))

        problem.conf.edit('variables',
                          {'r' : ('parameter field', 'pressure', 'p')})
        problem.set_variables()
##         print self.conf.variables
##         print problem.variables.names

        expr = 'd_surface_integrate.isurf.Left( r )'
        val = problem.evaluate(expr, r=p)
        ok2 = nm.abs(val - 1.0) < 1e-15
        self.report('with parameter: %s, value: %s, ok: %s' \
                    % (expr, val, ok2))

        return ok1 and ok2

    def test_dq_de(self):
        problem = self.problem

        problem.conf.edit('variables', self.conf.get_raw('variables'))
        problem.set_variables()

        p = problem.create_state_vector()
        p[:] = nm.arange(p.shape[0], dtype=p.dtype)

        
        val1 = problem.evaluate('de_grad.i1.Omega( p )', p)
        self.report('de_grad: min, max:', val1.min(), val1.max())

        # Works with one group only, which is the case here.
        ap, vg = problem.variables['p'].get_approximation(('i1', 'Omega', 0))
        aux1 = problem.evaluate('dq_grad.i1.Omega( p )', p)
        aux2 = nm.zeros((aux1.shape[0], 1) + aux1.shape[2:], dtype=aux1.dtype)
        vg.integrate(aux2, aux1)
        val2 = aux2 /  vg.variable(2)
        self.report('dq_grad: min, max:', val2.min(), val2.max())

        ok = self.compare_vectors( val1, val2,
                                   label1 = 'de mode',
                                   label2 = 'dq mode' )
        if not ok:
            self.report( 'variable %s: failed' % var_name )

        return ok

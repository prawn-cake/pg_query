# -*- coding: utf-8 -*-
from pg_query.operators import Evaluable
from pg_query.tokens import CommaValue


class Function(object):
    """Basic function implementation. Use this for aggregation functions"""

    def __init__(self, name):
        self.name = name

    def __call__(self, *args, alias=None):
        value = CommaValue(args)

        if alias:
            fn_str = "{}({}) AS '{}'".format(self.name, value.eval(), alias)
        else:
            fn_str = "{}({})".format(self.name, value.eval())
        return fn_str

    def __repr__(self):
        return "%s(name=%s(*args))" % (self.__class__.__name__, self.name)


class FunctionFactory(object):
    """Neat and natural function factory

    Usage:
        fn.COUNT('*') --> 'COUNT(*)'
        fn.COUNT('*', alias='count_all') --> 'COUNT(*) AS count_all'
    """
    _FUNCTIONS = ('COUNT', 'AVG', 'MIN', 'MAX', 'SUM')

    def __init__(self, rtype):
        self.rtype = rtype

    def __getattr__(self, name):
        # NOTE: probably make sense to restrict function names
        # if name.upper() not in self.FUNCTIONS:
        #     raise AttributeError("Wrong function name '%s'" % name)
        return self.rtype(name=name)


fn = FunctionFactory(rtype=Function)
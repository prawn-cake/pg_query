# -*- coding: utf-8 -*-
import abc
from collections import namedtuple


__all__ = ['Or', 'And', 'Q', 'JOIN', 'F']


NOT_A_VALUE = object()


class Evaluable(object):
    """Evaluable interface class. Just indicate that class has .eval() method
    """

    @abc.abstractmethod
    def eval(self):
        """This method should generally evaluate the value of it's holder.
        In most cases it should return some string part of SQL query

        """
        pass


# Declare join type namedtuple
join_t = namedtuple('JOIN', ['CROSS',
                             'INNER',
                             'LEFT_OUTER',
                             'RIGHT_OUTER',
                             'FULL_OUTER'])
JOIN = join_t(CROSS='CROSS JOIN',
              INNER='INNER JOIN',
              LEFT_OUTER='LEFT OUTER JOIN',
              RIGHT_OUTER='RIGHT OUTER JOIN',
              FULL_OUTER='FULL OUTER JOIN')


class Operand(Evaluable):
    """ Any {field_name} {operator} {value} object representation
    Used in:
        - WHERE clause
        - UPDATE .. SET a = 1 cases
    """
    def __init__(self, name, operator, value):
        self.name = name
        self.operator = operator
        self.value = value

    # NOTE: experimental method
    def __or__(self, other):
        (t1, val1), (t2, val2) = self.eval(), other.eval()
        sql_str = "( {} OR {} )".format(t1, t2)
        return sql_str, (val1, val2,)

    # NOTE: experimental method
    def __and__(self, other):
        (t1, val1), (t2, val2) = self.eval(), other.eval()

        sql_str = "( {} AND {} )".format(t1, t2)
        return sql_str, (val1, val2, )

    def __repr__(self):
        return "%s(name: '%s', operator: '%s', value: %s)" % (
            self.__class__.__name__, self.name, self.operator, self.value)

    def eval(self):
        # We substitute field object to the template directly instead of passing it as '%s' parameters
        if isinstance(self.value, FieldObject):
            return "{} {} {}".format(self.name, self.operator, self.value.eval()), NOT_A_VALUE
        return "{} {} %s".format(self.name, self.operator), self.value


class ConditionOperator(Evaluable):
    """ Basic operator representation"""

    OPERATORS = {
        'eq': '=',
        'gt': '>',    # greater than
        'lt': '<',    # less than
        'gte': '>=',  # greater or equal
        'lte': '<=',  # less or equal
        'neq': '!=',  # not equal
        'is': 'IS',
        'is_not': 'IS NOT',
        'in': 'IN',

        # NOTE: Pattern matching operators
        # More info: https://www.postgresql.org/docs/9.3/static/functions-matching.html
        'like': 'LIKE',
        'ilike': 'ILIKE',
        'similar_to': 'SIMILAR TO'
    }
    OP_SEPARATOR = '__'

    def __init__(self, *args, **kwargs):
        if args:
            self.conditions = args
        elif kwargs:
            self.conditions = kwargs

    @abc.abstractmethod
    def eval(self):
        """Implement operator evaluation in a subclass

        """
        pass

    @classmethod
    def _expand_operands(cls, operands):
        """Expand operands into sql tokens and raw values

        :param operands: list of Operand

        :return: ['a = %s', 'b >= %s', ... ], [1, 2, ...]
        """
        tokens, values = [], []
        for op in operands:
            sql, val = op.eval()
            tokens.append(sql)
            values.append(val)
        return tokens, values

    @classmethod
    def parse_conditions(cls, conditions, result=None):
        """Parse conditions

        :param conditions: list | tuple | dict
        :param result:
        :return: :raise Exception:
        """
        if result is None:
            result = []

        if isinstance(conditions, (list, tuple)):
            for cond in conditions:
                if isinstance(cond, ConditionOperator):
                    val = cond.eval()
                    result.append(val)
                else:
                    cls.parse_conditions(cond, result)

        elif isinstance(conditions, dict):
            operands = cls.parse_dict_condition(conditions)
            tokens, values = cls._expand_operands(operands)
            result.append((tokens, values))
        else:
            raise Exception(
                'Unexpected error. Debug: conditions=%s (%s), result=%s' % (
                    conditions, type(conditions), result))

        tokens, values = [], []
        for sql_str, val_list in result:
            # Can come as a list, like ['a = %s', 'b > %s']
            # or as a prepared string, like '( a = %s AND b > %s )' in case of
            # nested operators
            if isinstance(sql_str, str):
                tokens.append(sql_str)
            else:
                tokens.extend(sql_str)

            values.extend(list(val_list))
        return tokens, values

    @classmethod
    def parse_dict_condition(cls, condition):
        """Parse dict condition to native operators.
        Part of parse_conditions method

        Examples:
            {'a__lt': 1} to 'a < 1'
            {'b__gte': 10} to 'a >= 10'

        :param condition: dict
        :rtype : list
        :return : list of Operands
        """
        values = []
        operands = []
        for key, value in condition.items():
            keys = key.split(cls.OP_SEPARATOR)
            values.append(value)
            if len(keys) == 1:  # equal case
                operator = cls.OPERATORS.get('eq')
                name = keys[0]
            elif len(keys) == 2:
                # operator case
                operator = cls.OPERATORS.get(keys[1])
                if not operator:
                    # handle this as a "<table_name>.<field_name>"
                    table_name, field_name = keys
                    name = '%s.%s' % (table_name, field_name)
                    operator = cls.OPERATORS['eq']
                else:
                    name = keys[0]
            elif len(keys) == 3:
                # compose the name as a "<table_name>.<field_name>"
                table_name, field_name = keys[:2]
                name = '%s.%s' % (table_name, field_name)
                operator = cls.OPERATORS.get(keys[2])
            else:
                raise ValueError('Wrong condition operator in `{}: {}`'.format(
                    key, value))

            operands.append(Operand(name=name, operator=operator, value=value))
        return operands

    def __repr__(self):
        return "%s(condition=%s)" % (self.__class__.__name__, self.conditions)


class Or(ConditionOperator):
    """SQL OR condition operator"""

    def eval(self):
        tokens, values = self.parse_conditions(self.conditions)
        condition_str = ' OR '.join(tokens)
        return ' '.join(['(', condition_str, ')']), tuple(values)


class And(ConditionOperator):
    """SQL AND condition operator"""

    def eval(self):
        tokens, values = self.parse_conditions(self.conditions)
        condition_str = ' AND '.join(tokens)
        return ' '.join(['(', condition_str, ')']), tuple(values)


class QueryObject(Evaluable):
    """Query operator. Inspired by django Q object.
    Useful for more advanced filtering

    Example:
        Q(a__gt=1) | Q(a__lt=10) --> conditional value

    As a part of filtering:
        qs.select('MyTable').filter(Q(a__gt=1) | Q(a__lt=10))

    """

    def __init__(self, **kwargs):
        self.condition = And(kwargs)

    def __or__(self, other):
        return Or(self.condition, other.condition)

    def __and__(self, other):
        return And(self.condition, other.condition)

    def __repr__(self):
        return "Q(%s)" % self.condition

    def eval(self):
        return self.condition.eval()


class FieldObject(Evaluable):
    """Field object. Similar to django F expression.
    Allows to perform atomic operations directly pointing to the field value,
    e.g make such queries:

        UPDATE totals SET total = total + 1 WHERE name = 'bill';

    Where 'total' becomes an F expression
    """
    def __init__(self, value):
        self._value = value

    def eval(self):
        return self._value

    def __add__(self, other):
        return FieldObject("{} + {}".format(self.eval(), other))

    def __sub__(self, other):
        return FieldObject("{} - {}".format(self.eval(), other))

    def __mul__(self, other):
        return FieldObject("{} * {}".format(self.eval(), other))

    # py2 division method
    def __div__(self, other):
        return FieldObject("{} / {}".format(self.eval(), other))

    # py3 division methods
    def __truediv__(self, other):
        return FieldObject("{} / {}".format(self.eval(), other))

    def __floordiv__(self, other):
        return FieldObject("{} / {}".format(self.eval(), other))


Q = QueryObject
F = FieldObject

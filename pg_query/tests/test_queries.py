# -*- coding: utf-8 -*-
import unittest
from pg_query import query_facade as qf
from pg_query.functions import fn
from pg_query.operators import And, Q


class BaseQueryBuilderTest(unittest.TestCase):
    pass


class SelectQueryTest(unittest.TestCase):
    def test_simple_select(self):
        sql_tpl = qf.select('MyTable').get_raw()
        expected_calls = ('SELECT * FROM MyTable', ())
        self.assertEqual(sql_tpl, expected_calls)

    def test_select_with_params(self):
        sql_tpl = qf.select('MyTable').fields('id', 'name').get_raw()
        expected_calls = ('SELECT id, name FROM MyTable', (),)
        self.assertEqual(sql_tpl, expected_calls)

    def test_select_with_all_params(self):
        sql_tpl = qf.select('MyTable')\
            .fields('id', 'name', 'visits')\
            .filter(name='John', visits__gte=5)\
            .group_by('visits')\
            .order_by('id', 'name').desc().limit(10)\
            .offset(5)\
            .get_raw()

        # Expect different order of parameters, but still correct
        expected_calls = (
            ('SELECT id, name, visits FROM MyTable WHERE ( name = %s AND '
             'visits >= %s ) GROUP BY visits ORDER BY id, name DESC LIMIT 10 '
             'OFFSET 5',
             ('John', 5)),

            ('SELECT id, name, visits FROM MyTable WHERE ( visits >= %s AND '
             'name = %s ) GROUP BY visits ORDER BY id, name DESC LIMIT 10 '
             'OFFSET 5',
             (5, 'John'))
        )
        self.assertIn(sql_tpl, expected_calls)

    def test_select_user_function(self):
        """Test query like SELECT * FROM my_fn('arg1', 'arg2')

        """
        result = qf.select_fn('my_fn', args=('a', 1, True)).get_raw()
        expected = (
            ('SELECT * FROM my_fn(%s, %s, %s)', ('a', 1, True, ))
        )
        self.assertEqual(result, expected)

    def test_filter_with_condition_operator(self):
        result = qf.select('MyTable')\
            .fields('a', 'b')\
            .filter(And(a__in=['val1', 'val2'])).get_raw()

        expected_result = (
            'SELECT a, b FROM MyTable WHERE ( a IN %s )',
            (['val1', 'val2'],))
        self.assertEqual(result, expected_result)

    def test_join_with_using_keyword(self):
        sql, values = qf.select('MyTable1')\
            .join('MyTable2', using=('id', 'name')).get_raw()
        self.assertEqual(
            sql, 'SELECT * FROM MyTable1 INNER JOIN MyTable2 USING (id, name)')

    def test_select_with_agg_functions(self):
        raw_query = qf.select('users')\
            .fields(fn.COUNT('*'))\
            .filter(name='Mr.Robot').get_raw()
        self.assertEqual(
            raw_query,
            ('SELECT COUNT(*) FROM users WHERE ( name = %s )', ('Mr.Robot',)))

    def test_select_with_multiple_filter_calls(self):
        """Test the corner case when .filter() method is being called multiple
        times. Query builder concatenate it with AND operator
        """
        # With kwargs
        query = qf.select('users')\
            .filter(name='Mr.Robot')\
            .filter(login='anonymous')\
            .get_raw()
        self.assertEqual(
            query,
            ('SELECT * FROM users WHERE ( ( name = %s ) AND ( login = %s ) )',
             ('Mr.Robot', 'anonymous'))
        )

        # With Q objects
        query = qf.select('users')\
            .filter(Q(name='Mr.Robot') | Q(login='anonymous'))\
            .filter(Q(name='John'))\
            .get_raw()

        expected_sets = (
            ('SELECT * FROM users WHERE ( ( ( name = %s ) OR ( login = %s ) ) '
             'AND ( name = %s ) )',
             ('Mr.Robot', 'anonymous', 'John')),

            ('SELECT * FROM users WHERE ( ( ( login = %s ) OR ( name = %s ) ) '
             'AND ( name = %s ) )',
             ('anonymous', 'Mr.Robot', 'John')),
        )
        self.assertIn(query, expected_sets)


class InsertQueryTest(unittest.TestCase):
    def test_insert_single_row(self):
        sql_tpl = qf.insert('MyTable')\
            .data(name='Alex', gender='M')\
            .get_raw()

        # Expect return values in different, but still correct order
        expected_calls = (
            ('INSERT INTO MyTable (name, gender) VALUES (%s, %s)',
             ('Alex', 'M')),

            ('INSERT INTO MyTable (gender, name) VALUES (%s, %s)',
             ('M', 'Alex')),
        )
        self.assertIn(sql_tpl, expected_calls)

    def test_insert_single_row_with_returning_value(self):
        sql_tpl = qf.insert('MyTable')\
            .data(name='Alex', gender='M')\
            .returning('id')\
            .get_raw()

        # Expect return values in different order
        expected_calls = (
            ('INSERT INTO MyTable (name, gender) VALUES (%s, %s) RETURNING id',
             ('Alex', 'M')),

            ('INSERT INTO MyTable (gender, name) VALUES (%s, %s) RETURNING id',
             ('M', 'Alex')),
        )
        self.assertIn(sql_tpl, expected_calls)

    def test_insert_row_with_all_defaults_values(self):
        sql_tpl = qf.insert('MyTable').defaults().get_raw()

        expected_calls = (
            'INSERT INTO MyTable DEFAULT VALUES', ())
        self.assertEqual(sql_tpl, expected_calls)

    @unittest.skip('fix it later')
    def test_insert_multiple_rows(self):
        values = [('Alex', 'M'), ('Jane', 'F')]
        sql_tpl = qf.insert('MyTable')\
            .values_multi(values)\
            .get_raw()

        expected_calls = (
            'INSERT INTO MyTable VALUES %s', ('(Alex, M), (Jane, F)', )
        )
        self.assertEqual(sql_tpl, expected_calls)
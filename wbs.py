# The COPYRIGHT file at the top level of this repository contains the full
# copyright notices and license terms.
from decimal import Decimal
from sql.aggregate import Sum

from trytond.model import fields
from trytond.pool import Pool, PoolMeta
from trytond.pyson import Eval
from trytond.tools import grouped_slice, reduce_ids
from trytond.transaction import Transaction

__all__ = ['WorkBreakdownStructure']

__metaclass__ = PoolMeta


class WorkBreakdownStructure:
    __name__ = 'wbs'

    certifications = fields.One2Many('wbs.certification', 'wbs',
        'Certifications', readonly=True,
        states={
            'invisible': Eval('type') != 'group',
            },
        depends=['type'])
    certification_lines = fields.One2Many('wbs.certification.line', 'wbs',
        'Certification Lines', readonly=True,
        states={
            'invisible': Eval('type') != 'line',
            },
        depends=['type'])
    certified_quantity = fields.Function(fields.Float('Certified Quantity',
            digits=(16, Eval('unit_digits', 2)),
            states={
                'invisible': Eval('type') != 'line',
                },
            depends=['type', 'unit_digits']),
        'get_certified_quantity')
    progress = fields.Function(fields.Numeric('Progress', digits=(5, 4)),
        'get_progress')

    @classmethod
    def get_certified_quantity(cls, wbs, name):
        pool = Pool()
        Certification = pool.get('wbs.certification')
        CertificationLine = pool.get('wbs.certification.line')
        cursor = Transaction().cursor
        table_a = cls.__table__()
        table_c = cls.__table__()
        certification = Certification.__table__()
        line = CertificationLine.__table__()
        wbs_ids = [w.id for w in wbs]

        result = {}.fromkeys(wbs_ids, 0.0)
        for sub_ids in grouped_slice(wbs_ids):
            cursor.execute(*table_a.join(table_c,
                    condition=(table_c.left >= table_a.left)
                    & (table_c.right <= table_a.right)
                    ).join(line, condition=(
                        line.wbs == table_c.id)
                    ).join(certification, condition=(
                        certification.id == line.certification)).select(
                    table_a.id, Sum(line.quantity),
                    where=reduce_ids(table_a.id, sub_ids)
                    & (certification.state == 'confirmed'),
                    group_by=table_a.id))
            result.update(dict(cursor.fetchall()))
        return result

    @classmethod
    def get_progress(cls, records, name):
        result = {}
        for wbs in records:
            result[wbs.id] = (Decimal(wbs.certified_quantity) /
                Decimal(wbs.quantity or 1.0))
        return result

    @classmethod
    def copy(cls, records, default=None):
        if default is None:
            default = {}
        default.setdefault('cretifications', [])
        default.setdefault('cretification_lines', [])
        return super(WorkBreakdownStructure, cls).copy(records)

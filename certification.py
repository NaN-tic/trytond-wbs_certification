# The COPYRIGHT file at the top level of this repository contains the full
# copyright notices and license terms.
from trytond.pool import Pool, PoolMeta
from trytond.model import Workflow, ModelView, ModelSQL, fields
from trytond.pyson import Bool, Eval
from trytond.transaction import Transaction
import datetime

__all__ = ['Certification', 'CertificationLine']
__metaclass__ = PoolMeta


class Certification(Workflow, ModelSQL, ModelView):
    'WBS Certification'
    __name__ = 'wbs.certification'

    name = fields.Char('Name', readonly=True)
    date = fields.Date('Date')
    party = fields.Many2One('party.party', 'Party', required=True)
    company = fields.Many2One('company.company', 'Company', required=True,
        select=True,
        states={
            'readonly': Bool(Eval('lines', [])),
            }, depends=['lines'])
    wbs = fields.Many2One('wbs', 'Work Breakdown Structure', required=True,
        domain=[
            ('parent', '=', None),
            ('party', '=', Eval('party', 0)),
            ],
        depends=['party'])
    lines = fields.One2Many('wbs.certification.line', 'certification',
        'Lines')
    state = fields.Selection([
            ('draft', 'Draft'),
            ('proposal', 'Proposal'),
            ('confirmed', 'Confirmed'),
            ('cancel', 'Cancel')
            ], 'State', readonly=True, select=True)

    @classmethod
    def __setup__(cls):
        super(Certification, cls).__setup__()
        cls._transitions |= set((
                ('draft', 'proposal'),
                ('proposal', 'draft'),
                ('proposal', 'confirmed'),
                ('confirmed', 'cancel'),
                ('draft', 'cancel'),
                ('cancel', 'draft'),
                ))
        cls._buttons.update({
            'confirmed': {
                'invisible': (Eval('state') != 'proposal'),
                'icon': 'tryton-go-next',
                },
            'proposal': {
                'invisible': (Eval('state') != 'draft'),
                'icon': 'tryton-ok',
                },
            'draft': {
                'invisible': ~Eval('state').in_(['proposal', 'cancel']),
                'icon': 'tryton-clear',
                },
            'cancel': {
                'invisible': ~Eval('state').in_(['confirmed', 'draft']),
                'icon': 'tryton-cancel',
                },
            'set_wbs': {
                'readonly': ((Eval('state') != 'draft')
                        | ~Bool(Eval('wbs'))),
                },
            'invoice': {
                'readonly': ((Eval('state') != 'confirmed')
                        | ~Bool(Eval('wbs')) |
                        (Eval('invoice_state') != 'pending')),
                'icon': 'tryton-go-next',
                },
            })
        cls._error_messages.update({
                'delete_non_draft': ('Certification "%s" must be in draft '
                    'state in order to be deleted.'),
                })

    @staticmethod
    def default_company():
        return Transaction().context.get('company')

    @staticmethod
    def default_test_date():
        return datetime.datetime.now()

    @staticmethod
    def default_state():
        return 'draft'

    @staticmethod
    def default_invoice_state():
        return 'pending'

    @classmethod
    @ModelView.button
    @Workflow.transition('draft')
    def draft(cls, certifications):
        pass

    @classmethod
    @ModelView.button
    @Workflow.transition('confirmed')
    def confirmed(cls, certifications):
        cls.set_number(certifications)
        pass

    @classmethod
    @Workflow.transition('proposal')
    def proposal(cls, certifications):
        pass

    @classmethod
    @ModelView.button
    @Workflow.transition('cancel')
    def cancel(cls, certifications):
        pass

    @classmethod
    @ModelView.button
    def set_wbs(cls, certifications):
        CertLine = Pool().get('wbs.certification.line')
        for cert in certifications:
            if cert.wbs:
                CertLine.delete(cert.lines)
                cert.create_lines(cert.wbs)

    def create_lines(self, wbs, parent=None):
        CL = Pool().get('wbs.certification.line')
        for l in wbs.childs:
            if l.type in ('subtotal', 'total'):
                continue
            cl = CL()
            cl.certification = self
            cl.wbs = l
            cl.parent = parent
            cl.save()
            if l.childs:
                self.create_lines(l, cl)

    @classmethod
    def set_number(cls, certifications):
        pool = Pool()
        Config = pool.get('sale.configuration')
        Sequence = pool.get('ir.sequence')
        config = Config(1)
        sequence = config.certification_sequence
        to_write = []

        for cert in certifications:
            to_write.extend(([cert], {
                        'name': Sequence.get_id(sequence.id),
                        }))
        if to_write:
            cls.write(*to_write)

    @classmethod
    def delete(cls, certifications):
        for certification in certifications:
            if certification.state != 'draft':
                cls.raise_user_error('delete_non_draft', (
                        certification.rec_name,
                        ))
        return super(Certification, cls).delete(certifications)

    @classmethod
    def copy(cls, certifications, default=None):
        pool = Pool()
        Line = pool.get('wbs.certification.line')
        if default is None:
            default = {}
        default['lines'] = []
        new_certs = super(Certification, cls).copy(certifications,
            default=default)
        for cert, new_cert in zip(certifications, new_certs):
            new_default = default.copy()
            new_default['certification'] = new_cert.id
            Line.copy(cert.lines, default=new_default)
        return new_certs


class CertificationLine(ModelSQL, ModelView):
    'WBS Certification Line'
    __name__ = 'wbs.certification.line'

    certification = fields.Many2One('wbs.certification', 'Certification',
        required=True, ondelete='CASCADE')
    wbs = fields.Many2One('wbs', 'WBS',
        domain=[
            ('type', '=', 'line'),
            ])
    wbs_product = fields.Function(fields.Many2One('product.product',
        'Product'), 'get_wbs_field')
    wbs_quantity = fields.Function(fields.Float('WBS Quantity'),
        'get_wbs_field')
    wbs_unit = fields.Function(fields.Many2One('product.uom', 'Unit'),
        'get_wbs_field')

    quantity = fields.Float('Quantity')

    parent = fields.Many2One('wbs.certification.line', 'Parent', select=True,
        left='left', right='right', ondelete='CASCADE',
        domain=[
            ('certification', '=', Eval('certification')),
            # compatibility with sale_subchapters
            ],
        depends=['certification'])
    left = fields.Integer('Left', required=True, select=True)
    right = fields.Integer('Right', required=True, select=True)
    children = fields.One2Many('wbs.certification.line', 'parent', 'Children',
        domain=[
            ('certification', '=', Eval('certification')),
            ],
        depends=['certification'])

    @staticmethod
    def default_left():
        return 0

    @staticmethod
    def default_right():
        return 0

    def get_wbs_field(self, name):
        if not self.wbs:
            return None
        field = getattr(self.wbs, name.replace('wbs_', ''))
        if hasattr(field, 'id'):
            return field.id
        return field

    @classmethod
    def copy(cls, lines, default=None):
        # TODO: To test
        if default is None:
            default = {}
        default['wbs'] = None
        default['children'] = []
        new_lines = []
        for line in lines:
            new_line, = super(CertificationLine, cls).copy([line], default)
            new_lines.append(new_line)
            new_default = default.copy()
            new_default['parent'] = new_line.id
            cls.copy(line.children, default=new_default)
        return new_lines

# The COPYRIGHT file at the top level of this repository contains the full
# copyright notices and license terms.
from trytond.pool import Pool
from .configuration import *
from .certification import *
from .wbs import *


def register():
    Pool.register(
        Configuration,
        ConfigurationCompany,
        Certification,
        CertificationLine,
        WorkBreakdownStructure,
        module='wbs_certification', type_='model')
